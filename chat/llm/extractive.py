import re

import numpy as np

from vectorstore.embedding import embed, embed_many

from .base import LLMProvider

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
MIN_SENTENCE_LENGTH = 15


class ExtractiveProvider(LLMProvider):
    """Default provider - no API key, no external call, no generative
    model. Still a real, working answer mode (not a placeholder): it
    splits the retrieved chunks into sentences, ranks them by semantic
    similarity to the question (reusing the same embedding model as
    retrieval), and returns the handful of best-matching sentences with
    page citations - noticeably more readable than dumping whole raw
    chunks, without needing an LLM.
    """

    MAX_SENTENCES = 4

    def generate(self, question, chunks):
        if not chunks:
            return (
                "I couldn't find anything in this document relevant to "
                f'"{question}".'
            )

        candidates = self._candidate_sentences(chunks)
        if not candidates:
            return (
                "I found some matching pages, but couldn't pull a clear "
                f'answer to "{question}" out of them.'
            )

        top = self._rank_sentences(question, candidates)

        parts = [f'Based on the document, here\'s what I found about "{question}":\n']
        for sentence, page_number in top:
            parts.append(f"\n- {sentence} (page {page_number})")
        return "".join(parts)

    def _candidate_sentences(self, chunks):
        candidates = []
        seen = set()
        for chunk in chunks:
            for raw in SENTENCE_SPLIT_RE.split(chunk["text"]):
                sentence = raw.strip()
                if len(sentence) < MIN_SENTENCE_LENGTH or not self._looks_complete(sentence):
                    continue
                key = sentence.lower()
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((sentence, chunk["page_number"]))
        return candidates

    @staticmethod
    def _looks_complete(sentence):
        """Word-based chunking (documents/services.py chunk_text) can cut
        a chunk mid-sentence at its edges. Rather than surface a garbled
        fragment like "...escape the", only keep sentences that read like
        real, complete ones: starts capitalized, ends with terminal
        punctuation.
        """
        if sentence[-1] not in ".!?":
            return False
        first = sentence[0]
        return first.isupper() or first.isdigit() or first in "\"'“("

    def _rank_sentences(self, question, candidates):
        question_vector = np.array(embed(question))
        sentence_vectors = np.array(embed_many([sentence for sentence, _ in candidates]))

        question_unit = question_vector / np.linalg.norm(question_vector)
        sentence_units = sentence_vectors / np.linalg.norm(sentence_vectors, axis=1, keepdims=True)
        scores = sentence_units @ question_unit

        ranked = sorted(zip(candidates, scores), key=lambda pair: -pair[1])
        return [candidate for candidate, _ in ranked[: self.MAX_SENTENCES]]
