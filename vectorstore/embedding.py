import threading

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(text):
    """Embed a single string. Returns a list[float]."""
    return _get_model().encode(text, convert_to_numpy=True).tolist()


def embed_many(texts):
    """Embed a batch of strings in one pass. Returns list[list[float]],
    same order as `texts`. Meaningfully faster than calling embed() per
    text - the model batches the forward pass instead of one at a time.
    """
    return _get_model().encode(list(texts), convert_to_numpy=True).tolist()
