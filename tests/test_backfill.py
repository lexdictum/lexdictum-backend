"""Core backfill logic tests (no external services)."""

from unittest.mock import MagicMock, patch

from app.pipeline.chunker import TextChunk
from scripts.backfill_document_chunks import (
    BackfillStats,
    backfill_document,
    fetch_qdrant_chunks,
)


class TestFetchQdrantChunks:
    def test_scrolls_qdrant_payloads(self):
        qdrant = MagicMock()
        qdrant.collection_exists.return_value = True
        point = MagicMock()
        point.payload = {
            "chunk_index": 0,
            "text": "Fragmento legal",
            "page": 2,
        }
        qdrant.scroll.side_effect = [([point], None)]

        chunks = fetch_qdrant_chunks(qdrant, "case_document_chunks", "doc-1")

        assert len(chunks) == 1
        assert chunks[0].text == "Fragmento legal"
        assert chunks[0].chunk_index == 0
        assert chunks[0].page == 2

    def test_returns_empty_when_collection_missing(self):
        qdrant = MagicMock()
        qdrant.collection_exists.return_value = False

        assert fetch_qdrant_chunks(qdrant, "missing", "doc-1") == []


class TestBackfillDocument:
    def test_dry_run_reports_missing_chunks(self):
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        qdrant = MagicMock()

        document = {"id": "doc-1", "case_id": "case-1"}
        chunks = [TextChunk(text="Texto", chunk_index=0, page=1)]

        with patch(
            "scripts.backfill_document_chunks.fetch_existing_chunk_indices",
            return_value=set(),
        ), patch(
            "scripts.backfill_document_chunks.fetch_qdrant_chunks",
            return_value=chunks,
        ):
            inserted, changed = backfill_document(
                client,
                qdrant,
                "case_document_chunks",
                document,
                dry_run=True,
            )

        assert inserted == 1
        assert changed is True
        client.table.return_value.insert.assert_not_called()

    def test_skips_when_chunks_already_present(self):
        client = MagicMock()
        qdrant = MagicMock()
        document = {"id": "doc-1", "case_id": "case-1"}
        chunks = [TextChunk(text="Texto", chunk_index=0, page=1)]

        with patch(
            "scripts.backfill_document_chunks.fetch_existing_chunk_indices",
            return_value={0},
        ), patch(
            "scripts.backfill_document_chunks.fetch_qdrant_chunks",
            return_value=chunks,
        ):
            inserted, changed = backfill_document(
                client,
                qdrant,
                "case_document_chunks",
                document,
                dry_run=False,
            )

        assert inserted == 0
        assert changed is False


class TestRunBackfillDryRun:
    def test_dry_run_does_not_persist(self):
        documents = [{"id": "doc-1", "case_id": "case-1", "chunk_count": 1}]

        with (
            patch(
                "scripts.backfill_document_chunks.get_supabase_admin",
                return_value=MagicMock(),
            ),
            patch(
                "scripts.backfill_document_chunks.get_qdrant_client",
                return_value=MagicMock(),
            ),
            patch(
                "scripts.backfill_document_chunks.fetch_ready_documents",
                return_value=documents,
            ),
            patch(
                "scripts.backfill_document_chunks.backfill_document",
                return_value=(1, True),
            ) as mock_backfill,
            patch(
                "scripts.backfill_document_chunks.persist_document_chunks",
            ) as mock_persist,
        ):
            from scripts.backfill_document_chunks import run_backfill

            stats = run_backfill(dry_run=True)

        assert isinstance(stats, BackfillStats)
        assert stats.documents_scanned == 1
        assert stats.documents_backfilled == 1
        assert stats.chunks_inserted == 1
        mock_backfill.assert_called_once()
        mock_persist.assert_not_called()
