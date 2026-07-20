import requests
from django.conf import settings

from .base import CONCISE_INSTRUCTION, LLMProvider

# llama3.2 (3B, ~2GB) - a good default for low-memory machines. Even
# smaller options (qwen2.5:1.5b, ~1GB; llama3.2:1b, ~1.3GB) work fine
# for this app's job (summarize supplied excerpts, not open-ended
# reasoning) - set OLLAMA_MODEL in .env to switch, no code change.
DEFAULT_MODEL = "llama3.2"

SYSTEM_PROMPT = (
    "Answer the question using only the provided document excerpts. "
    "Cite page numbers inline (e.g. \"(page 3)\"). If the excerpts don't "
    "contain the answer, say so plainly instead of guessing. "
    f"{CONCISE_INSTRUCTION}"
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
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 200},  # ~100 words + headroom
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["response"]
