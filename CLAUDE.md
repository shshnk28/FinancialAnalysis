# CLAUDE.md — Investment-Analysis Ingestion Pipeline

This file is the durable spec for this repo. Re-read it before each work session.
It defines a **two-phase** ingestion pipeline and the frozen decisions behind it.

---

## 0. What we are building

Ingestion for a RAG-based investment-analysis tool. Input: company annual-report
PDFs. Output: embeddings indexed in a vector DB, plus the original content as
retrievable metadata.

**Scope (expanded — see §8).** Originally this repo was ingestion only. It is now
being grown into a **live service**: a REST API over the pipeline, then retrieval
(vector search + LLM answering), then a UI, then a hosted demo. So **serving the
pipeline over HTTP is in scope**, and **retrieval is in scope from the search step
(§8 Step 3) onward** — it was previously out of scope. Dossier assembly and
ratio-fetching from structured APIs remain **out of scope**. The **CLI stays the
reference path** and the **two-phase consent gate (§1/§1a) is unchanged** — the API
is transport over the same seam, not a new pipeline.

Language: **Python**.

---

## 1. THE PHASE BOUNDARY — hardest constraint in this repo

The pipeline runs in two phases separated by a **cost-consent gate**.

- **Phase 1 — Scan.** Free. Local only. No LLM calls, no embedding calls,
  no network spend. Extracts content, detects tables and images, counts tokens,
  and emits a cost summary for user consent.
- **Phase 2 — Process.** Paid. Runs ONLY after the user approves the Phase 1
  summary. Embeds `prose_chunks` and indexes them via `VectorStore`.
  **LLM table-summarization is currently on hold** (see §3c) — tables are
  logged-and-skipped instead, the same disposition as images and dense
  vector-graphic regions. No table content is embedded or indexed while this
  hold is in effect.

**Phase 1 and Phase 2 are both built.** We are now building the **service layer**
(§8) — a REST API over the same two phases, then search, UI, and hosting. The phase
boundary still holds regardless of transport: Phase 2 runs ONLY behind the consent
gate (§1a), and every piece of code must respect which phase it belongs to.

**Self-check test:** which phase does this code belong to? Extraction, chunking,
token-counting, and manifest assembly are **Phase 1** (free, local, no embedding).
Embedding and vector indexing are **Phase 2**, and run only after the consent gate
(§1a). Note embedding is **local and currently free** — the only *paid* Phase 2 step,
LLM table-summarization, remains on hold (§3c), so nothing in Phase 2 spends money
today; the gate still governs it as the architectural invariant.

### 1a. Gate mechanics — the two-command handoff (DECIDED)

The cost-consent gate is realized as **two separate CLI commands**, with the
`IngestionManifest` (§5) as the durable handoff artifact:

1. **`ingest-phase1 <pdf>`** (built) runs the free/local scan and **persists the
   full manifest** as JSON to a deterministic path **`./manifests/<report_id>.json`**,
   printing that path alongside the cost summary. The manifest is self-contained —
   it holds every chunk's text — so nothing else is needed downstream.
2. **The user reviews** the printed cost summary.
3. **`ingest-phase2 <manifest.json>`** (implemented in `ingestion/indexing/cli.py`) takes the
   manifest path as an **explicit argument**, **re-prints the cost summary** from it,
   and **requires interactive confirmation** (`[y/N]`, default No) before doing any
   embed/index work. A **`--yes`** flag bypasses the prompt for automation/CI;
   **`--replace`** authorizes overwriting a different document on a collision (§3e).

Rules:
- Phase 2 consumes **only** the manifest JSON — it never re-opens the PDF or
  re-runs extraction. The manifest is the §5 seam, made durable.
- The manifest filename is derived from `report_id` (the content hash, §5) so it is
  unique per document and predictable; `./manifests/` is the default directory.
- **Consent = the deliberate second invocation + the confirmation.** Running
  `ingest-phase2` on a reviewed manifest is the act of approval.
- **Currently free:** with the LLM hold in effect (§3c), Phase 2 is embed+index —
  both local and free — so the gate presently guards compute/time, not dollars. The
  gate stays regardless: it is the architectural invariant, and regains dollar-stakes
  if the hold lifts.
- **Manifest persistence (DONE):** `ingest-phase1` writes the full manifest to
  `./manifests/<report_id>.json` by **default** (creating the dir as needed) and prints
  that path plus the exact `ingest-phase2 <path>` command to run next. `--json-out`
  overrides the location. The `manifests/` dir is gitignored (generated artifact).

---

## 2. Design principles (apply throughout)

- **No silent data loss.** Every element gets an explicit disposition: parsed,
  summarized, or logged-and-skipped. Nothing is dropped without a record.
  **Tables currently get the logged-and-skipped disposition**, not summarized
  — LLM table-summarization is on hold (§3c).
- **LLM is never the source of truth for numbers.** Precise financial ratios
  come from a structured API elsewhere (not this repo). When/if LLM
  table-summarization is resumed (currently on hold, §3c), the LLM only turns
  table grids into prose for retrieval — it never computes or asserts numeric
  values itself.
