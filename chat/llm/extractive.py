import re

import numpy as np

from vectorstore.embedding import embed, embed_many

from .base import LLMProvider

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
MIN_SENTENCE_LENGTH = 15


class ExtractiveProvider(LLMProvider):
    """Default provider - no API key, no external call, no generative
    model. Still a real, working answer mode (not a placeholder): for
    each retrieved chunk, it finds the best-matching sentence (by
    semantic similarity to the question, same embedding model as
    retrieval) and returns that sentence plus its immediate neighbors in
    their original order - a short, coherent excerpt per source, not a
    scattershot of disconnected sentences pulled from all over the
    document. Limited to the strongest couple of sources so the answer
    reads like a focused explanation rather than a wall of citations.
    """

    MAX_SOURCES = 2
    SENTENCES_BEFORE = 1
    SENTENCES_AFTER = 1

    # Cosine similarity floor (all-MiniLM-L6-v2, question vs. sentence).
    # Calibrated empirically: genuinely relevant sentences score ~0.6-0.9,
    # unrelated filler scores ~0.2-0.35. Below this, a chunk is "in the
    # top-k nearest neighbors" but not actually relevant - vector search
    # always returns top_k results even when nothing matches well, so
    # this stops those weak matches from padding out the answer.
    MIN_SCORE = 0.4

    def generate(self, question, chunks):
        if not chunks:
            return (
                "I couldn't find anything in this document relevant to "
                f'"{question}".',
                [],
            )

        chunk_sentences = self._split_chunks(chunks)
        if not chunk_sentences:
            return (
                "I found some matching pages, but couldn't pull a clear "
                f'answer to "{question}" out of them.',
                [],
            )

        ranked = self._rank_chunks(question, chunk_sentences)

        parts = [f'Based on the document, here\'s what I found about "{question}":']
        used_chunk_ids = []
        seen_excerpts = []
        for chunk, sentences, best_index, score in ranked:
            if len(used_chunk_ids) >= self.MAX_SOURCES:
                break
            if score < self.MIN_SCORE:
                break  # ranked best-first, so nothing after this clears the bar either

            start = max(0, best_index - self.SENTENCES_BEFORE)
            end = min(len(sentences), best_index + self.SENTENCES_AFTER + 1)
            excerpt = " ".join(sentences[start:end])

            # Overlapping chunks (chunk_text's 150-word stride overlap)
            # can independently rank as top sources for the same
            # question and yield near-duplicate excerpts. Skip repeats
            # rather than showing the same content twice.
            if self._is_duplicate(excerpt, seen_excerpts):
                continue

            parts.append(f"\n\nFrom page {chunk['page_number']}:\n{excerpt}")
            used_chunk_ids.append(chunk["chunk_id"])
            seen_excerpts.append(excerpt)

        if not used_chunk_ids:
            return (
                "I found some matching pages, but couldn't pull a clear "
                f'answer to "{question}" out of them.',
                [],
            )

        return "".join(parts), used_chunk_ids

    @staticmethod
    def _is_duplicate(excerpt, seen_excerpts, threshold=0.7):
        words = set(excerpt.lower().split())
        for seen in seen_excerpts:
            seen_words = set(seen.lower().split())
            if not words or not seen_words:
                continue
            overlap = len(words & seen_words) / min(len(words), len(seen_words))
            if overlap >= threshold:
                return True
        return False

    def _split_chunks(self, chunks):
        """Return [(chunk, [sentence, ...]), ...], skipping chunks with
        no usable sentences.
        """
        result = []
        for chunk in chunks:
            sentences = [
                s.strip() for s in SENTENCE_SPLIT_RE.split(chunk["text"]) if len(s.strip()) >= MIN_SENTENCE_LENGTH
            ]
            if sentences:
                result.append((chunk, sentences))
        return result

    def _rank_chunks(self, question, chunk_sentences):
        """For each (chunk, sentences), find its best-matching sentence
        and score. Returns [(chunk, sentences, best_index, score), ...]
        sorted best-first. Embeds every candidate sentence in one batch
        call.
        """
        question_vector = np.array(embed(question))
        question_unit = question_vector / np.linalg.norm(question_vector)

        all_sentences = [s for _, sentences in chunk_sentences for s in sentences]
        all_vectors = np.array(embed_many(all_sentences))
        all_units = all_vectors / np.linalg.norm(all_vectors, axis=1, keepdims=True)
        all_scores = all_units @ question_unit

        ranked = []
        offset = 0
        for chunk, sentences in chunk_sentences:
            scores = all_scores[offset : offset + len(sentences)]
            offset += len(sentences)
            best_index = int(np.argmax(scores))
            ranked.append((chunk, sentences, best_index, float(scores[best_index])))

        ranked.sort(key=lambda item: -item[3])
        return ranked
