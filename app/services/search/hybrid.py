"""Hybrid search: combine Postgres FTS (sparse) and Qdrant (dense) via RRF."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedResult:
    document_id: str
    chunk_index: int
    score: float
    source: str


def reciprocal_rank_fusion(
    *ranked_lists: list[RankedResult],
    k: int = 60,
) -> list[RankedResult]:
    """Fuse multiple ranked lists using RRF (Cormack et al.)."""
    scores: dict[tuple[str, int], float] = {}
    sources: dict[tuple[str, int], str] = {}

    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            key = (item.document_id, item.chunk_index)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            sources[key] = item.source

    fused = [
        RankedResult(
            document_id=key[0],
            chunk_index=key[1],
            score=score,
            source=sources[key],
        )
        for key, score in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    ]
    return fused
