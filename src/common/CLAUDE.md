# common/ — shared contract, config, interfaces

Cross-cutting building blocks that **both** the write path (`ingestion/`) and the
read path (`search/`) depend on. This package holds **no phase logic** and imports
nothing from `ingestion`, `api`, or `search` — the dependency arrow points *into*
`common`, never out. Read the root `CLAUDE.md` first for the invariants (phase
boundary §1, gate §1a, seam §5); this file owns the frozen config those sections
reference.

## What lives here

- `models.py` — the **§5 seam dataclasses**: `IngestionManifest`, `Chunk`,
  `TableGrid`, `SkippedVisual`, `CostEstimate`. The manifest is the durable Phase-1→
  Phase-2 handoff; its authoritative field list and rules stay in root §5.
- `manifest.py` — build/estimate/print/load helpers over that model:
  `build_manifest`, `estimate_cost`, `print_consent_summary` (used by the Phase-1
  CLI) and `load_manifest` (used by Phase 2 to reconstruct the manifest from JSON —
  Phase 2 never re-opens the PDF).
- `config/` — the frozen config objects below.
- `interfaces/` — the swappable-component ABCs: `Embedder`, `LLMClient`,
  `VectorStore` (+ `VectorRecord`). Concrete implementations live in their phase
  packages (`ingestion/indexing/`), never here.

---

## §3a. EmbedderProfile (frozen starting values) — `config/embedder_profile.py`

The embedder, its tokenizer, and chunk sizing are ONE bound unit. Swapping the
embedder must swap the tokenizer and re-tune the chunker together — otherwise the
chunker measures with the wrong ruler. Encode this as a single `EmbedderProfile`
object that BOTH the chunker (§3b) and the embed-call (§3f) read from.

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
  Keep `overlap_ratio` in 0.10–0.15. Never >= 0.5 (pathological re-chunking).
- This is the FIRST swappable component. Other profiles (MiniLM, bge, gte) get
  added and compared via recall@k later (§6). Build the abstraction now; add later.

---

## §3c. LLM (summarizer interface — **currently on hold**) — `config/llm_config.py`

**STATUS: on hold.** Phase 2 does not call the LLM to summarize tables right now —
tables are logged-and-skipped (§2), same disposition as images and dense
vector-graphic regions. Reversible policy, not a scope removal: the interface,
config, and Phase-1 tiktoken cost-estimate machinery stay in the codebase and are
simply not invoked. Phase 1's per-table token count / cost estimate are therefore
informational only while the hold holds. See root §6 for re-enabling.

- Provider: **OpenAI** (decided, if/when re-enabled). Cost-estimation tokenizer: **tiktoken**.
- Provider-agnostic interface (`common/interfaces/llm_client.py`):
  `LLMClient.summarize(table_markdown: str) -> str`. OpenAI is the implementation
  behind it; keep it clean so an Anthropic impl can be added without touching callers.
- `max_output_tokens = 150` — hard cap on each table summary's OUTPUT. DISTINCT from
  `EmbedderProfile.max_input_tokens` (512): different model, direction, purpose. Do
  not conflate (root §7).
- Prompt also instructs "at most 5 short lines" for quality; `max_output_tokens` is
  the enforceable cost ceiling.
- **Phase 1 does NOT call the LLM** — it only imports the tiktoken tokenizer to COUNT
  tokens for the estimate. The `LLMClient` implementation is Phase 2.
- **Note (Step 3):** the search step will add a *different* LLM call — answering a
  query over retrieved chunks. That is a new cost surface, not this summarizer; keep
  them separate.

---

## §3d. Credentials — `python-dotenv`

- Loaded from environment variables (`OPENAI_API_KEY`) via `python-dotenv`.
- Never hardcoded. Never committed. `.env` is gitignored.
