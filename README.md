# Investment-Analysis Ingestion Pipeline

Ingestion for a RAG-based investment-analysis tool. Input: company annual-report
PDFs. Output (once Phase 2 is built): embeddings indexed in a vector DB, with the
original content retained as retrievable metadata. Retrieval, dossier assembly,
and ratio-fetching from structured financial APIs are out of scope for this repo.

## Two-phase design

The pipeline is split by a cost-consent gate:

- **Phase 1 — Scan** *(implemented here)*. Free, local only. No LLM calls, no
  embedding calls, no network spend beyond a one-time tokenizer download.
  Extracts text and tables, detects images/dense vector graphics, counts exact
  table tokens, and produces a manifest plus a printed cost estimate.
- **Phase 2 — Process** *(not yet built)*. Paid. Runs only after a user reviews
  and approves the Phase 1 cost summary. Summarizes tables via an LLM, embeds
  content, and indexes it into a vector store.

Phase 1 never calls an LLM or embedding model — it only imports `tiktoken` to
*count* tokens for the cost estimate.

## Key architectural decisions

- **No silent data loss.** Every element extracted from a PDF gets an explicit
  disposition — parsed, or logged-and-skipped — never silently dropped. This
  includes reclassifying grid structures that have no real cell content as
  skipped visuals rather than treating them as captured tables.
- **The LLM is never the source of truth for numbers.** It only turns table
  grids into prose for retrieval, in Phase 2 — precise financial ratios come
  from a structured API elsewhere, not this repo.
- **Cost is visible and consented to before it's incurred.** That's the point
  of the phase boundary.
- **Swappable components sit behind interfaces.** The embedder, LLM client, and
  vector store are each an abstract interface paired with its own config
  object, so a component and its config can be swapped together without
  touching the rest of the pipeline. Only the interfaces exist so far — Phase 1
  never invokes them.
- **The embedder, its tokenizer, and the chunker's sizing are one bound unit.**
  Changing the embedding model means changing its tokenizer and re-tuning chunk
  size together, since chunk length is measured with that specific tokenizer.

## Status

Phase 1 is implemented and verified end-to-end against a real annual report,
with a pytest suite covering each module. Phase 2 (summarization, embedding,
vector indexing) and the vector DB choice are intentionally not started.
