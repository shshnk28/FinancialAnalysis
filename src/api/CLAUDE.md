# api/ — REST transport over the pipeline

FastAPI layer over the existing seam (root §5) and gate (§1a). **Not a new
pipeline** — it calls the same `run_phase1_scan(...)` (and, later, Phase-2/search)
the CLI uses. The full roadmap and frozen service-layer decisions are root §8.

Top-level package (sibling of `common`, `ingestion`, `search`) because it composes
across packages: it imports the write path from `ingestion.*` and shared models from
`common.*`. Entry point: `ingest-api` → `api.app:run` (uvicorn, `:8000`, `/docs`).

## Modules

- `app.py` — the FastAPI app + Pydantic request/response models + `run()` launcher.
- `jobs.py` — `JobStore` + `Job`: an in-process thread-pool job runner. Deliberately
  minimal and **swappable for an out-of-process queue** when Step 2's heavier torch
  embedding arrives — the seam is shaped so endpoints won't change.

## Why async (both phases)

A scan (~108s) and an embed (~77s) can't block an HTTP response, so long work is
submitted as a job and the client polls for the result. Search (Step 3) is the only
synchronous call.

## Endpoints (Step 1 — built)

- `POST /phase1` — body `{file_path, company, period, report_id?}` (server-side path
  for now; multipart upload deferred to hosting, Step 5). Validates the path →
  submits a job → **202 `{job_id, status:"registered"}`**.
- `GET /jobs/{job_id}` — status; on `done`, `result = {report_id, manifest_file,
  cost_summary}`. `manifest_file` = `<report_id>.json`, the artifact Step 2 consumes.
- `GET /healthz` — liveness.

**Phase boundary holds:** `/phase1` is free/local (no embedding, Qdrant, LLM). The
gate (§1a) still governs Phase 2 — realized as the deliberate second API call (Step 2),
the transport equivalent of the second CLI invocation.
