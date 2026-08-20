import tiktoken

from common.config.llm_config import LLMConfig
from common.models import TableGrid
from ingestion.extraction.token_counting import ENCODING_NAME, count_table_tokens, estimate_output_tokens


def test_count_table_tokens_matches_manual_tiktoken_count():
    config = LLMConfig(prompt_template="Summarize:\n\n")
    table = TableGrid(table_id="r:1:1", page=1, markdown="| a | b |\n| --- | --- |\n| 1 | 2 |")

    [count] = count_table_tokens([table], config)

    encoding = tiktoken.get_encoding(ENCODING_NAME)
    expected = len(encoding.encode(config.prompt_template + table.markdown))
    assert count == expected


def test_count_table_tokens_returns_one_count_per_table_in_order():
    config = LLMConfig()
    tables = [
        TableGrid(table_id="r:1:1", page=1, markdown="short"),
        TableGrid(table_id="r:2:1", page=2, markdown="a much longer table markdown string here"),
    ]
    counts = count_table_tokens(tables, config)
    assert len(counts) == 2
    assert counts[1] > counts[0]


def test_estimate_output_tokens_is_table_count_times_cap():
    config = LLMConfig(max_output_tokens=150)
    tables = [TableGrid(table_id=f"r:{i}:1", page=i, markdown="x") for i in range(4)]
    assert estimate_output_tokens(tables, config) == 4 * 150


def test_estimate_output_tokens_zero_for_no_tables():
    assert estimate_output_tokens([], LLMConfig()) == 0
