import json
import sys

import pytest

from ingestion.cli import main

_IDENTITY = ["--company", "Eternal Ltd", "--period", "FY2026"]


def test_cli_runs_end_to_end_and_prints_consent_summary(synthetic_pdf, tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)  # isolate default ./manifests/ output from the repo
    monkeypatch.setattr(sys, "argv", ["ingest-phase1", str(synthetic_pdf), *_IDENTITY])
    main()

    printed = capsys.readouterr().out
    assert "PHASE 1 SCAN COMPLETE" in printed
    assert "No LLM or embedding calls made" in printed
    # Identity is surfaced in the consent summary for the user to confirm.
    assert "Eternal Ltd" in printed
    assert "FY2026" in printed


def test_cli_json_out_writes_manifest_with_no_phase_2_content(synthetic_pdf, tmp_path, monkeypatch):
    json_path = tmp_path / "manifest.json"
    monkeypatch.setattr(
        sys, "argv", ["ingest-phase1", str(synthetic_pdf), *_IDENTITY, "--json-out", str(json_path)]
    )
    main()

    data = json.loads(json_path.read_text())
    assert data["document_name"] == synthetic_pdf.name
    assert data["company"] == "Eternal Ltd"
    assert data["period"] == "FY2026"
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
        ["ingest-phase1", str(synthetic_pdf), *_IDENTITY, "--report-id", "fixedid", "--json-out", str(json_path)],
    )
    main()

    data = json.loads(json_path.read_text())
    assert all(c["chunk_id"].startswith("fixedid:") for c in data["prose_chunks"])
    assert all(t["table_id"].startswith("fixedid:") for t in data["tables"])


def test_cli_requires_company_and_period(synthetic_pdf, monkeypatch):
    # Identity is mandatory — argparse should exit non-zero when it's missing.
    monkeypatch.setattr(sys, "argv", ["ingest-phase1", str(synthetic_pdf)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0


def test_cli_persists_manifest_to_default_path(synthetic_pdf, tmp_path, capsys, monkeypatch):
    # With no --json-out, Phase 1 must persist to ./manifests/<report_id>.json by default (§1a).
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["ingest-phase1", str(synthetic_pdf), *_IDENTITY, "--report-id", "abc123"]
    )
    main()

    default_path = tmp_path / "manifests" / "abc123.json"
    assert default_path.exists()
    data = json.loads(default_path.read_text())
    assert data["company"] == "Eternal Ltd"
    assert data["period"] == "FY2026"

    # The printed output points the user at the exact manifest path for Phase 2.
    printed = capsys.readouterr().out
    assert "manifests/abc123.json" in printed  # relative path, as printed
    assert "ingest-phase2" in printed
