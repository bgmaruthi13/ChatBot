import logging

from pypdf import PdfReader

from .models import Chunk, Document
from vectorstore.client import add_chunks
from vectorstore.client import delete_document as delete_document_from_store
from vectorstore.embedding import embed_many

logger = logging.getLogger(__name__)


def extract_text_from_path(path):
    """Extract text per page from a PDF file on disk.

    Returns a list of (page_number, text) tuples, 1-indexed. Digital-PDF
    text layer only - no OCR fallback (dropped, see BACKLOG.md 2.2: it
    needs Tesseract + Poppler system binaries this environment can't
    install without admin elevation).
    """
    reader = PdfReader(path)
    return [(i, page.extract_text() or "") for i, page in enumerate(reader.pages, start=1)]


def extract_text(document):
    """Extract text per page from a Document's uploaded PDF."""
    return extract_text_from_path(document.file.path)


# Word count, not a true subword tokenizer count - a lightweight
# approximation that needs no extra dependency. Close enough for
# windowing chunks; embedding models truncate long inputs regardless.
CHUNK_SIZE_WORDS = 800
CHUNK_OVERLAP_WORDS = 150
CHUNK_STRIDE_WORDS = CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS


def chunk_text(pages):
    """Split extracted per-page text into overlapping, retrieval-sized
    chunks.

    `pages` is a list of (page_number, text) tuples, e.g. from
    extract_text(). Returns a list of dicts ready to become Chunk rows:
    {"text", "page_number", "chunk_index"} - page_number is the page the
    chunk's first word came from.
    """
    words = []
    word_pages = []
    for page_number, text in pages:
        for word in text.split():
            words.append(word)
            word_pages.append(page_number)

    if not words:
        return []

    chunks = []
    start = 0
    total = len(words)
    while start < total:
        end = min(start + CHUNK_SIZE_WORDS, total)
        chunks.append(
            {
                "text": " ".join(words[start:end]),
                "page_number": word_pages[start],
                "chunk_index": len(chunks),
            }
        )
        if end == total:
            break
        start += CHUNK_STRIDE_WORDS

    return chunks


def embed_document_chunks(document):
    """Batch-embed every chunk of a document and mark each embedded=True
    as it succeeds (so a partial failure doesn't silently look complete).

    Returns the chunks (ordered by chunk_index) paired with their
    vectors, so callers (Epic 5's vector-store wiring) can push them to
    Chroma without recomputing.
    """
    chunks = list(document.chunks.order_by("chunk_index"))
    if not chunks:
        return []

    vectors = embed_many([chunk.text for chunk in chunks])

    for chunk in chunks:
        chunk.embedded = True
    Chunk.objects.bulk_update(chunks, ["embedded"])

    return list(zip(chunks, vectors))


def process_document(document):
    """Run the full processing pipeline for a Document: extract, chunk,
    embed, store vectors. On success, status becomes 'ready'.

    Never raises - failures at any stage (corrupt file, password
    protection, unreadable PDF) are caught and recorded as
    status='failed' with a human-readable error_message.
    """
    document.status = Document.Status.PROCESSING
    document.save(update_fields=["status"])

    try:
        pages = extract_text(document)
        document.page_count = len(pages)
        document.save(update_fields=["page_count"])

        document.chunks.all().delete()
        chunk_dicts = chunk_text(pages)
        Chunk.objects.bulk_create(
            Chunk(document=document, **chunk_dict) for chunk_dict in chunk_dicts
        )

        chunk_vector_pairs = embed_document_chunks(document)
        if chunk_vector_pairs:
            chunks, vectors = zip(*chunk_vector_pairs)
            add_chunks(document.pk, chunks, vectors)

        document.status = Document.Status.READY
        document.save(update_fields=["status"])
    except Exception as exc:
        logger.exception("Processing failed for document %s", document.pk)
        document.status = Document.Status.FAILED
        document.error_message = str(exc) or exc.__class__.__name__
        document.save(update_fields=["status", "error_message"])


def delete_document_vectors(document_id):
    """Remove a document's vectors from the vector store."""
    delete_document_from_store(document_id)
