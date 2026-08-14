from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from ingestion.models import SkippedVisual, TableGrid

DENSE_CURVE_THRESHOLD = 20


@dataclass
class PageExtraction:
    page: int
    text: str


@dataclass
class ExtractionResult:
    document_name: str
    page_count: int
    pages: list[PageExtraction] = field(default_factory=list)
    tables: list[TableGrid] = field(default_factory=list)
    skipped_visuals: list[SkippedVisual] = field(default_factory=list)


def _normalize_table(rows: list[list[str | None]]) -> list[list[str]]:
    return [[(cell or "").strip() for cell in row] for row in rows]


def _is_blank(normalized_rows: list[list[str]]) -> bool:
    return all(cell == "" for row in normalized_rows for cell in row)


def _table_to_markdown(normalized_rows: list[list[str]]) -> str:
    header, *body = normalized_rows
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def scan_pdf(path: Path, report_id: str) -> ExtractionResult:
    result = ExtractionResult(document_name=path.name, page_count=0)

    with pdfplumber.open(path) as pdf:
        result.page_count = len(pdf.pages)
        table_index = 0

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            result.pages.append(PageExtraction(page=page_num, text=text))

            page_tables = page.extract_tables()
            blank_table_count = 0
            for rows in page_tables:
                if not rows:
                    continue
                normalized = _normalize_table(rows)
                if _is_blank(normalized):
                    blank_table_count += 1
                    result.skipped_visuals.append(
                        SkippedVisual(page=page_num, visual_type="empty_table_structure")
                    )
                    continue
                table_index += 1
                result.tables.append(
                    TableGrid(
                        table_id=f"{report_id}:{page_num}:{table_index}",
                        page=page_num,
                        markdown=_table_to_markdown(normalized),
                    )
                )
            real_table_count = len(page_tables) - blank_table_count

            for image in page.images:
                result.skipped_visuals.append(
                    SkippedVisual(
                        page=page_num,
                        visual_type="image",
                        width=image.get("width"),
                        height=image.get("height"),
                    )
                )

            curve_count = len(page.curves)
            dense_curves = curve_count > DENSE_CURVE_THRESHOLD
            if dense_curves:
                result.skipped_visuals.append(
                    SkippedVisual(page=page_num, visual_type="vector_graphic", curve_count=curve_count)
                )

            word_count = len(text.split())
            print(
                f"Page {page_num}: {word_count} words prose, {real_table_count} table(s), "
                f"{blank_table_count} blank table structure(s) (skipped), "
                f"{len(page.images)} image(s), {1 if dense_curves else 0} dense vector region(s)"
            )

    return result
