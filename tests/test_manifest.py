from common.config.pricing import CHEAP_TIER, EXPENSIVE_TIER
from common.manifest import build_manifest, estimate_cost
from common.models import Chunk, SkippedVisual, TableGrid


def test_estimate_cost_arithmetic():
    table_tokens = [1_000_000, 1_000_000]  # 2M input tokens exactly
    est_output_tokens = 1_000_000

    cost = estimate_cost(table_tokens, est_output_tokens)

    assert cost.table_input_tokens_total == 2_000_000
    assert cost.est_output_tokens_total == 1_000_000
    assert cost.input_cost_usd == 2 * CHEAP_TIER.input_usd_per_million_tokens
    assert cost.output_cost_usd_min == CHEAP_TIER.output_usd_per_million_tokens
    assert cost.output_cost_usd_max == EXPENSIVE_TIER.output_usd_per_million_tokens
    assert cost.total_cost_usd_min == cost.input_cost_usd + cost.output_cost_usd_min
    assert cost.total_cost_usd_max == cost.input_cost_usd + cost.output_cost_usd_max
    assert cost.total_cost_usd_min <= cost.total_cost_usd_max


def test_estimate_cost_zero_tables():
    cost = estimate_cost([], 0)
    assert cost.table_input_tokens_total == 0
    assert cost.input_cost_usd == 0
    assert cost.total_cost_usd_min == 0
    assert cost.total_cost_usd_max == 0


def test_estimate_cost_note_is_flagged_as_placeholder():
    cost = estimate_cost([100], 150)
    assert "PLACEHOLDER" in cost.pricing_note


def test_build_manifest_assembles_all_contract_fields():
    chunks = [Chunk(chunk_id="r:1:0", text="hi", page=1, section=None, token_count=1)]
    tables = [TableGrid(table_id="r:2:1", page=2, markdown="| a |\n| --- |\n| 1 |")]
    skipped = [SkippedVisual(page=1, visual_type="image", width=10, height=10)]
    table_tokens = [42]

    manifest = build_manifest(
        document_name="report.pdf",
        company="Eternal Ltd",
        period="FY2026",
        page_count=2,
        prose_chunks=chunks,
        tables=tables,
        skipped_visuals=skipped,
        table_input_tokens=table_tokens,
        est_output_tokens=150,
    )

    assert manifest.document_name == "report.pdf"
    assert manifest.company == "Eternal Ltd"
    assert manifest.period == "FY2026"
    assert manifest.page_count == 2
    assert manifest.prose_chunks == chunks
    assert manifest.tables == tables
    assert manifest.skipped_visuals == skipped
    assert manifest.table_input_tokens == table_tokens
    assert manifest.est_output_tokens == 150
    assert manifest.cost_estimate is not None
    assert manifest.cost_estimate.table_input_tokens_total == 42

    # Phase 1 must never populate embeddings or table summaries (§1/§5).
    assert not hasattr(manifest, "embeddings")
    assert not any(hasattr(t, "summary") for t in manifest.tables)
