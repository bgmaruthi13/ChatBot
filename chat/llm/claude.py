from django.conf import settings

from .base import CONCISE_INSTRUCTION, LLMProvider

DEFAULT_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = (
    "Answer the question using only the provided document excerpts. "
    "Cite page numbers inline (e.g. \"(page 3)\"). If the excerpts don't "
    "contain the answer, say so plainly instead of guessing. "
    f"{CONCISE_INSTRUCTION}"
)


class ClaudeProvider(LLMProvider):
    def __init__(self):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._model = getattr(settings, "ANTHROPIC_MODEL", None) or DEFAULT_MODEL

    def generate(self, question, chunks):
        if not chunks:
            return "I couldn't find anything in this document relevant to that question."

        context = "\n\n".join(f"[Page {c['page_number']}]\n{c['text']}" for c in chunks)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=200,  # ~100 words + headroom; SYSTEM_PROMPT sets the real target
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Document excerpts:\n\n{context}\n\nQuestion: {question}",
                }
            ],
        )
        return response.content[0].text
