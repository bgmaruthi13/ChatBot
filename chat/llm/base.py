from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """A chat answer generator. `chunks` is the list of dicts returned by
    chat.services.retrieve() (chunk_id, document_id, page_number, text,
    distance), nearest-first.
    """

    @abstractmethod
    def generate(self, question, chunks):
        """Return an answer string built from `question` and `chunks`."""
        raise NotImplementedError
