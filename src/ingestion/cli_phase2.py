import argparse
import sys
from pathlib import Path
from typing import Callable

from ingestion.interfaces.vector_store import VectorRecord
from ingestion.manifest import load_manifest, print_consent_summary
from ingestion.models import IngestionManifest
from ingestion.vector_store_qdrant import COLLECTION_NAME, QdrantVectorStore


def _report_id_of(manifest: IngestionManifest) -> str:
    # report_id is the chunk_id prefix (report_id:page:chunk_index); rsplit keeps it
    # correct even if a --report-id override contained colons.
    return manifest.prose_chunks[0].chunk_id.rsplit(":", 2)[0]


def _prompt_confirm(prompt: str) -> bool:
    return input(prompt).strip().lower() in ("y", "yes")


def run_phase2(
    manifest: IngestionManifest,
    store: QdrantVectorStore,
    embedder,
    *,
    assume_yes: bool = False,
    replace: bool = False,
    interactive: bool = True,
    confirm: Callable[[str], bool] = _prompt_confirm,
) -> int:
    """Embed the manifest's prose chunks and index them into Qdrant, behind the
    §1a consent gate and the §3e (company, period) collision guard.

    Returns a process exit code (0 = indexed / clean no-op, 2 = refused/aborted).
    Takes an injected `store` and `embedder` so the gate logic is testable without
    loading the real model."""
    print_consent_summary(manifest)

    chunks = manifest.prose_chunks
    if not chunks:
        print("No prose chunks in this manifest — nothing to embed or index.")
        return 0

    report_id = _report_id_of(manifest)
    existing = store.existing_report_ids(manifest.company, manifest.period)
    other_docs = existing - {report_id}  # different report_id(s) at this (company, period)

    replacing = False
    if other_docs:
        # §3e collision: a DIFFERENT document already occupies this (company, period).
        print(
            f"\n⚠️  COLLISION: {manifest.company} / {manifest.period} already has a different "
            f"document indexed (report_id(s): {sorted(other_docs)})."
        )
        print(f"    Incoming: report_id {report_id} ({manifest.document_name}).")
        if replace:
            replacing = True
        elif interactive and not assume_yes:
            if confirm("    Replace the existing document? [y/N]: "):
                replacing = True
            else:
                print("    Aborted — existing document left intact.")
                return 0
        else:
            print(
                "    Refused: overwriting a different document requires --replace.",
                file=sys.stderr,
            )
            return 2
    else:
        # No collision (fresh index, or idempotent refresh of the same report) — normal §1a gate.
        if not assume_yes:
            if interactive:
                if not confirm("\nProceed with embed + index? [y/N]: "):
                    print("Aborted — no changes made.")
                    return 0
            else:
                print("Refused: non-interactive run requires --yes to proceed.", file=sys.stderr)
                return 2

    if replacing:
        store.delete_document(manifest.company, manifest.period)
        print("    Replaced: prior document's vectors deleted.")

    texts = [c.text for c in chunks]
    print(f"Embedding {len(texts)} chunks (CPU)...")
    vectors = embedder.embed(texts)

    records = [
        VectorRecord(
            vector=vector,
            content=chunk.text,
            metadata={
                "chunk_id": chunk.chunk_id,
                "page": chunk.page,
                "section": chunk.section,
                "report_id": report_id,
                "document_name": manifest.document_name,
                "company": manifest.company,
                "period": manifest.period,
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    store.index(records)
    print(f"Indexed {len(records)} chunks into '{COLLECTION_NAME}' for {manifest.company} / {manifest.period}.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2 embed + index (runs behind the consent gate)")
    parser.add_argument("manifest_path", type=Path, help="Path to the Phase 1 manifest JSON")
    parser.add_argument("--qdrant-path", default="qdrant_data", help="Embedded Qdrant storage dir")
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Allow overwriting a DIFFERENT document already indexed for this company/period",
    )
    args = parser.parse_args()

    from ingestion.embedding import SentenceTransformerEmbedder

    manifest = load_manifest(args.manifest_path)
    store = QdrantVectorStore(path=args.qdrant_path)
    embedder = SentenceTransformerEmbedder()

    code = run_phase2(
        manifest,
        store,
        embedder,
        assume_yes=args.yes,
        replace=args.replace,
        interactive=sys.stdin.isatty(),
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
