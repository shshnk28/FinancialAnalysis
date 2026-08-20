# search/ — the read path (planned, Step 3)

**Skeleton only — not yet built.** This is the retrieval side, the counterpart to
the `ingestion/` write path. It becomes real at root §8 **Step 3**.

Planned shape (subject to a decision freeze before implementation, like every other
component):

- **Input:** a query + **mandatory** `company` and `period` filters.
- **Retrieve:** embed the query with the active `EmbedderProfile` (§3a, from `common/`)
  — the SAME embedder used at index time — and run a dense search over the Qdrant
  `annual_reports` collection, scoped by `company`/`period` payload filters (§3e).
- **Answer:** pass the retrieved chunks to an `LLMClient` to synthesize an answer.
  This is a **new LLM cost surface**, distinct from the on-hold table summarizer (§3c) —
  it needs its own provider/key/guardrail decision, and (for a public demo) a spend cap.

Scope note: retrieval was previously out of scope (root §0); it is brought in scope
**from this step onward**. Dossier assembly and structured-API ratio fetching remain
out of scope.

Reuses from `common/`: `EmbedderProfile`, the `LLMClient` interface, and the Qdrant
payload schema. It should NOT duplicate the embedder or store — import them.
