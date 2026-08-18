import sys

from ingestion.cli import main as phase1_main
from ingestion.cli_phase2 import run_phase2
from ingestion.embedding import SentenceTransformerEmbedder
from ingestion.manifest import load_manifest
from ingestion.vector_store_qdrant import COLLECTION_NAME, QdrantVectorStore


def test_phase1_then_phase2_end_to_end(synthetic_pdf, tmp_path, monkeypatch):
    """Full chain with REAL components: Phase 1 writes a manifest, Phase 2 loads it,
    embeds with the actual model, and indexes into an on-disk embedded Qdrant."""
    monkeypatch.chdir(tmp_path)

    # --- Phase 1: scan -> persist manifest ---
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest-phase1", str(synthetic_pdf), "--company", "Eternal Ltd", "--period", "FY2026", "--report-id", "e2e"],
    )
    phase1_main()

    manifest_path = tmp_path / "manifests" / "e2e.json"
    assert manifest_path.exists()

    # --- Phase 2: load manifest -> embed -> index ---
    manifest = load_manifest(manifest_path)
    store = QdrantVectorStore(path=str(tmp_path / "qdrant_data"))
    code = run_phase2(manifest, store, SentenceTransformerEmbedder(), assume_yes=True, interactive=False)
    assert code == 0

    # Vectors landed with the right dimensionality, payload, and named vector.
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == {"e2e"}
    count = store.client.count(COLLECTION_NAME).count
    assert count == len(manifest.prose_chunks) > 0

    points, _ = store.client.scroll(COLLECTION_NAME, with_payload=True, with_vectors=True, limit=1)
    p = points[0]
    assert len(p.vector["dense"]) == 768
    assert p.payload["company"] == "Eternal Ltd"
    assert p.payload["period"] == "FY2026"
    assert p.payload["report_id"] == "e2e"
    assert p.payload["text"]  # chunk text stored for retrieval
