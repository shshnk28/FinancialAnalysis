import json
import sys

from ingestion.cli import main


def test_cli_runs_end_to_end_and_prints_consent_summary(synthetic_pdf, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["ingest-phase1", str(synthetic_pdf)])
    main()

    printed = capsys.readouterr().out
    assert "PHASE 1 SCAN COMPLETE" in printed
    assert "No LLM or embedding calls made" in printed


def test_cli_json_out_writes_manifest_with_no_phase_2_content(synthetic_pdf, tmp_path, monkeypatch):
    json_path = tmp_path / "manifest.json"
    monkeypatch.setattr(
        sys, "argv", ["ingest-phase1", str(synthetic_pdf), "--json-out", str(json_path)]
    )
    main()

    data = json.loads(json_path.read_text())
    assert data["document_name"] == synthetic_pdf.name
    assert data["page_count"] == 2
    assert "cost_estimate" in data

    # Chunks and tables carry no embeddings or LLM-generated summaries (Phase 1 contract).
    for chunk in data["prose_chunks"]:
        assert set(chunk.keys()) == {"chunk_id", "text", "page", "section", "token_count"}
    for table in data["tables"]:
        assert set(table.keys()) == {"table_id", "page", "markdown"}


def test_cli_accepts_report_id_override(synthetic_pdf, tmp_path, monkeypatch):
    json_path = tmp_path / "manifest.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest-phase1", str(synthetic_pdf), "--report-id", "fixedid", "--json-out", str(json_path)],
    )
    main()

    data = json.loads(json_path.read_text())
    assert all(c["chunk_id"].startswith("fixedid:") for c in data["prose_chunks"])
    assert all(t["table_id"].startswith("fixedid:") for t in data["tables"])