- **Cost is visible and consented before it is incurred.** The gate is the point.
- **Swappable components are abstracted behind interfaces** (embedder, LLM,
  vector DB). Choices are deferred and measured, not guessed.

---

## 3. FROZEN CONFIG — lives with the package that owns it

To keep this file lean (§9), each frozen-config block now lives in the package
CLAUDE.md next to its code. The **§ anchors are stable** — cross-references
elsewhere in this file still resolve here:

- **§3a EmbedderProfile** — embedder/tokenizer/chunk-sizing as one bound unit
  (mpnet, 512 max input, chunk 450, overlap 0.12). → **`src/common/CLAUDE.md`**
- **§3b Chunker** — `RecursiveCharacterTextSplitter.from_huggingface_tokenizer`
  fed the active profile's tokenizer. → **`src/ingestion/extraction/CLAUDE.md`**
- **§3c LLM (table summarizer, ON HOLD)** — OpenAI behind `LLMClient.summarize`;
  `max_output_tokens = 150`; not invoked while on hold. → **`src/common/CLAUDE.md`**
- **§3d Credentials** — `OPENAI_API_KEY` via `python-dotenv`; never committed.
  → **`src/common/CLAUDE.md`**
- **§3e Vector DB** — Qdrant embedded, dense-only, single `annual_reports`
  collection, `uuid5` point IDs, `(company, period)` collision guard, named vectors.
  → **`src/ingestion/indexing/CLAUDE.md`**
- **§3f Embedding execution** — sentence-transformers, local CPU, normalize,
  batch 32. → **`src/ingestion/indexing/CLAUDE.md`**

The two numbers people confuse (`max_input_tokens` 512 vs `max_output_tokens` 150)
are in §7.

---

## 4. PHASE 1 — build order

The step-by-step build order (extraction → chunking → token counting → manifest +
cost report) and the extraction rules (blank-table reclassification, image/curve
log-and-skip) live in **`src/ingestion/extraction/CLAUDE.md`**.

---

## 5. THE CONTRACT BETWEEN PHASES

Phase 1 produces ONE typed artifact that Phase 2 consumes. This dataclass is the
seam — it is how "implement Phase 2 later" stays a clean continuation, not a
rewrite. Define it explicitly.

```
IngestionManifest:
    document_name       : str
    company             : str                  # user-provided identity (--company)
    period              : str                  # user-provided reporting period (--period), e.g. "FY2026"
    page_count          : int
    prose_chunks        : list[Chunk]          # text + metadata (page, section, chunk_id)
    tables              : list[TableGrid]      # markdown grid + source page  (NOT yet summarized)
    skipped_visuals     : list[SkippedVisual]  # page, type, dimensions/curve-count
    table_input_tokens  : list[int]            # exact, per table (tiktoken)
    est_output_tokens   : int                  # tables * max_output_tokens (ceiling)
    cost_estimate       : CostEstimate         # input exact + output capped, min/max
```

Rules:
- Phase 1 populates this fully. It contains NO embeddings and NO table summaries
  — those are Phase 2 products.
- Phase 2 consumes `prose_chunks` (embeds them directly) and indexes via
  `VectorStore`. **`tables` are currently logged-and-skipped, not summarized or
  embedded** — LLM table-summarization is on hold (§3c). The field stays
  populated as retrievable metadata and as the seam Phase 2 will consume
  (`tables`, to summarize) if that hold is lifted.
- `chunk_id` scheme: `report_id:page:chunk_index` — stable, for retrieval-quality
  debugging later.
- **Document identity (`company`, `period`)** is document-level and **user-provided**
  at ingestion via required `--company` / `--period` flags on `ingest-phase1` — no
  filename parsing, no LLM extraction (both were considered and rejected as
  fragile/out-of-boundary). It is surfaced in the consent summary for the user to
  confirm. Phase 2 **denormalizes** these onto each Qdrant point's payload so
  retrieval can filter by company/period; they are NOT stored per-`Chunk` in the
  manifest. Schema is intentionally minimal (two strings) — a canonical
  ticker/company-id key can be added later if joins to the structured API are needed.

---

## 6. DECISIONS STILL OPEN (do not implement)

- Whether/when to lift the LLM table-summarization hold (§3c) — until then,
  tables are logged-and-skipped rather than summarized/embedded.
- Enabling hybrid retrieval — add sparse vectors to the Qdrant collection (§3e);
  a deferred improvement, dense-only ships first.
- Torch-free embedding via ONNX (optimum / Qdrant fastembed) (§3f) — a deferred
  optimization; sentence-transformers ships first. Needs verification that
  all-mpnet-base-v2 is supported without a manual ONNX export.
- Hardening the `(company, period)` uniqueness guard (§3e) — a canonical company/period
  key and/or `period` normalization so differently-spelled periods can't evade the
  collision check. Deferred; the free-text guard ships first.
