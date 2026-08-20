from ingestion.extraction.report_id import compute_report_id


def test_report_id_is_twelve_hex_chars(tmp_path):
    path = tmp_path / "a.pdf"
    path.write_bytes(b"some pdf bytes")
    report_id = compute_report_id(path)
    assert len(report_id) == 12
    assert all(c in "0123456789abcdef" for c in report_id)


def test_report_id_is_deterministic_for_same_content(tmp_path):
    path_a = tmp_path / "a.pdf"
    path_b = tmp_path / "b.pdf"
    path_a.write_bytes(b"identical content")
    path_b.write_bytes(b"identical content")
    assert compute_report_id(path_a) == compute_report_id(path_b)


def test_report_id_differs_for_different_content(tmp_path):
    path_a = tmp_path / "a.pdf"
    path_b = tmp_path / "b.pdf"
    path_a.write_bytes(b"content one")
    path_b.write_bytes(b"content two")
    assert compute_report_id(path_a) != compute_report_id(path_b)
