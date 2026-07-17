import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from chat.llm.extractive import ExtractiveProvider
from chat.models import ChatSession
from chat.services import ask
from documents.models import Document
from documents.services import delete_document_vectors, process_document

FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "documents", "tests", "fixtures"
)


class ExtractiveProviderTests(TestCase):
    """Unit-level: feeds synthetic chunk dicts directly, no document
    pipeline needed. Locks in the behavior fixed after a real user
    reported the old sentence-scattering output as unreadable.
    """

    def setUp(self):
        self.provider = ExtractiveProvider()

    def test_no_chunks_returns_fallback_and_no_citations(self):
        answer, used = self.provider.generate("anything", [])
        self.assertIn("couldn't find anything", answer)
        self.assertEqual(used, [])

    def test_groups_relevant_content_and_drops_irrelevant_chunk(self):
        relevant = {
            "chunk_id": 1,
            "document_id": 1,
            "page_number": 7,
            "text": (
                "Chapter 5: Post-Installation Steps. "
                "1. Run the SunSystems installer. "
                "2. Select Install SunSystems software. "
                "3. Follow the on-screen instructions to complete setup."
            ),
        }
        irrelevant = {
            "chunk_id": 2,
            "document_id": 1,
            "page_number": 13,
            "text": (
                "This section describes configuration options that do not "
                "affect installation directly and are covered here for "
                "completeness only. Contact support for further details."
            ),
        }

        answer, used = self.provider.generate(
            "How to install sunsystems?", [relevant, irrelevant]
        )

        self.assertIn("Run the SunSystems installer", answer)
        self.assertIn("page 7", answer)
        # The unrelated chunk should be filtered by the relevance floor,
        # not padded in just to fill MAX_SOURCES.
        self.assertEqual(used, [1])
        # Citations returned must match exactly what's shown in the text.
        self.assertEqual(answer.count("From page"), len(used))

    def test_deduplicates_near_identical_excerpts_from_overlapping_chunks(self):
        shared_text = (
            "Chapter 5: Post-Installation Steps. "
            "1. Run the SunSystems installer. "
            "2. Select Install SunSystems software."
        )
        chunks = [
            {"chunk_id": 1, "document_id": 1, "page_number": 6, "text": shared_text},
            {"chunk_id": 2, "document_id": 1, "page_number": 7, "text": shared_text},
        ]

        answer, used = self.provider.generate("How to install sunsystems?", chunks)

        self.assertEqual(len(used), 1)
        self.assertEqual(answer.count("From page"), 1)


class AskCitationMatchingTests(TestCase):
    """Integration-level: chat.services.ask() must record only the
    chunks the provider actually used, not every chunk retrieve()
    fetched - otherwise the UI's citation footer lists pages that don't
    appear anywhere in the visible answer.
    """

    def setUp(self):
        path = os.path.join(FIXTURES_DIR, "sample_install_guide.pdf")
        with open(path, "rb") as f:
            upload = SimpleUploadedFile(
                "sample_install_guide.pdf", f.read(), content_type="application/pdf"
            )
        self.document = Document.objects.create(
            title="sample_install_guide.pdf", file=upload, status=Document.Status.PENDING
        )
        process_document(self.document)
        self.document.refresh_from_db()
        self.session = ChatSession.objects.create(document=self.document)

    def tearDown(self):
        delete_document_vectors(self.document.pk)
        self.document.file.delete(save=False)
        self.document.delete()

    def test_citations_match_pages_shown_in_answer(self):
        message = ask("How to install sunsystems?", self.document.pk, self.session)

        cited_pages = {str(c["page_number"]) for c in message.source_chunks}
        for page in cited_pages:
            self.assertIn(f"page {page}", message.content)

        # every "From page N:" in the text must have a matching citation
        self.assertEqual(message.content.count("From page"), len(message.source_chunks))
