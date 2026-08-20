from ingestion.extraction.pdf import _is_blank, _normalize_table, _table_to_markdown, scan_pdf


def test_normalize_table_strips_whitespace_and_replaces_none():
    rows = [["  Metric  ", None], [" 1 ", "2"]]
    assert _normalize_table(rows) == [["Metric", ""], ["1", "2"]]


def test_is_blank_true_for_all_empty_cells():
    assert _is_blank([["", ""], ["", ""]]) is True


def test_is_blank_false_when_any_cell_has_content():
    assert _is_blank([["", ""], ["", "x"]]) is False


def test_table_to_markdown_renders_header_and_rows():
    normalized = [["Metric", "FY24"], ["Revenue", "100"]]
    markdown = _table_to_markdown(normalized)
    assert markdown == "| Metric | FY24 |\n| --- | --- |\n| Revenue | 100 |"


def test_scan_pdf_against_synthetic_report(synthetic_pdf, capsys):
    result = scan_pdf(synthetic_pdf, report_id="testreport")

    assert result.document_name == synthetic_pdf.name
    assert result.page_count == 2

    # Page 1: prose only, no real tables.
    page_1 = next(p for p in result.pages if p.page == 1)
    assert "synthetic annual report" in page_1.text
    assert not any(t.page == 1 for t in result.tables)

    # Page 2: exactly one real table, with actual cell content, correctly ID'd.
    page_2_tables = [t for t in result.tables if t.page == 2]
    assert len(page_2_tables) == 1
    table = page_2_tables[0]
    assert table.table_id == "testreport:2:1"
    assert "Revenue" in table.markdown
    assert "120" in table.markdown

    # No blank grid structures should have been misclassified as real tables.
    assert all(t.markdown.strip() for t in result.tables)

    # Per-page report is printed as we go (§4 build-order requirement).
    printed = capsys.readouterr().out
    assert "Page 1:" in printed
    assert "Page 2:" in printed
