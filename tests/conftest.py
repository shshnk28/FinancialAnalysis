from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def synthetic_pdf(tmp_path_factory) -> Path:
    """A tiny 2-page PDF: page 1 is prose, page 2 is a real bordered table.

    Built with reportlab rather than shipping a binary fixture, so tests stay
    fast, deterministic, and don't depend on the large real sample PDF.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

    path = tmp_path_factory.mktemp("fixtures") / "synthetic_report.pdf"
    styles = getSampleStyleSheet()

    prose = (
        "This is a synthetic annual report used for testing the Phase 1 "
        "ingestion pipeline. It contains enough words to exercise the chunker. "
    ) * 15

    table_data = [
        ["Metric", "FY24", "FY25"],
        ["Revenue", "100", "120"],
        ["Profit", "10", "15"],
    ]
    table = Table(table_data)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))

    doc = SimpleDocTemplate(str(path), pagesize=letter)
    doc.build([Paragraph(prose, styles["Normal"]), PageBreak(), table])

    return path
