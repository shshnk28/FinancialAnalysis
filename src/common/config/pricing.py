# PLACEHOLDER pricing — not yet confirmed against current OpenAI rates.
# Phase 2 will pin an actual summarization model; until then, Phase 1's cost
# estimate brackets between a named "cheap" and "expensive" tier so the
# consent report shows a defensible range rather than a single guessed number.
from dataclasses import dataclass


@dataclass(frozen=True)
class PricingTier:
    name: str
    input_usd_per_million_tokens: float
    output_usd_per_million_tokens: float


CHEAP_TIER = PricingTier(
    name="gpt-4o-mini (placeholder)",
    input_usd_per_million_tokens=0.15,
    output_usd_per_million_tokens=0.60,
)

EXPENSIVE_TIER = PricingTier(
    name="gpt-4o (placeholder)",
    input_usd_per_million_tokens=2.50,
    output_usd_per_million_tokens=10.00,
)
