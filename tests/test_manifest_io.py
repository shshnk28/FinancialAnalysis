import json
from dataclasses import asdict

from common.manifest import build_manifest, load_manifest
from common.models import Chunk, SkippedVisual, TableGrid


def _sample_manifest():
    return build_manifest(
        document_name="report.pdf",
        company="Eternal Ltd",
        period="FY2026",
        page_count=2,
        prose_chunks=[
            Chunk(chunk_id="r:1:0", text="hello", page=1, section=None, token_count=1),
            Chunk(chunk_id="r:1:1", text="world", page=1, section=None, token_count=1),
        ],
        tables=[TableGrid(table_id="r:2:1", page=2, markdown="| a |\n| --- |\n| 1 |")],
        skipped_visuals=[
            SkippedVisual(page=1, visual_type="image", width=10.0, height=20.0),
            SkippedVisual(page=3, visual_type="vector_graphic", curve_count=42),
        ],
        table_input_tokens=[42],
        est_output_tokens=150,
    )


def test_load_manifest_round_trips(tmp_path):
    original = _sample_manifest()
    path = tmp_path / "m.json"
    path.write_text(json.dumps(asdict(original), indent=2))

    loaded = load_manifest(path)

    # Full structural equality — nested Chunk/TableGrid/SkippedVisual/CostEstimate reconstructed.
    assert loaded == original


def test_load_manifest_reconstructs_nested_dataclass_types(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps(asdict(_sample_manifest()), indent=2))

    loaded = load_manifest(path)

    assert all(isinstance(c, Chunk) for c in loaded.prose_chunks)
    assert all(isinstance(t, TableGrid) for t in loaded.tables)
    assert all(isinstance(v, SkippedVisual) for v in loaded.skipped_visuals)
    assert loaded.company == "Eternal Ltd"
    assert loaded.period == "FY2026"
