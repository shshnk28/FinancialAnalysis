"""Phase 1 — free/local scan: PDF extraction, chunking, token counting, manifest.

Public surface re-exported for ergonomic imports (`from ingestion.extraction import
scan_pdf`). These pull no heavy deps (no torch/Qdrant) — Phase 1 stays free/local.
"""

from ingestion.extraction.pdf import PageExtraction, scan_pdf
from ingestion.extraction.service import run_phase1_scan

__all__ = ["PageExtraction", "scan_pdf", "run_phase1_scan"]
