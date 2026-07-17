from django.conf import settings

from .base import LLMProvider

DEFAULT_MODEL = "gpt-5"

SYSTEM_PROMPT = (
    "Answer the question using only the provided document excerpts. "
    "Cite page numbers inline (e.g. \"(page 3)\"). If the excerpts don't "
    "contain the answer, say so plainly instead of guessing."
)


class OpenAIProvider(LLMProvider):
    def __init__(self):
        import openai

        self._client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = getattr(settings, "OPENAI_MODEL", None) or DEFAULT_MODEL

    def generate(self, question, chunks):
        if not chunks:
            return "I couldn't find anything in this document relevant to that question."

        context = "\n\n".join(f"[Page {c['page_number']}]\n{c['text']}" for c in chunks)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Document excerpts:\n\n{context}\n\nQuestion: {question}",
                },
            ],
        )
        return response.choices[0].message.content
