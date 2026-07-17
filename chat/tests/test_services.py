import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from chat.services import retrieve
from documents.models import Document
from documents.services import delete_document_vectors, process_document
from vectorstore.embedding import embed

FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "documents", "tests", "fixtures"
)


class EmbeddingDeterminismTests(TestCase):
    def test_same_text_yields_identical_vectors(self):
        v1 = embed("hello world")
        v2 = embed("hello world")
        self.assertEqual(v1, v2)

    def test_different_text_yields_different_vectors(self):
        v1 = embed("cats are small domesticated mammals")
        v2 = embed("rocket engines burn propellant for thrust")
        self.assertNotEqual(v1, v2)


class RetrieveRelevanceTests(TestCase):
    def setUp(self):
        path = os.path.join(FIXTURES_DIR, "sample_topics.pdf")
        with open(path, "rb") as f:
            upload = SimpleUploadedFile(
                "sample_topics.pdf", f.read(), content_type="application/pdf"
            )
        self.document = Document.objects.create(
            title="sample_topics.pdf", file=upload, status=Document.Status.PENDING
        )
        process_document(self.document)
        self.document.refresh_from_db()

    def tearDown(self):
        delete_document_vectors(self.document.pk)
        self.document.file.delete(save=False)
        self.document.delete()

    def test_document_processed_successfully(self):
        self.assertEqual(self.document.status, Document.Status.READY)
        self.assertGreater(self.document.chunks.count(), 0)

    def test_retrieve_returns_topically_relevant_chunk(self):
        rocket_results = retrieve(
            "rocket engines burn propellant for thrust", document_id=self.document.pk, top_k=1
        )
        self.assertIn("rocket", rocket_results[0]["text"].lower())

        cats_results = retrieve(
            "cats are small domesticated mammals", document_id=self.document.pk, top_k=1
        )
        self.assertIn("cat", cats_results[0]["text"].lower())

    def test_retrieve_scopes_to_given_document(self):
        results = retrieve("anything", document_id=999999, top_k=5)
        self.assertEqual(results, [])
