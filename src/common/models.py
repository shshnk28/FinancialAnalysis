from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Chunk:
    chunk_id: str  # "report_id:page:chunk_index"
    text: str
    page: int
    section: Optional[str]
    token_count: int


@dataclass
class TableGrid:
    table_id: str  # "report_id:page:table_index"
    page: int
    markdown: str


@dataclass
class SkippedVisual:
    page: int
    visual_type: Literal["image", "vector_graphic", "empty_table_structure"]
    width: Optional[float] = None
    height: Optional[float] = None
    curve_count: Optional[int] = None


@dataclass
class CostEstimate:
    table_input_tokens_total: int
    est_output_tokens_total: int
    input_cost_usd: float
    output_cost_usd_min: float
    output_cost_usd_max: float
    total_cost_usd_min: float
    total_cost_usd_max: float
    pricing_note: str


@dataclass
class IngestionManifest:
    document_name: str
    company: str        # user-provided document identity (for per-company retrieval filtering)
    period: str         # user-provided reporting period, e.g. "FY2026"
    page_count: int
    prose_chunks: list[Chunk] = field(default_factory=list)
    tables: list[TableGrid] = field(default_factory=list)
    skipped_visuals: list[SkippedVisual] = field(default_factory=list)
    table_input_tokens: list[int] = field(default_factory=list)
    est_output_tokens: int = 0
    cost_estimate: Optional[CostEstimate] = None
