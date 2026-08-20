# ingestion/extraction/ — Phase 1 (Scan)

**Free, local, no spend.** No LLM calls, no embedding calls, no network. Turns an
annual-report PDF into the `IngestionManifest` (root §5) plus a cost-consent summary,
and persists the manifest to `./manifests/<report_id>.json` (the §1a handoff). This
package must never import torch, sentence-transformers, or Qdrant — that's Phase 2.

## Modules

- `pdf.py` — pdfplumber extraction (`scan_pdf`, `PageExtraction`). Named `pdf.py`
  (not `extraction.py`) to avoid an `extraction.extraction` path; public names are
  re-exported from the package `__init__`.
- `chunking.py` — prose → `Chunk`s via §3b.
- `token_counting.py` — exact per-table tiktoken input tokens (for the estimate).
- `report_id.py` — `compute_report_id` = SHA-256 of PDF bytes, first 12 hex chars.
- `service.py` — `run_phase1_scan(...)`: the reusable orchestration (extract → chunk →
  count → build_manifest → persist). **Shared by the CLI and the API** — no duplicated
  logic. Returns `(manifest, manifest_path)`; does not print.
- `cli.py` — `ingest-phase1` entry point; adds presentation (`print_consent_summary`
  + next-step hints) around `run_phase1_scan`.

## §3b. Chunker

- Use `RecursiveCharacterTextSplitter.from_huggingface_tokenizer()` fed the active
  `EmbedderProfile.tokenizer` (§3a, in `common/`). This measures chunk length in the
  SAME tokens the embedder will see.
- Recursive separators (paragraph → line → sentence → word) and overlap handling are
  the library's — do not hand-roll splitting.
- Chunk size and overlap come from the active `EmbedderProfile`, never hardcoded here.

## §4. Build order (verify each step before the next)

Build incrementally; after each step print output and stop so it can be verified.

1. **Extraction** — pdfplumber over every page: text → prose; table mode → markdown
   grids; detect image objects (`page.images`) and dense vector-graphic regions
   (`page.curves`) for the log-and-skip branch; print a per-page report. Blank
   pdfplumber "tables" are reclassified as `empty_table_structure` skipped visuals —
   never emitted as real tables (upholds §2, no silent data loss).
2. **Chunking** — split prose via §3b using the active `EmbedderProfile`; print chunk
   count and a sample chunk with its token length.
3. **Token counting** — per table, EXACT input tokens (prompt + table markdown) via
   tiktoken. Output is bounded by `max_output_tokens` (150), not counted.
4. **Manifest + cost report** — assemble the §5 manifest and print the consent summary.

## CLI

```
ingest-phase1 <pdf> --company "Eternal Ltd" --period "FY2026" [--report-id ID] [--json-out PATH]
```
`--company`/`--period` are REQUIRED (document identity, root §5). Default output is
`./manifests/<report_id>.json`; `--json-out` overrides. `manifests/` is gitignored.
