import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ingestion.chunking import chunk_prose
from ingestion.config.embedder_profile import ACTIVE_PROFILE
from ingestion.config.llm_config import DEFAULT_LLM_CONFIG
from ingestion.extraction import scan_pdf
from ingestion.manifest import build_manifest, print_consent_summary
from ingestion.report_id import compute_report_id
from ingestion.token_counting import count_table_tokens, estimate_output_tokens


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 ingestion scan (free, local only)")
    parser.add_argument("pdf_path", type=Path, help="Path to the annual-report PDF")
    parser.add_argument("--company", required=True, help="Company this report belongs to (retrieval metadata)")
    parser.add_argument("--period", required=True, help="Reporting period, e.g. FY2026 (retrieval metadata)")
    parser.add_argument("--report-id", default=None, help="Override auto-derived report_id")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Override the default manifest path (default: ./manifests/<report_id>.json)",
    )
    args = parser.parse_args()

    report_id = args.report_id or compute_report_id(args.pdf_path)

    extraction = scan_pdf(args.pdf_path, report_id)
    chunks = chunk_prose(extraction.pages, ACTIVE_PROFILE, report_id)
    table_tokens = count_table_tokens(extraction.tables, DEFAULT_LLM_CONFIG)
    est_output_tokens = estimate_output_tokens(extraction.tables, DEFAULT_LLM_CONFIG)

    manifest = build_manifest(
        document_name=extraction.document_name,
        company=args.company,
        period=args.period,
        page_count=extraction.page_count,
        prose_chunks=chunks,
        tables=extraction.tables,
        skipped_visuals=extraction.skipped_visuals,
        table_input_tokens=table_tokens,
        est_output_tokens=est_output_tokens,
    )

    print_consent_summary(manifest)

    # Phase 1 always persists the manifest — it is the durable handoff to Phase 2 (§1a).
    # Default location is deterministic (./manifests/<report_id>.json); --json-out overrides.
    out_path = args.json_out or Path("manifests") / f"{report_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(manifest), indent=2))
    print(f"Manifest written to {out_path}")
    print(f"Next (Phase 2, once built): review the summary above, then  ingest-phase2 {out_path}")


if __name__ == "__main__":
    main()
