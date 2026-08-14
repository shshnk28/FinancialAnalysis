from abc import ABC, abstractmethod

from ingestion.config.llm_config import LLMConfig


class LLMClient(ABC):
    """Phase 2 only. Not called in Phase 1."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    def summarize(self, table_markdown: str) -> str:
        raise NotImplementedError
