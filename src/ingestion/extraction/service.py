"""Reusable Phase-1 orchestration.

This is the single code path for the free/local scan, shared by BOTH the CLI
(`ingest-phase1`) and the REST API (Step 1). It performs extraction → chunking →
token counting → manifest assembly → manifest persistence, and returns the
manifest plus the path it was written to. It does NOT print — presentation
(the consent summary, next-step hints) belongs to the caller.

Phase boundary (§1): everything here is free and local — no embedding, no
Qdrant, no LLM calls.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from ingestion.extraction.chunking import chunk_prose
from common.config.embedder_profile import ACTIVE_PROFILE
from common.config.llm_config import DEFAULT_LLM_CONFIG
from ingestion.extraction.pdf import scan_pdf
from common.manifest import build_manifest
from common.models import IngestionManifest
from ingestion.extraction.report_id import compute_report_id
from ingestion.extraction.token_counting import count_table_tokens, estimate_output_tokens

DEFAULT_MANIFEST_DIR = Path("manifests")


def run_phase1_scan(
    pdf_path: Path,
    company: str,
    period: str,
    report_id: Optional[str] = None,
    out_dir: Path = DEFAULT_MANIFEST_DIR,
    out_path: Optional[Path] = None,
) -> tuple[IngestionManifest, Path]:
    """Scan a PDF into an IngestionManifest and persist it as JSON.

    Args:
        pdf_path: annual-report PDF to scan.
        company / period: user-provided document identity (retrieval metadata).
        report_id: override the content-hash-derived report_id.
        out_dir: directory for the default ``<report_id>.json`` manifest path.
        out_path: explicit manifest path; overrides ``out_dir`` when given.

    Returns:
        (manifest, manifest_path) — the durable §1a handoff artifact Phase 2 consumes.
    """
    pdf_path = Path(pdf_path)
    report_id = report_id or compute_report_id(pdf_path)

    extraction = scan_pdf(pdf_path, report_id)
    chunks = chunk_prose(extraction.pages, ACTIVE_PROFILE, report_id)
    table_tokens = count_table_tokens(extraction.tables, DEFAULT_LLM_CONFIG)
    est_output_tokens = estimate_output_tokens(extraction.tables, DEFAULT_LLM_CONFIG)

    manifest = build_manifest(
        document_name=extraction.document_name,
        company=company,
        period=period,
        page_count=extraction.page_count,
        prose_chunks=chunks,
        tables=extraction.tables,
        skipped_visuals=extraction.skipped_visuals,
        table_input_tokens=table_tokens,
        est_output_tokens=est_output_tokens,
    )

    # Phase 1 always persists the manifest — it is the durable handoff to Phase 2 (§1a).
    manifest_path = out_path or (out_dir / f"{report_id}.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(asdict(manifest), indent=2))

    return manifest, manifest_path
