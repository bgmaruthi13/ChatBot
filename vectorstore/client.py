import threading

import chromadb
from django.conf import settings

COLLECTION_NAME = "chunks"

_client = None
_client_lock = threading.Lock()


def _get_collection():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _client.get_or_create_collection(COLLECTION_NAME)


def add_chunks(document_id, chunks, vectors):
    """Add a document's chunks + their precomputed vectors to the store.

    `chunks` is an iterable of Chunk model instances; `vectors` is a
    parallel iterable of embeddings (same order, same length).
    """
    chunks = list(chunks)
    if not chunks:
        return

    _get_collection().upsert(
        ids=[str(chunk.pk) for chunk in chunks],
        embeddings=list(vectors),
        documents=[chunk.text for chunk in chunks],
        metadatas=[
            {
                "document_id": document_id,
                "chunk_id": chunk.pk,
                "page_number": chunk.page_number,
            }
            for chunk in chunks
        ],
    )


def query(vector, document_id=None, top_k=5):
    """Similarity search. Returns a list of dicts:
    {"chunk_id", "document_id", "page_number", "text", "distance"},
    ordered nearest-first. Scoped to `document_id` if given.
    """
    where = {"document_id": document_id} if document_id is not None else None
    result = _get_collection().query(
        query_embeddings=[list(vector)],
        n_results=top_k,
        where=where,
    )

    if not result["ids"] or not result["ids"][0]:
        return []

    return [
        {
            "chunk_id": metadata["chunk_id"],
            "document_id": metadata["document_id"],
            "page_number": metadata["page_number"],
            "text": text,
            "distance": distance,
        }
        for metadata, text, distance in zip(
            result["metadatas"][0], result["documents"][0], result["distances"][0]
        )
    ]


def delete_document(document_id):
    """Remove all of a document's chunks from the vector store."""
    _get_collection().delete(where={"document_id": document_id})
