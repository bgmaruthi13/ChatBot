import os

from django.test import TestCase

from documents.services import (
    CHUNK_OVERLAP_WORDS,
    CHUNK_SIZE_WORDS,
    chunk_text,
    extract_text_from_path,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class ExtractTextTests(TestCase):
    def test_extracts_non_empty_text_per_page_in_order(self):
        pages = extract_text_from_path(os.path.join(FIXTURES_DIR, "sample_text.pdf"))

        self.assertEqual(len(pages), 3)
        for _, text in pages:
            self.assertTrue(text.strip())
        self.assertIn("Page one", pages[0][1])
        self.assertIn("Page two", pages[1][1])
        self.assertIn("Page three", pages[2][1])

    def test_corrupted_pdf_raises(self):
        with self.assertRaises(Exception):
            extract_text_from_path(os.path.join(FIXTURES_DIR, "sample_corrupted.pdf"))

    def test_password_protected_pdf_raises(self):
        with self.assertRaises(Exception):
            extract_text_from_path(os.path.join(FIXTURES_DIR, "sample_locked.pdf"))


class ChunkTextTests(TestCase):
    def test_reconstruction_matches_source_and_respects_max_size(self):
        words = [f"word{i:05d}" for i in range(2000)]
        pages = [
            (1, " ".join(words[0:700])),
            (2, " ".join(words[700:1400])),
            (3, " ".join(words[1400:2000])),
        ]

        chunks = chunk_text(pages)

        for chunk in chunks:
            self.assertLessEqual(len(chunk["text"].split()), CHUNK_SIZE_WORDS)

        reconstructed = chunks[0]["text"].split()
        for chunk in chunks[1:]:
            reconstructed.extend(chunk["text"].split()[CHUNK_OVERLAP_WORDS:])
        self.assertEqual(reconstructed, words)

    def test_chunk_indices_are_sequential(self):
        pages = [(1, " ".join(f"w{i}" for i in range(2000)))]
        chunks = chunk_text(pages)
        self.assertEqual([c["chunk_index"] for c in chunks], list(range(len(chunks))))

    def test_no_text_returns_no_chunks(self):
        self.assertEqual(chunk_text([(1, "")]), [])
        self.assertEqual(chunk_text([]), [])
