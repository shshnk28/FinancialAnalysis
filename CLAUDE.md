# CLAUDE.md — Investment-Analysis Ingestion Pipeline

This file is the durable spec for this repo. Re-read it before each work session.
It defines a **two-phase** ingestion pipeline and the frozen decisions behind it.

---

## 0. What we are building

Ingestion for a RAG-based investment-analysis tool. Input: company annual-report
PDFs. Output: embeddings indexed in a vector DB, plus the original content as
retrievable metadata. Retrieval, dossier assembly, and ratio-fetching from
structured APIs are **out of scope** for this repo.

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

**We are implementing PHASE 1 ONLY right now.** Do not write Phase 2 logic yet.
Design Phase 1 so Phase 2 slots in against the contract in §5.

**Self-check test:** before writing any code, ask "is this free and local?"
If it calls an LLM, an embedding model, or any paid/network service, it is
Phase 2 — stop. Phase 1's only outputs are a manifest object (§5) and a printed
cost report.

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

## 3. FROZEN CONFIG

### 3a. EmbedderProfile (starting values)

The embedder, its tokenizer, and chunk sizing are ONE bound unit. Swapping the
embedder must swap the tokenizer and re-tune the chunker together — otherwise the
chunker measures with the wrong ruler. Encode this as a single `EmbedderProfile`
object that BOTH the chunker and the embed-call read from.

```
EmbedderProfile:
    name              = "all-mpnet-base-v2"
    model_id          = "sentence-transformers/all-mpnet-base-v2"
    tokenizer         = HF AutoTokenizer for model_id   # the chunker's ruler
    max_input_tokens  = 512        # embedder's INPUT limit (hard truncation ceiling)
    chunk_size        = 450        # tokens; headroom below max_input_tokens
    overlap_ratio     = 0.12       # overlap = round(chunk_size * overlap_ratio) -> ~54 tokens
```

Rules:
- `chunk_size` is in TOKENS, measured with this profile's `tokenizer`.
- `chunk_size` MUST stay below `max_input_tokens` (headroom for special tokens),
  or chunks get silently truncated by the embedder — forbidden (§2).
- Overlap is derived: `overlap_tokens = round(chunk_size * overlap_ratio)`.
  Keep `overlap_ratio` in the range 0.10–0.15. Never >= 0.5 (causes pathological
  re-chunking).
- This is the FIRST swappable component. Later, other profiles (MiniLM, bge, gte)
  will be added and compared via recall@k. Build the abstraction now; add profiles
  later.

### 3b. Chunker

- Use `RecursiveCharacterTextSplitter.from_huggingface_tokenizer()` fed the
  active `EmbedderProfile.tokenizer`. This measures chunk length in the SAME
  tokens the embedder will see.
- Recursive separator behavior (paragraph -> line -> sentence -> word) and
  overlap handling are the library's — do not hand-roll splitting.
- Chunk size and overlap come from the active `EmbedderProfile` (§3a), never
  hardcoded elsewhere.

### 3c. LLM (Phase 2 — interface only in Phase 1; **currently on hold**)

**STATUS: on hold.** Phase 2 does not call the LLM to summarize tables right
now — tables are logged-and-skipped instead (§2), same disposition as images
and dense vector-graphic regions. This is a reversible policy decision, not a
scope removal: the interface, config, and Phase 1 token-counting/cost-estimate
machinery described below stay in the codebase unchanged and are simply not
invoked for table summarization at present. Phase 1's per-table token count and
cost estimate are therefore informational only while the hold is in effect —
no real spend occurs against them. See §6 for re-enabling this.

- Provider: **OpenAI** (decided, if/when re-enabled). Tokenizer for cost estimation: **tiktoken**.
- Expose a provider-agnostic interface:
  ```
  LLMClient.summarize(table_markdown: str) -> str
  ```
  OpenAI is the implementation behind it. Keep the interface clean so an
  Anthropic implementation could be added without touching callers.
- `max_output_tokens = 150` — the hard cap on each table summary's OUTPUT.
  This is DISTINCT from `EmbedderProfile.max_input_tokens` (512). Different model,
  different direction, different purpose. Do not conflate.
- Prompt also instructs "at most 5 short lines" for quality; `max_output_tokens`
  is the enforceable cost ceiling.
- **Phase 1 does NOT call the LLM.** Phase 1 only imports the tiktoken tokenizer
  to COUNT tokens for the estimate. The `LLMClient` implementation is Phase 2.

### 3d. Credentials

- Loaded from environment variables (`OPENAI_API_KEY`), via `python-dotenv`.
- Never hardcoded. Never committed. `.env` is gitignored.

### 3e. Vector DB (Phase 2 — deferred)

- Choice undecided; taken after Phase 1 completes.
- Abstract behind an interface, e.g.:
  ```
  VectorStore.index(records: list[VectorRecord]) -> None
  ```
  where a `VectorRecord` carries the vector + original content + metadata.
- No implementation in Phase 1.

---

## 4. PHASE 1 — build order (verify each step before the next)

Build incrementally. After each step, print output and stop so it can be run and
verified before continuing.

1. **Extraction** — pdfplumber over every page:
   - text mode -> prose
   - table mode -> tables as markdown grids
   - detect image objects (`page.images`) and dense vector-graphic regions
     (`page.curves`) for the log-and-skip branch
   - print a per-page report of what was found
2. **Chunking** — split prose via §3b using the active `EmbedderProfile`.
   Print chunk count and a sample chunk with its token length.
3. **Token counting** — for each table, compute EXACT input tokens
   (prompt + table markdown) via tiktoken. Output is bounded by
   `max_output_tokens` (150), not counted.
4. **Manifest + cost report** — assemble the §5 manifest dataclass and print the
   consent summary (see the Phase 1 sample doc for the exact shape).

---

## 5. THE CONTRACT BETWEEN PHASES

Phase 1 produces ONE typed artifact that Phase 2 consumes. This dataclass is the
seam — it is how "implement Phase 2 later" stays a clean continuation, not a
rewrite. Define it explicitly.

```
IngestionManifest:
    document_name       : str
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

---

## 6. DECISIONS STILL OPEN (do not implement)

- Whether/when to lift the LLM table-summarization hold (§3c) — until then,
  tables are logged-and-skipped rather than summarized/embedded.
- Vector DB choice (§3e) — after Phase 1.
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
