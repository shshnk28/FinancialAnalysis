import math

from ingestion.embedding import SentenceTransformerEmbedder
from ingestion.interfaces.embedder import Embedder


def test_embedder_is_an_embedder():
    # Construction alone must not load the model (lazy) — just checks the type/wiring.
    assert isinstance(SentenceTransformerEmbedder(), Embedder)


def test_embedder_empty_input_returns_empty_without_loading_model():
    assert SentenceTransformerEmbedder().embed([]) == []


def test_embedder_returns_normalized_768d_vectors():
    # Real run: downloads/loads all-mpnet-base-v2 (~420MB) on first call, then caches.
    embedder = SentenceTransformerEmbedder()
    vectors = embedder.embed(["hello world", "consolidated financial statements"])

    assert len(vectors) == 2
    assert all(len(v) == 768 for v in vectors)  # all-mpnet-base-v2 dimensionality
    for v in vectors:
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-3  # normalize_embeddings=True → unit length