- Additional `EmbedderProfile`s for recall@k comparison — after Phase 1 works.
- Section-header-aware pre-splitting (so chunks don't straddle report sections) —
  a refinement, not day-one.

---

## 7. QUICK REFERENCE — two numbers people confuse

| Name | Value | Belongs to | Meaning |
|---|---|---|---|
| `max_input_tokens`  | 512 | EmbedderProfile | mpnet's input ceiling; caps chunk size |
| `max_output_tokens` | 150 | LLMClient config | cap on each table summary's output; bounds cost |

Different models, different directions. Never merge them.

Note: LLM table-summarization is currently on hold (§3c), so `max_output_tokens`
remains defined in code but isn't presently enforced against real spend.

---

## 8. SERVICE / API LAYER (in progress)

The pipeline is being grown from two CLI commands into a **live, demoable service**.
This is transport over the existing seam (§5) and gate (§1a) — **not** a new
pipeline. We build one step at a time:

| Step | Deliverable | Status |
|---|---|---|
| **1** | Phase-1 scan API (path + company + period → job → manifest + cost summary) | **built** |
| 2 | Phase-2 indexing API (manifest filename → job → "registered"); Qdrant → server mode | planned |
| 3 | Search API (query + company + period → vector search → LLM answer over chunks) | planned |
| 4 | UI over indexing + search | planned |
| 5 | Host on portfolio site | planned |

**Frozen decisions:**
- **Framework:** FastAPI + uvicorn. Entry point: `ingest-api` (`api.app:run`).
- **Async, both phases:** a scan (~108s) and an embed (~77s) can't block an HTTP
  response, so `POST /phase1` (and later the phase-2 endpoint) returns a **job id
  immediately** and the client polls **`GET /jobs/{id}`** for status + result. The
  job runner is an in-process `JobStore` on a thread pool (§ `api/jobs.py`) —
  deliberately swappable for an out-of-process queue when Step 2's heavier torch
  embedding arrives.
- **Input:** **server-side file path** for now (`Phase1Request.file_path`). Multipart
  upload is deferred to the hosting step (Step 5), when anonymous visitors have no
  server path.
- **Qdrant server mode** is the target once API + indexing worker + search run as
  separate processes (one-line `QdrantClient(url=...)`, §3e). Wired in Step 2/3 —
  **Phase 1 never touches Qdrant**, so Step 1 doesn't need it.

**Phase boundary still holds.** Phase 1 over HTTP is **free/local** — no embedding,
Qdrant, or LLM. The consent gate (§1a) still governs Phase 2, now realized as the
**deliberate second API call** (Step 2), the transport equivalent of the second CLI
invocation.

**Shared code path.** Both the CLI and the API call `run_phase1_scan(...)` in
`src/ingestion/extraction/service.py` (extraction → chunk → count → build_manifest → persist).
The CLI adds only presentation (`print_consent_summary` + next-step hints); the API
returns the same numbers as JSON. No duplicated orchestration.

**Endpoints (Step 1):** `POST /phase1` → `202 {job_id, status:"registered"}`;
`GET /jobs/{job_id}` → status, and on `done` a `result` of
`{report_id, manifest_file, cost_summary}` (`manifest_file` = `<report_id>.json`,
the artifact Step 2 consumes); `GET /healthz`; auto OpenAPI docs at `/docs`.
Endpoint/job details live in **`src/api/CLAUDE.md`**.

---

## 9. REPO STRUCTURE — where things live

This root file holds the **cross-cutting invariants** (phase boundary §1/§1a,
principles §2, the seam §5, open decisions §6, the roadmap §8). Package-specific
detail lives in a `CLAUDE.md` next to the code — Claude Code loads it automatically
when you work in that subtree. **Keep each invariant in exactly one place** (this
root); package files *reference* §-anchors, never restate them, or the copies drift.

```
src/
  common/           # shared contract + config + interfaces — imports nothing above it
    models.py         §5 seam dataclasses (IngestionManifest, Chunk, …)
    manifest.py       build/estimate/print/load over the manifest
    config/           §3a EmbedderProfile · §3c LLMConfig · pricing
    interfaces/       Embedder · LLMClient · VectorStore ABCs
    CLAUDE.md         → §3a, §3c, §3d
  ingestion/        # the write path (PDF → indexed vectors)
    CLAUDE.md         → umbrella: the two phases + the seam
    extraction/       Phase 1 (Scan, free/local): pdf, chunking, token_counting,
                      report_id, service (run_phase1_scan), cli   → §3b, §4
    indexing/         Phase 2 (Process, gated): embedding, vector_store_qdrant, cli
                      → §3e, §3f
  search/           # the read path — Step 3 skeleton (planned)   → §8 Step 3
  api/              # FastAPI transport over the pipeline: app, jobs   → §8
CLAUDE.md           # this file — invariants, contract, roadmap
```

**Console scripts:** `ingest-phase1` → `ingestion.extraction.cli:main`;
`ingest-phase2` → `ingestion.indexing.cli:main`; `ingest-api` → `api.app:run`.
