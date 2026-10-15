"""
Local embeddings, cache first.

The model is sentence-transformers/all-MiniLM-L6-v2 (384 dimensions, about
90 MB). No API key. Every text that ships with the workshop is also
pre-embedded in data/vector_cache.json, so the seed corpus, the attacks, and
the labeled set load in seconds even if the model never downloads. The model
is only needed for text you type yourself.

Portable: all of it. Nothing here knows about Weaviate.
"""

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from memory.connect import REPO_ROOT


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CACHE_PATH = REPO_ROOT / "data" / "vector_cache.json"

_cache: dict[str, list[float]] | None = None
_model = None


def model_name() -> str:
    return os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)


def _key(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:24]


def _load_cache() -> dict[str, list[float]]:
    global _cache
    if _cache is None:
        if CACHE_PATH.exists():
            with open(CACHE_PATH) as f:
                data = json.load(f)
            _cache = data.get("vectors", {}) if data.get("model") == model_name() else {}
        else:
            _cache = {}
    return _cache


def model_available() -> bool:
    try:
        _get_model()
        return True
    except Exception:  # noqa: BLE001
        return False


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(model_name())
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Cached vectors are returned as-is; the rest go through the model."""
    cache = _load_cache()
    out: list[list[float] | None] = [cache.get(_key(t)) for t in texts]
    missing = [i for i, v in enumerate(out) if v is None]
    if missing:
        try:
            model = _get_model()
        except Exception as exc:  # noqa: BLE001
            sample = texts[missing[0]][:60]
            raise RuntimeError(
                f"The embedding model could not load and this text is not in the cache: {sample!r}. "
                "Run `python setup.py` on a good connection, or stick to the shipped examples."
            ) from exc
        vectors = model.encode([texts[i] for i in missing], normalize_embeddings=True)
        for i, vec in zip(missing, vectors):
            out[i] = [float(x) for x in vec]
    return out  # type: ignore[return-value]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]


def cosine(a: list[float], b: list[float]) -> float:
    """Vectors are unit length, so cosine similarity is a dot product."""
    return float(np.dot(np.asarray(a), np.asarray(b)))


def build_cache(texts: list[str], path: Path = CACHE_PATH) -> int:
    """Embed every text with the model and write the cache file. Used by the repo, not in the room."""
    model = _get_model()
    unique = sorted({t.strip() for t in texts if t and t.strip()})
    vectors = model.encode(unique, normalize_embeddings=True, show_progress_bar=False)
    payload = {
        "model": model_name(),
        "dimensions": int(vectors.shape[1]),
        "vectors": {_key(t): [round(float(x), 6) for x in v] for t, v in zip(unique, vectors)},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f)
    global _cache
    _cache = None
    return len(unique)


def workshop_texts() -> list[str]:
    """Every text shipped with the workshop, so build_cache can cover them all."""
    data = REPO_ROOT / "data"
    texts: list[str] = []
    for name in ["seed_corpus.json", "attacks.json", "labeled_candidates.json"]:
        p = data / name
        if p.exists():
            with open(p) as f:
                items = json.load(f)
            texts += [item["text"] for item in items]
    p = data / "queries.json"
    if p.exists():
        with open(p) as f:
            texts += json.load(f)
    return texts


if __name__ == "__main__":
    n = build_cache(workshop_texts())
    print(f"Cached {n} vectors with {model_name()} at {CACHE_PATH}")
