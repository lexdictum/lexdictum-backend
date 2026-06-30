"""Hybrid search RRF fusion tests."""

from app.services.search.hybrid import RankedResult, reciprocal_rank_fusion


def test_reciprocal_rank_fusion_combines_lists():
    vector = [
        RankedResult("doc-a", 0, 0.9, "vector"),
        RankedResult("doc-b", 0, 0.8, "vector"),
    ]
    bm25 = [
        RankedResult("doc-b", 0, 1.0, "fts"),
        RankedResult("doc-c", 0, 0.7, "fts"),
    ]

    fused = reciprocal_rank_fusion(vector, bm25)

    assert len(fused) == 3
    assert fused[0].document_id == "doc-b"
    assert fused[0].score > fused[1].score


def test_reciprocal_rank_fusion_respects_k_parameter():
    vector = [RankedResult("doc-a", 0, 0.9, "vector")]
    fts = [RankedResult("doc-b", 0, 0.8, "fts")]

    fused_default = reciprocal_rank_fusion(vector, fts)
    fused_high_k = reciprocal_rank_fusion(vector, fts, k=120)

    assert len(fused_default) == 2
    assert fused_default[0].score > fused_high_k[0].score


def test_reciprocal_rank_fusion_deduplicates_by_chunk():
    vector = [
        RankedResult("doc-a", 0, 0.9, "vector"),
        RankedResult("doc-a", 1, 0.7, "vector"),
    ]
    fts = [
        RankedResult("doc-a", 0, 0.95, "fts"),
        RankedResult("doc-a", 2, 0.6, "fts"),
    ]

    fused = reciprocal_rank_fusion(vector, fts)

    keys = {(item.document_id, item.chunk_index) for item in fused}
    assert len(keys) == len(fused)
    assert fused[0].document_id == "doc-a"
    assert fused[0].chunk_index == 0


def test_reciprocal_rank_fusion_single_list():
    vector = [
        RankedResult("doc-a", 0, 0.9, "vector"),
        RankedResult("doc-b", 0, 0.8, "vector"),
    ]

    fused = reciprocal_rank_fusion(vector)

    assert [item.document_id for item in fused] == ["doc-a", "doc-b"]
