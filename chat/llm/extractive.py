import re

import numpy as np

from vectorstore.embedding import embed, embed_many

from .base import LLMProvider

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
MIN_SENTENCE_LENGTH = 15


class ExtractiveProvider(LLMProvider):
    """Default provider - no API key, no external call, no generative
    model. Still a real, working answer mode (not a placeholder): shows
    the full text of every retrieved chunk that's actually relevant to
    the question, each under its own page citation, in relevance order.
    Irrelevant chunks (vector search always returns top_k results even
    when nothing matches well) and near-duplicate chunks (from
    chunk_text's overlapping windows) are filtered out - everything else
    found is shown as-is, unsummarized, until a real LLM is configured
    (Epic 9: LLM_PROVIDER=claude/openai/ollama) to condense it instead.
    """

    # Cosine similarity floor (all-MiniLM-L6-v2, question vs. sentence).
    # Calibrated empirically: genuinely relevant sentences score ~0.6-0.9,
    # unrelated filler scores ~0.2-0.35. Below this, a chunk is "in the
    # top-k nearest neighbors" but not actually relevant - vector search
    # always returns top_k results even when nothing matches well, so
    # this stops those weak matches showing up as if they were useful.
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
        seen_texts = []
        for chunk, _sentences, _best_index, score in ranked:
            if score < self.MIN_SCORE:
                break  # ranked best-first, so nothing after this clears the bar either

            text = chunk["text"]

            # Overlapping chunks (chunk_text's 150-word stride overlap)
            # can both be relevant to the same question and largely
            # repeat each other. Skip repeats rather than showing the
            # same content twice.
            if self._is_duplicate(text, seen_texts):
                continue

            parts.append(f"\n\nFrom page {chunk['page_number']}:\n{text}")
            used_chunk_ids.append(chunk["chunk_id"])
            seen_texts.append(text)

        if not used_chunk_ids:
            return (
                "I found some matching pages, but couldn't pull a clear "
                f'answer to "{question}" out of them.',
                [],
            )

        return "".join(parts), used_chunk_ids

    @staticmethod
    def _is_duplicate(text, seen_texts, threshold=0.7):
        words = set(text.lower().split())
        for seen in seen_texts:
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
        and score, used to rank/filter chunks by relevance. Returns
        [(chunk, sentences, best_index, score), ...] sorted best-first.
        Embeds every candidate sentence in one batch call.
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
