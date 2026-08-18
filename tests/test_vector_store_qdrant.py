import pytest

from ingestion.interfaces.vector_store import VectorRecord
from ingestion.vector_store_qdrant import COLLECTION_NAME, point_id_for


@pytest.fixture
def store():
    from qdrant_client import QdrantClient

    from ingestion.vector_store_qdrant import QdrantVectorStore

    return QdrantVectorStore(client=QdrantClient(location=":memory:"))


def _record(chunk_id, report_id, company="Eternal Ltd", period="FY2026", dim=8):
    return VectorRecord(
        vector=[0.1] * dim,
        content=f"text for {chunk_id}",
        metadata={
            "chunk_id": chunk_id,
            "page": 1,
            "section": None,
            "report_id": report_id,
            "document_name": "report.pdf",
            "company": company,
            "period": period,
        },
    )


def test_point_id_is_deterministic():
    assert point_id_for("r:1:0") == point_id_for("r:1:0")
    assert point_id_for("r:1:0") != point_id_for("r:1:1")


def test_index_then_query_existing_report_ids(store):
    store.index([_record("rA:1:0", "rA"), _record("rA:1:1", "rA")])
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == {"rA"}
    assert store.existing_report_ids("Other Co", "FY2026") == set()


def test_reindexing_identical_chunk_is_idempotent(store):
    store.index([_record("rA:1:0", "rA")])
    store.index([_record("rA:1:0", "rA")])  # same chunk_id → same point ID → overwrite
    assert store.client.count(COLLECTION_NAME).count == 1


def test_different_report_for_same_company_period_coexists_until_replaced(store):
    store.index([_record("rA:1:0", "rA")])
    store.index([_record("rB:1:0", "rB")])  # different doc, same (company, period)
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == {"rA", "rB"}


def test_delete_document_removes_only_that_company_period(store):
    store.index([_record("rA:1:0", "rA", company="Eternal Ltd", period="FY2026")])
    store.index([_record("rC:1:0", "rC", company="Other Co", period="FY2026")])

    store.delete_document("Eternal Ltd", "FY2026")

    assert store.existing_report_ids("Eternal Ltd", "FY2026") == set()
    assert store.existing_report_ids("Other Co", "FY2026") == {"rC"}


def test_payload_carries_text_and_metadata(store):
    store.index([_record("rA:1:0", "rA")])
    points, _ = store.client.scroll(COLLECTION_NAME, with_payload=True, limit=10)
    payload = points[0].payload
    assert payload["text"] == "text for rA:1:0"
    assert payload["company"] == "Eternal Ltd"
    assert payload["chunk_id"] == "rA:1:0"


def test_empty_index_is_noop(store):
    store.index([])  # must not create a collection or raise
    assert store.existing_report_ids("Eternal Ltd", "FY2026") == set()
