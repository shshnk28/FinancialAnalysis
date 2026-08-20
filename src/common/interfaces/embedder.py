from abc import ABC, abstractmethod

from common.config.embedder_profile import EmbedderProfile


class Embedder(ABC):
    """Phase 2 only. Not called in Phase 1."""

    def __init__(self, profile: EmbedderProfile) -> None:
        self.profile = profile

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError
