import uuid
from typing import Optional

from ingestion.interfaces.vector_store import VectorRecord, VectorStore

# §3e frozen decisions
COLLECTION_NAME = "annual_reports"     # single collection, payload-filtered
DENSE_VECTOR_NAME = "dense"            # named vector, so sparse can be added later
INDEXED_PAYLOAD_FIELDS = ("company", "period", "report_id")
# Fixed project namespace for deterministic uuid5 point IDs (do not change — it would
# re-key every previously indexed point).
REPORT_NAMESPACE = uuid.UUID("1b671a64-40d5-491e-99b0-da01ff1f3341")


def point_id_for(chunk_id: str) -> str:
    """Deterministic Qdrant point ID from a chunk_id string (§3e)."""
    return str(uuid.uuid5(REPORT_NAMESPACE, chunk_id))


class QdrantVectorStore(VectorStore):
    """Phase 2 vector store (§3e): embedded/in-process Qdrant, single collection,
    named dense vector, deterministic uuid5 point IDs, (company, period) filtering.

    Pass `client` to inject a test client (e.g. QdrantClient(location=":memory:"));
    otherwise an on-disk embedded client is created at `path`."""

    def __init__(self, path: str = "qdrant_data", client=None) -> None:
        if client is None:
            from qdrant_client import QdrantClient

            client = QdrantClient(path=path)
        self.client = client

    def _ensure_collection(self, vector_size: int) -> None:
        from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

        if self.client.collection_exists(COLLECTION_NAME):
            return
        self.client.create_collection(
            COLLECTION_NAME,
            vectors_config={DENSE_VECTOR_NAME: VectorParams(size=vector_size, distance=Distance.COSINE)},
        )
        for field in INDEXED_PAYLOAD_FIELDS:
            try:
                self.client.create_payload_index(
                    COLLECTION_NAME, field_name=field, field_schema=PayloadSchemaType.KEYWORD
                )
            except Exception:
                # Payload indexes are a server-side performance optimization; the
                # embedded/local backend filters by full scan regardless, so a
                # no-op/unsupported index call here is safe to ignore.
                pass

    def _company_period_filter(self, company: str, period: str):
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        return Filter(
            must=[
                FieldCondition(key="company", match=MatchValue(value=company)),
                FieldCondition(key="period", match=MatchValue(value=period)),
            ]
        )

    def existing_report_ids(self, company: str, period: str) -> set[str]:
        """report_ids already indexed for this (company, period). Empty if none.

        Drives the §3e collision guard: same report_id = idempotent refresh; a
        different one = a different document already occupies this (company, period)."""
        if not self.client.collection_exists(COLLECTION_NAME):
            return set()
        flt = self._company_period_filter(company, period)
        ids: set[str] = set()
        offset = None
        while True:
            points, offset = self.client.scroll(
                COLLECTION_NAME,
                scroll_filter=flt,
                with_payload=["report_id"],
                with_vectors=False,
                limit=256,
                offset=offset,
            )
            ids.update(p.payload.get("report_id") for p in points)
            if offset is None:
                break
        return ids

    def delete_document(self, company: str, period: str) -> None:
        """Delete all points for a logical document (company, period) — the §3e replace step."""
        if not self.client.collection_exists(COLLECTION_NAME):
            return
        from qdrant_client.models import FilterSelector

        self.client.delete(
            COLLECTION_NAME,
            points_selector=FilterSelector(filter=self._company_period_filter(company, period)),
        )

    def index(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        from qdrant_client.models import PointStruct

        self._ensure_collection(vector_size=len(records[0].vector))
        points = [
            PointStruct(
                id=point_id_for(r.metadata["chunk_id"]),
                vector={DENSE_VECTOR_NAME: r.vector},
                payload={**r.metadata, "text": r.content},
            )
            for r in records
        ]
        self.client.upsert(COLLECTION_NAME, points=points)
