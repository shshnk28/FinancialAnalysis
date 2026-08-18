from functools import cached_property

from ingestion.config.embedder_profile import ACTIVE_PROFILE, EmbedderProfile
from ingestion.interfaces.embedder import Embedder

# Chunks per forward pass (§3f) — throughput/memory only; no effect on the vectors.
BATCH_SIZE = 32


class SentenceTransformerEmbedder(Embedder):
    """Phase 2 dense embedder (§3f): the profile's model via sentence-transformers,
    run locally on CPU. Model config comes from the active EmbedderProfile — never
    hardcoded here (§3a)."""

    def __init__(self, profile: EmbedderProfile = ACTIVE_PROFILE) -> None:
        super().__init__(profile)

    @cached_property
    def _model(self):
        # Lazy: the ~420MB model loads/downloads on first embed, not at construction.
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.profile.model_id, device="cpu")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,  # unit vectors (§3f); pairs with cosine (§3e)
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
