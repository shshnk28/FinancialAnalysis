"""REST API over the ingestion pipeline (Step 1: the Phase-1 scan endpoint).

Transport over the SAME two-phase seam the CLI uses — it does not change the
pipeline. Phase 1 over HTTP is still free/local (no embedding, Qdrant, or LLM);
the consent gate (§1a) still governs Phase 2, now realized as a deliberate second
API call (Step 2).

Because a scan takes ~100s, `POST /phase1` returns a job id immediately and the
client polls `GET /jobs/{id}` for the cost-consent summary and the manifest
filename Phase 2 will consume.
"""

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from api.jobs import JobStore
from common.models import IngestionManifest
from ingestion.extraction.service import run_phase1_scan

app = FastAPI(
    title="Investment-Analysis Ingestion API",
    description="REST transport over the two-phase ingestion pipeline (Phase 1 scan is free/local).",
    version="0.1.0",
)

# One in-process store for now; swapped for an out-of-process queue in Step 2.
JOBS = JobStore()


# --- request / response models ---------------------------------------------


class Phase1Request(BaseModel):
    file_path: str = Field(..., description="Server-side path to the annual-report PDF")
    company: str = Field(..., description="Company this report belongs to (retrieval metadata)")
    period: str = Field(..., description="Reporting period, e.g. FY2026 (retrieval metadata)")
    report_id: Optional[str] = Field(None, description="Override the content-hash-derived report_id")


class JobCreated(BaseModel):
    job_id: str
    status: str = "registered"


class CostSummary(BaseModel):
    document_name: str
    company: str
    period: str
    page_count: int
    prose_chunks: int
    tables: int
    skipped_visuals: int
    table_input_tokens_total: int
    est_output_tokens_total: int
    total_cost_usd_min: float
    total_cost_usd_max: float
    pricing_note: str


class Phase1Result(BaseModel):
    report_id: str
    manifest_file: str
    cost_summary: CostSummary


class JobStatusResponse(BaseModel):
    job_id: str
    kind: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


# --- helpers ----------------------------------------------------------------


def _phase1_result(manifest: IngestionManifest, manifest_path: Path) -> dict[str, Any]:
    """Shape the manifest into the JSON result the status endpoint returns.

    Mirrors the numbers `print_consent_summary` shows the CLI user.
    """
    ce = manifest.cost_estimate
    report_id = manifest_path.stem  # API uses the default <report_id>.json naming
    summary = CostSummary(
        document_name=manifest.document_name,
        company=manifest.company,
        period=manifest.period,
        page_count=manifest.page_count,
        prose_chunks=len(manifest.prose_chunks),
        tables=len(manifest.tables),
        skipped_visuals=len(manifest.skipped_visuals),
        table_input_tokens_total=ce.table_input_tokens_total,
        est_output_tokens_total=ce.est_output_tokens_total,
        total_cost_usd_min=ce.total_cost_usd_min,
        total_cost_usd_max=ce.total_cost_usd_max,
        pricing_note=ce.pricing_note,
    )
    return Phase1Result(
        report_id=report_id,
        manifest_file=manifest_path.name,
        cost_summary=summary,
    ).model_dump()


# --- endpoints --------------------------------------------------------------


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/phase1", response_model=JobCreated, status_code=202)
def start_phase1(req: Phase1Request) -> JobCreated:
    """Kick off a free/local Phase-1 scan as a background job."""
    pdf_path = Path(req.file_path)
    if pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="file_path must point to a .pdf")
    if not pdf_path.is_file():
        raise HTTPException(status_code=400, detail=f"No file at {req.file_path}")

    def _do_scan() -> dict[str, Any]:
        manifest, manifest_path = run_phase1_scan(
            pdf_path=pdf_path,
            company=req.company,
            period=req.period,
            report_id=req.report_id,
        )
        return _phase1_result(manifest, manifest_path)

    job = JOBS.submit("phase1", _do_scan)
    return JobCreated(job_id=job.id)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id")
    return JobStatusResponse(
        job_id=job.id,
        kind=job.kind,
        status=job.status,
        result=job.result,
        error=job.error,
    )


def run() -> None:
    """`ingest-api` entry point — launches the dev server."""
    import uvicorn

    uvicorn.run("api.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    run()
