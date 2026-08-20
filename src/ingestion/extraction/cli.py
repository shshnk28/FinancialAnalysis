import argparse
from pathlib import Path

from common.manifest import print_consent_summary
from ingestion.extraction.service import run_phase1_scan


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

    manifest, out_path = run_phase1_scan(
        pdf_path=args.pdf_path,
        company=args.company,
        period=args.period,
        report_id=args.report_id,
        out_path=args.json_out,
    )

    print_consent_summary(manifest)
    print(f"Manifest written to {out_path}")
    print(f"Next (Phase 2): review the summary above, then  ingest-phase2 {out_path}")


if __name__ == "__main__":
    main()
