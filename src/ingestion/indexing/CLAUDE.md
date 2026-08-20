# ingestion/indexing/ — Phase 2 (Process)

**Runs ONLY behind the cost-consent gate (root §1a).** Consumes the persisted
manifest JSON (never the PDF), embeds `prose_chunks`, and indexes them into Qdrant.
Currently **free** (local CPU embedding, LLM table-summarization on hold §3c) but
Phase 2 regardless — it runs only after the gate, never in the Phase 1 scan.

## Modules

- `embedding.py` — `SentenceTransformerEmbedder(Embedder)` (§3f).
- `vector_store_qdrant.py` — `QdrantVectorStore(VectorStore)` (§3e): collection
  management, `existing_report_ids`, `delete_document`, `index`, `point_id_for`.
- `cli.py` — `ingest-phase2` entry point; holds `run_phase2(...)`, the gate +
  collision-guard logic (injectable `store`/`embedder` so it is testable without the
  ~420MB model).

```
ingest-phase2 <manifest.json> [--yes] [--replace] [--qdrant-path DIR]
```
`--yes` bypasses the interactive `[y/N]`; `--replace` authorizes overwriting a
DIFFERENT document already indexed for the same `(company, period)` on a collision.

---

## §3e. Vector DB — DECIDED: Qdrant, embedded/in-process

- **Frozen:** **Qdrant**, run **embedded / in-process** via `QdrantClient(path=...)` —
  on-disk local persistence, **no server, no Docker**. Rationale: local-first fit, and
  an **identical client API across embedded → local server → Qdrant Cloud**, so scaling
  up is a one-line constructor change (§2 "build the abstraction now, swap later").
  *(The service layer, root §8, will move this to server mode via `QdrantClient(url=...)`
  once API + worker + search run as separate processes.)*
- **Retrieval mode (frozen for now):** **DENSE ONLY.** Sparse/hybrid fusion is deferred (§6).
- **Collection config** (derived from §3a): **768-dim** vectors, **cosine** distance.
- **Collection layout:** a **single collection** (`annual_reports`) holds every
  company's vectors; retrieval scopes by company/period via **payload filters**, not
  separate collections. Enables cross-company comparison and scales fine at our size.
- **Point ID scheme:** Qdrant IDs must be uint64/UUID, so the string `chunk_id`
  (`report_id:page:chunk_index`) can't be the ID directly. Use a deterministic
  **`uuid5(namespace, chunk_id)`** — same chunk always maps to the same point →
  idempotent upserts. The human-readable `chunk_id` rides in the payload.
- **Payload schema:** each point carries `chunk_id`, `text` (so retrieval returns text
  directly), `page`, `section`, plus denormalized identity `report_id`, `document_name`,
  `company`, `period`. **Payload indexes** on **`company`, `period`, `report_id`**.
- **Re-ingestion & `(company, period)` uniqueness guard:** before indexing, check Qdrant
  for existing points at this `(company, period)`:
  - **None** → proceed (fresh index).
  - **Same `report_id`** → identical content; idempotent refresh (UUIDv5 overwrite in place); proceed quietly.
  - **Different `report_id`** → **collision**: a different document already occupies this
    company+period. The system CANNOT distinguish a legit corrected-report re-ingest from
    a mistaken wrong-file ingest, so it must NOT act silently. **Refuse by default:**
    interactively show existing vs incoming and require `[y/N]` (default No); with
    `--yes`, refuse unless **`--replace`** is also passed. Only on explicit approval,
    **replace** = delete existing points keyed on `(company, period)` (NOT `report_id`,
    which changes with content), then insert. Upholds §2 (no silent data loss).
  - **Caveat:** only as reliable as `(company, period)` strings being consistent
    (`FY2026` vs `FY25-26` would evade it). Canonical-key/normalization hardening is deferred (§6).
- **Forward-compat for hybrid:** collection created with **named vectors** (dense named
  `"dense"`) so a sparse vector can be added later without a destructive migration. Do
  NOT add sparse now.
- Interface (in `common/`): `VectorStore.index(records: list[VectorRecord]) -> None`;
  `VectorRecord` maps to a Qdrant point `(uuid5 id, {"dense": vector}, payload)`.

---

## §3f. Embedding execution — DECIDED: sentence-transformers, local, CPU

- **Frozen:** run `EmbedderProfile.model_id` via **`sentence-transformers`**, **locally,
  on CPU** — the canonical way to run all-mpnet-base-v2. Adds **`torch`** as a Phase-2
  dependency; Phase 1 deliberately avoided torch (fast tokenizer only) — this is where
  it legitimately enters.
- **Impl:** `SentenceTransformerEmbedder(Embedder)` lazily loads the model and implements
  `embed(texts) -> list[list[float]]`. All sizing/model config comes from the active
  `EmbedderProfile` (§3a) — never hardcoded here.
- **Encode settings (frozen):**
  - `normalize_embeddings=True` — unit vectors. Redundant under cosine (§3e) but harmless;
    leaves the door open to dot-product later without re-embedding.
  - `batch_size = 32` — chunks per forward pass (NOT tokens, NOT dims); CPU default,
    tunable, not load-bearing (no effect on vectors, only throughput/memory).
  - **No query/passage prefixes** — mpnet doesn't use them (unlike e5/bge); embed as-is.
- **Input:** `prose_chunks[*].text` only. Tables are NOT embedded while the §3c hold holds.
- **Model asset:** all-mpnet-base-v2 (~420MB) downloads once from HF Hub to the local
  cache, then runs offline.
