from dataclasses import dataclass

from app.config import Settings, get_settings
from app.pipeline.extractors import TextBlock, split_legal_sections


@dataclass(frozen=True)
class TextChunk:
    text: str
    chunk_index: int
    page: int | None


def chunk_text(
    blocks: list[TextBlock],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    settings: Settings | None = None,
) -> list[TextChunk]:
    settings = settings or get_settings()
    size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap

    if size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("chunk_overlap must be non-negative")
    if overlap >= size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    segments: list[tuple[str, int | None]] = []
    for block in blocks:
        for section in split_legal_sections(block.text):
            segments.extend(
                _split_segment(section, block.page, size),
            )

    if not segments:
        return []

    merged = _merge_segments(segments, size)
    return _apply_overlap(merged, size, overlap)


def _split_segment(
    text: str,
    page: int | None,
    chunk_size: int,
) -> list[tuple[str, int | None]]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return []

    pieces: list[tuple[str, int | None]] = []
    for paragraph in paragraphs:
        if len(paragraph) <= chunk_size:
            pieces.append((paragraph, page))
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + chunk_size, len(paragraph))
            if end < len(paragraph):
                split_at = paragraph.rfind(" ", start, end)
                if split_at > start:
                    end = split_at
            piece = paragraph[start:end].strip()
            if piece:
                pieces.append((piece, page))
            if end >= len(paragraph):
                break
            start = max(end, start + 1)

    return pieces


def _merge_segments(
    segments: list[tuple[str, int | None]],
    chunk_size: int,
) -> list[tuple[str, int | None]]:
    merged: list[tuple[str, int | None]] = []
    current: list[str] = []
    current_page: int | None = None
    current_len = 0

    for text, page in segments:
        separator = 2 if current else 0
        projected = current_len + separator + len(text)
        if current and projected > chunk_size:
            merged.append(("\n\n".join(current), current_page))
            current = [text]
            current_page = page
            current_len = len(text)
            continue

        if current:
            current.append(text)
            current_len = projected
            if current_page is None:
                current_page = page
        else:
            current = [text]
            current_page = page
            current_len = len(text)

    if current:
        merged.append(("\n\n".join(current), current_page))

    return merged


def _apply_overlap(
    chunks: list[tuple[str, int | None]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    if chunk_overlap == 0 or len(chunks) <= 1:
        return [
            TextChunk(text=text, chunk_index=index, page=page)
            for index, (text, page) in enumerate(chunks)
        ]

    overlapped: list[TextChunk] = []
    for index, (text, page) in enumerate(chunks):
        if index == 0:
            overlapped.append(TextChunk(text=text, chunk_index=index, page=page))
            continue

        previous_text = chunks[index - 1][0]
        prefix = previous_text[-chunk_overlap:].strip()
        combined = f"{prefix}\n\n{text}" if prefix else text
        if len(combined) > chunk_size:
            combined = combined[-chunk_size:]
        overlapped.append(TextChunk(text=combined, chunk_index=index, page=page))

    return overlapped
