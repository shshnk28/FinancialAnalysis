from ingestion.config.pricing import CHEAP_TIER, EXPENSIVE_TIER
from ingestion.models import Chunk, CostEstimate, IngestionManifest, SkippedVisual, TableGrid


def estimate_cost(table_tokens: list[int], est_output_tokens: int) -> CostEstimate:
    input_tokens_total = sum(table_tokens)
    input_cost = input_tokens_total / 1_000_000 * CHEAP_TIER.input_usd_per_million_tokens
    output_cost_min = est_output_tokens / 1_000_000 * CHEAP_TIER.output_usd_per_million_tokens
    output_cost_max = est_output_tokens / 1_000_000 * EXPENSIVE_TIER.output_usd_per_million_tokens

    return CostEstimate(
        table_input_tokens_total=input_tokens_total,
        est_output_tokens_total=est_output_tokens,
        input_cost_usd=input_cost,
        output_cost_usd_min=output_cost_min,
        output_cost_usd_max=output_cost_max,
        total_cost_usd_min=input_cost + output_cost_min,
        total_cost_usd_max=input_cost + output_cost_max,
        pricing_note=(
            f"PLACEHOLDER pricing, not yet confirmed: input priced at {CHEAP_TIER.name} rate "
            f"(${CHEAP_TIER.input_usd_per_million_tokens}/M tokens); output bracketed between "
            f"{CHEAP_TIER.name} and {EXPENSIVE_TIER.name} output rates. Confirm real OpenAI "
            f"pricing before treating this as a trustworthy consent figure."
        ),
    )


def build_manifest(
    document_name: str,
    company: str,
    period: str,
    page_count: int,
    prose_chunks: list[Chunk],
    tables: list[TableGrid],
    skipped_visuals: list[SkippedVisual],
    table_input_tokens: list[int],
    est_output_tokens: int,
) -> IngestionManifest:
    return IngestionManifest(
        document_name=document_name,
        company=company,
        period=period,
        page_count=page_count,
        prose_chunks=prose_chunks,
        tables=tables,
        skipped_visuals=skipped_visuals,
        table_input_tokens=table_input_tokens,
        est_output_tokens=est_output_tokens,
        cost_estimate=estimate_cost(table_input_tokens, est_output_tokens),
    )


def print_consent_summary(manifest: IngestionManifest) -> None:
    ce = manifest.cost_estimate
    print()
    print("=" * 60)
    print("PHASE 1 SCAN COMPLETE — COST-CONSENT SUMMARY")
    print("=" * 60)
    print(f"Document: {manifest.document_name}")
    print(f"Company: {manifest.company}")
    print(f"Period: {manifest.period}")
    print(f"Pages: {manifest.page_count}")
    print(f"Prose chunks: {len(manifest.prose_chunks)}")
    print(f"Tables (real content): {len(manifest.tables)}")
    print(f"Skipped visuals (images/vector-graphics/blank-tables): {len(manifest.skipped_visuals)}")
    print(f"Exact table input tokens: {ce.table_input_tokens_total}")
    print(f"Capped table output tokens: {ce.est_output_tokens_total}")
    print(f"Estimated Phase 2 cost: ${ce.total_cost_usd_min:.4f} - ${ce.total_cost_usd_max:.4f}")
    print(f"  ({ce.pricing_note})")
    print()
    print("Phase 1 complete. No LLM or embedding calls made. Review the above before approving Phase 2.")
    print("=" * 60)
