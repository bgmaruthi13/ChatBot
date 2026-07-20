from abc import ABC, abstractmethod

# Shared by every generative provider's system prompt (claude/openai/
# ollama) so answers stay short regardless of which one is active.
# Paired with a matching output-token cap in each provider - the prompt
# instruction is the real control (a model asked for ~75 words rarely
# needs a hard stop), the token cap is just a backstop.
CONCISE_INSTRUCTION = "Keep your answer between 50 and 100 words."


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
