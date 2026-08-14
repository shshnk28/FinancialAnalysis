import dataclasses

import pytest

from ingestion.config.llm_config import DEFAULT_LLM_CONFIG, LLMConfig


def test_default_llm_config_matches_frozen_spec():
    assert DEFAULT_LLM_CONFIG.provider == "openai"
    assert DEFAULT_LLM_CONFIG.max_output_tokens == 150


def test_llm_config_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULT_LLM_CONFIG.max_output_tokens = 999


def test_custom_llm_config_overrides_defaults():
    config = LLMConfig(max_output_tokens=50)
    assert config.max_output_tokens == 50
    assert config.provider == "openai"  # other fields keep their defaults
