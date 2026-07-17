from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """A chat answer generator. `chunks` is the list of dicts returned by
    chat.services.retrieve() (chunk_id, document_id, page_number, text,
    distance), nearest-first.
    """

    @abstractmethod
    def generate(self, question, chunks):
        """Return either:
        - an answer string (citations shown will be every retrieved
          chunk - reasonable for a generative provider that may draw on
          the full context even without quoting it), or
        - a (answer, used_chunk_ids) tuple, where used_chunk_ids is the
          subset of `chunks`' chunk_id values actually reflected in the
          answer, so the UI's citations match exactly what's shown.
        """
        raise NotImplementedError
