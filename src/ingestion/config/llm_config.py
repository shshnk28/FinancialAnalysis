from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "openai"
    max_output_tokens: int = 150
    prompt_template: str = "Summarize the following financial table concisely:\n\n"


DEFAULT_LLM_CONFIG = LLMConfig()
