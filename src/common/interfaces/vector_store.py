from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class VectorRecord:
    vector: list[float]
    content: str
    metadata: dict[str, Any]


class VectorStore(ABC):
    """Phase 2 only. Not called in Phase 1."""

    @abstractmethod
    def index(self, records: list[VectorRecord]) -> None:
        raise NotImplementedError
