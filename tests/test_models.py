from ingestion.models import IngestionManifest


def test_ingestion_manifest_default_lists_are_independent_instances():
    # Regression guard: field(default_factory=list) must not become a shared
    # mutable default (e.g. accidentally rewritten as `= []`).
    a = IngestionManifest(document_name="a.pdf", page_count=1)
    b = IngestionManifest(document_name="b.pdf", page_count=1)

    a.prose_chunks.append("not a real chunk, just checking identity")

    assert a.prose_chunks is not b.prose_chunks
    assert b.prose_chunks == []


def test_ingestion_manifest_defaults_are_empty():
    manifest = IngestionManifest(document_name="a.pdf", page_count=1)
    assert manifest.prose_chunks == []
    assert manifest.tables == []
    assert manifest.skipped_visuals == []
    assert manifest.table_input_tokens == []
    assert manifest.est_output_tokens == 0
    assert manifest.cost_estimate is None
