import pytest

from ingestion.cli_phase2 import run_phase2
from ingestion.manifest import build_manifest
from ingestion.models import Chunk
from ingestion.vector_store_qdrant import COLLECTION_NAME, QdrantVectorStore

DIM = 8


class FakeEmbedder:
    """Deterministic stand-in — avoids loading the real ~420MB model in unit tests."""

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return [[float(i)] + [0.0] * (DIM - 1) for i, _ in enumerate(texts)]


def _manifest(report_id, company="Eternal Ltd", period="FY2026", n_chunks=2):
    chunks = [
        Chunk(chunk_id=f"{report_id}:1:{i}", text=f"chunk {i}", page=1, section=None, token_count=3)
        for i in range(n_chunks)
    ]
    return build_manifest(
        document_name=f"{report_id}.pdf",
        company=company,
        period=period,
        page_count=1,
        prose_chunks=chunks,
        tables=[],
        skipped_visuals=[],
        table_input_tokens=[],
        est_output_tokens=0,
    )


@pytest.fixture
def store():
    from qdrant_client import QdrantClient

    return QdrantVectorStore(client=QdrantClient(location=":memory:"))


def test_fresh_index_with_yes(store):
    code = run_phase2(_manifest("rA"), store, FakeEmbedder(), assume_yes=True, interactive=False)
    assert code == 0
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == {"rA"}
    assert store.client.count(COLLECTION_NAME).count == 2


def test_idempotent_refresh_same_report(store):
    run_phase2(_manifest("rA"), store, FakeEmbedder(), assume_yes=True, interactive=False)
    run_phase2(_manifest("rA"), store, FakeEmbedder(), assume_yes=True, interactive=False)
    # Same report_id → same chunk_ids → same point IDs → overwrite, no duplicates.
    assert store.client.count(COLLECTION_NAME).count == 2


def test_collision_non_interactive_without_replace_is_refused(store):
    run_phase2(_manifest("rA"), store, FakeEmbedder(), assume_yes=True, interactive=False)

    code = run_phase2(
        _manifest("rB"), store, FakeEmbedder(), assume_yes=True, replace=False, interactive=False
    )
    assert code == 2  # refused — needs --replace
    # Prior document untouched; the wrong one was NOT indexed.
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == {"rA"}


def test_collision_with_replace_swaps_the_document(store):
    run_phase2(_manifest("rA"), store, FakeEmbedder(), assume_yes=True, interactive=False)

    code = run_phase2(
        _manifest("rB"), store, FakeEmbedder(), replace=True, interactive=False
    )
    assert code == 0
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == {"rB"}  # rA replaced


def test_collision_interactive_yes_replaces(store):
    run_phase2(_manifest("rA"), store, FakeEmbedder(), assume_yes=True, interactive=False)

    code = run_phase2(
        _manifest("rB"), store, FakeEmbedder(), interactive=True, confirm=lambda _: True
    )
    assert code == 0
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == {"rB"}


def test_collision_interactive_no_aborts_intact(store):
    run_phase2(_manifest("rA"), store, FakeEmbedder(), assume_yes=True, interactive=False)

    code = run_phase2(
        _manifest("rB"), store, FakeEmbedder(), interactive=True, confirm=lambda _: False
    )
    assert code == 0  # deliberate abort
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == {"rA"}  # unchanged


def test_non_interactive_without_yes_is_refused(store):
    code = run_phase2(_manifest("rA"), store, FakeEmbedder(), assume_yes=False, interactive=False)
    assert code == 2
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == set()


def test_interactive_decline_makes_no_changes(store):
    code = run_phase2(
        _manifest("rA"), store, FakeEmbedder(), interactive=True, confirm=lambda _: False
    )
    assert code == 0
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == set()


def test_same_company_different_period_is_not_a_collision(store):
    run_phase2(_manifest("rA", period="FY2025"), store, FakeEmbedder(), assume_yes=True, interactive=False)
    # Same company, different period → independent document, no collision.
    code = run_phase2(_manifest("rB", period="FY2026"), store, FakeEmbedder(), assume_yes=True, interactive=False)
    assert code == 0
    assert store.existing_report_ids("Eternal Ltd", "FY2025") == {"rA"}
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == {"rB"}


def test_empty_manifest_is_clean_noop(store):
    code = run_phase2(_manifest("rA", n_chunks=0), store, FakeEmbedder(), assume_yes=True, interactive=False)
    assert code == 0
