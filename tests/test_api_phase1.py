import json
import time

import pytest
from fastapi.testclient import TestClient

from api.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate the default ./manifests/ output into a tmp cwd.
    monkeypatch.chdir(tmp_path)
    return TestClient(app)


def _poll(client, job_id, timeout=60.0):
    """Poll GET /jobs/{id} until the job leaves the running/pending states."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/jobs/{job_id}").json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.1)
    raise AssertionError("job did not finish in time")


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_phase1_scan_produces_manifest_and_cost_summary(client, synthetic_pdf, tmp_path):
    resp = client.post(
        "/phase1",
        json={
            "file_path": str(synthetic_pdf),
            "company": "Eternal Ltd",
            "period": "FY2026",
            "report_id": "apitest",
        },
    )
    assert resp.status_code == 202
    created = resp.json()
    assert created["status"] == "registered"

    result = _poll(client, created["job_id"])
    assert result["status"] == "done", result.get("error")

    r = result["result"]
    assert r["report_id"] == "apitest"
    assert r["manifest_file"] == "apitest.json"

    # Manifest was persisted where Step 2 will look for it.
    manifest_path = tmp_path / "manifests" / "apitest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())

    # Cost summary numbers match the persisted manifest.
    cs = r["cost_summary"]
    assert cs["company"] == "Eternal Ltd"
    assert cs["period"] == "FY2026"
    assert cs["page_count"] == data["page_count"] == 2
    assert cs["prose_chunks"] == len(data["prose_chunks"])
    assert cs["tables"] == len(data["tables"])
    assert cs["skipped_visuals"] == len(data["skipped_visuals"])
    assert cs["table_input_tokens_total"] == data["cost_estimate"]["table_input_tokens_total"]


def test_phase1_rejects_non_pdf_path(client):
    resp = client.post(
        "/phase1",
        json={"file_path": "/tmp/not_a_pdf.txt", "company": "X", "period": "FY2026"},
    )
    assert resp.status_code == 400


def test_phase1_rejects_missing_file(client, tmp_path):
    resp = client.post(
        "/phase1",
        json={"file_path": str(tmp_path / "does_not_exist.pdf"), "company": "X", "period": "FY2026"},
    )
    assert resp.status_code == 400


def test_unknown_job_id_is_404(client):
    assert client.get("/jobs/nope").status_code == 404
