import threading

from django.conf import settings

from .base import CONCISE_INSTRUCTION, LLMProvider

# Runs entirely in-process via Hugging Face transformers (already a
# dependency of sentence-transformers/the embedding pipeline) - no
# Ollama, no separate server, no system-level installer. First use
# downloads the weights to the HF cache (same place the embedding
# model lives); every run after that is fully offline.
DEFAULT_MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"

SYSTEM_PROMPT = (
    "Answer the question using only the provided document excerpts. "
    "Cite page numbers inline (e.g. \"(page 3)\"). If the excerpts don't "
    "contain the answer, say so plainly instead of guessing. "
    f"{CONCISE_INSTRUCTION}"
)

# SmolLM2-135M-Instruct's context window is 8192 tokens - but with real
# retrieved chunks (chat.services.retrieve() returns up to 5, each up to
# ~800 words), the excerpts alone can exceed that (hit 12k+ tokens in
# testing, which hangs/errors mid-generation rather than failing
# cleanly). Capped by characters on the *context string itself*, before
# it's placed in the prompt - not by post-hoc tokenizer truncation,
# which would risk silently cutting off the question if it ever landed
# after the excerpts in the truncated tail.
MAX_CONTEXT_CHARS = 2000

_model = None
_tokenizer = None
_model_lock = threading.Lock()


def _get_model_and_tokenizer(model_name):
    global _model, _tokenizer
    if _model is None:
        with _model_lock:
            if _model is None:
                from transformers import AutoModelForCausalLM, AutoTokenizer

                _tokenizer = AutoTokenizer.from_pretrained(model_name)
                _model = AutoModelForCausalLM.from_pretrained(model_name)
    return _model, _tokenizer


class SmolLMProvider(LLMProvider):
    """No Ollama, no API key - a small instruction-tuned model
    (SmolLM2-135M-Instruct by default) loaded directly via transformers
    and run in-process. Smallest/weakest of this app's generative
    options (see chat/llm/ollama.py's docstring-adjacent comparison) -
    picked here specifically to avoid installing separate LLM runtime
    software, not for answer quality.
    """

    def __init__(self):
        self._model_name = getattr(settings, "SMOLLM_MODEL", None) or DEFAULT_MODEL

    def generate(self, question, chunks):
        if not chunks:
            return "I couldn't find anything in this document relevant to that question."

        model, tokenizer = _get_model_and_tokenizer(self._model_name)

        context = "\n\n".join(f"[Page {c['page_number']}]\n{c['text']}" for c in chunks)
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "..."
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Document excerpts:\n\n{context}\n\nQuestion: {question}",
            },
        ]

        # return_dict=True: apply_chat_template returns a BatchEncoding
        # (dict-like: input_ids, attention_mask, ...), not a bare
        # tensor, on this transformers version - passing **inputs to
        # generate() is the version-robust way to feed it in.
        inputs = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
        )
        output = model.generate(
            **inputs,
            max_new_tokens=200,  # ~100 words + headroom
            pad_token_id=tokenizer.eos_token_id,
            # Greedy/deterministic: sampling let this model "creatively"
            # fabricate details not in the source text (observed: made
            # up dates, payload contents, speeds, none in the document).
            # Greedy decoding keeps a model this small anchored to the
            # given context instead of drifting into invented content.
            do_sample=False,
            no_repeat_ngram_size=3,
        )
        generated = output[0][inputs["input_ids"].shape[-1]:]
        return tokenizer.decode(generated, skip_special_tokens=True).strip()
