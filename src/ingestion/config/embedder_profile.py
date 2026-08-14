from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class EmbedderProfile:
    name: str
    model_id: str
    max_input_tokens: int
    chunk_size: int
    overlap_ratio: float

    def __post_init__(self) -> None:
        assert self.chunk_size < self.max_input_tokens, "chunk_size must stay below max_input_tokens"
        assert 0.10 <= self.overlap_ratio < 0.5, "overlap_ratio must be in [0.10, 0.15], never >= 0.5"

    @property
    def overlap_tokens(self) -> int:
        return round(self.chunk_size * self.overlap_ratio)

    @property
    def tokenizer(self):
        return _load_tokenizer(self.model_id)


@lru_cache(maxsize=None)
def _load_tokenizer(model_id: str):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(model_id)


MPNET_PROFILE = EmbedderProfile(
    name="all-mpnet-base-v2",
    model_id="sentence-transformers/all-mpnet-base-v2",
    max_input_tokens=512,
    chunk_size=450,
    overlap_ratio=0.12,
)

ACTIVE_PROFILE = MPNET_PROFILE
