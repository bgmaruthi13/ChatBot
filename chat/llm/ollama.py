import requests
from django.conf import settings

from .base import LLMProvider

DEFAULT_MODEL = "llama3.2"

SYSTEM_PROMPT = (
    "Answer the question using only the provided document excerpts. "
    "Cite page numbers inline (e.g. \"(page 3)\"). If the excerpts don't "
    "contain the answer, say so plainly instead of guessing."
)


class OllamaProvider(LLMProvider):
    """No API key required - talks to a local Ollama server over HTTP.
    Fully offline generative option. If the server isn't reachable,
    generate() raises requests' own clear connection error rather than
    hanging or failing silently.
    """

    def __init__(self):
        self._base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = getattr(settings, "OLLAMA_MODEL", None) or DEFAULT_MODEL

    def generate(self, question, chunks):
        if not chunks:
            return "I couldn't find anything in this document relevant to that question."

        context = "\n\n".join(f"[Page {c['page_number']}]\n{c['text']}" for c in chunks)
        prompt = f"{SYSTEM_PROMPT}\n\nDocument excerpts:\n\n{context}\n\nQuestion: {question}"

        response = requests.post(
            f"{self._base_url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["response"]
