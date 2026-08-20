import tiktoken

from common.config.llm_config import LLMConfig
from common.models import TableGrid

# Flagged default: no specific OpenAI model is pinned yet (Phase 2 decision).
# o200k_base is the current-generation encoding; swap once Phase 2 picks a model.
ENCODING_NAME = "o200k_base"


def count_table_tokens(tables: list[TableGrid], llm_config: LLMConfig) -> list[int]:
    encoding = tiktoken.get_encoding(ENCODING_NAME)
    return [len(encoding.encode(llm_config.prompt_template + table.markdown)) for table in tables]


def estimate_output_tokens(tables: list[TableGrid], llm_config: LLMConfig) -> int:
    return len(tables) * llm_config.max_output_tokens
