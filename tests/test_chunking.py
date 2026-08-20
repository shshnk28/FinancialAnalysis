from ingestion.extraction.chunking import chunk_prose
from common.config.embedder_profile import ACTIVE_PROFILE
from ingestion.extraction.pdf import PageExtraction


def test_chunk_prose_produces_chunk_id_scheme_report_id_page_index():
    pages = [PageExtraction(page=3, text="hello world " * 20)]
    chunks = chunk_prose(pages, ACTIVE_PROFILE, report_id="abc123")
    assert all(c.chunk_id.startswith("abc123:3:") for c in chunks)
    assert [c.chunk_id for c in chunks] == [f"abc123:3:{i}" for i in range(len(chunks))]


def test_chunk_prose_leaves_section_none_in_phase_1():
    pages = [PageExtraction(page=1, text="some prose text")]
    chunks = chunk_prose(pages, ACTIVE_PROFILE, report_id="abc123")
    assert all(c.section is None for c in chunks)


def test_chunk_prose_skips_blank_pages():
    pages = [
        PageExtraction(page=1, text="   \n  "),
        PageExtraction(page=2, text="real content here"),
    ]
    chunks = chunk_prose(pages, ACTIVE_PROFILE, report_id="abc123")
    assert all(c.page == 2 for c in chunks)


def test_chunk_prose_stays_within_configured_chunk_size():
    # A large body of text should split into multiple chunks, each within
    # a small headroom of the configured chunk_size (never near max_input_tokens).
    long_text = "The quick brown fox jumps over the lazy dog. " * 500
    pages = [PageExtraction(page=1, text=long_text)]
    chunks = chunk_prose(pages, ACTIVE_PROFILE, report_id="abc123")

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.token_count <= ACTIVE_PROFILE.chunk_size + 10  # small special-token headroom
        assert chunk.token_count < ACTIVE_PROFILE.max_input_tokens
        assert chunk.token_count == len(ACTIVE_PROFILE.tokenizer.encode(chunk.text))


def test_chunk_prose_restarts_index_per_page():
    pages = [
        PageExtraction(page=1, text="first page text " * 200),
        PageExtraction(page=2, text="second page text " * 200),
    ]
    chunks = chunk_prose(pages, ACTIVE_PROFILE, report_id="abc123")
    page_1_indices = [int(c.chunk_id.split(":")[-1]) for c in chunks if c.page == 1]
    page_2_indices = [int(c.chunk_id.split(":")[-1]) for c in chunks if c.page == 2]
    assert page_1_indices[0] == 0
    assert page_2_indices[0] == 0
