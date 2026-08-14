from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingestion.config.embedder_profile import EmbedderProfile
from ingestion.extraction import PageExtraction
from ingestion.models import Chunk


def chunk_prose(pages: list[PageExtraction], profile: EmbedderProfile, report_id: str) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tokenizer=profile.tokenizer,
        chunk_size=profile.chunk_size,
        chunk_overlap=profile.overlap_tokens,
    )

    chunks: list[Chunk] = []
    for page in pages:
        if not page.text.strip():
            continue
        for idx, piece in enumerate(splitter.split_text(page.text)):
            chunks.append(
                Chunk(
                    chunk_id=f"{report_id}:{page.page}:{idx}",
                    text=piece,
                    page=page.page,
                    section=None,
                    token_count=len(profile.tokenizer.encode(piece)),
                )
            )
    return chunks
