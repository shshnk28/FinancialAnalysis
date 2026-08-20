# ingestion/ — the write path (PDF → indexed vectors)

The umbrella for the two-phase ingestion pipeline. It splits along the **phase
boundary** (root §1): the two sub-packages are the two phases, separated by the
cost-consent gate (§1a).

- **`extraction/` — Phase 1 (Scan).** Free, local, no LLM/embedding/network spend.
  PDF → `IngestionManifest` (+ cost summary). See `extraction/CLAUDE.md` (owns §3b, §4).
- **`indexing/` — Phase 2 (Process).** Behind the gate. Consumes the manifest,
  embeds `prose_chunks`, indexes into Qdrant. See `indexing/CLAUDE.md` (owns §3e, §3f).

The seam between them is the `IngestionManifest` (root §5), defined in `common/`.
Phase 2 consumes **only** the persisted manifest JSON — it never re-opens the PDF.

Everything shared (models, config, interfaces) lives in `src/common/`, not here.
The HTTP transport over these phases lives in `src/api/`.
