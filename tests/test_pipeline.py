import io
import uuid
from unittest.mock import MagicMock, patch

import fitz
import pytest
from docx import Document

from app.config import Settings
from app.pipeline.chunker import chunk_text
from app.pipeline.embedder import embed_texts, reset_embedder_cache
from app.pipeline.extractors import (
    ExtractionError,
    TextBlock,
    extract_text,
    split_legal_sections,
)
from app.pipeline.indexer import index_document_chunks, remove_document_vectors
from app.vector.qdrant import (
    ChunkRecord,
    chunk_point_id,
    delete_document_vectors,
    upsert_chunks,
)


def _make_pdf(text_by_page: dict[int, str]) -> bytes:
    document = fitz.open()
    for page_number in sorted(text_by_page):
        page = document.new_page()
        page.insert_text((72, 72), text_by_page[page_number])
    content = document.tobytes()
    document.close()
    return content


def _make_docx(paragraphs: list[str]) -> bytes:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class TestExtractors:
    def test_extract_pdf_text(self):
        content = _make_pdf({1: "Contrato de arrendamiento", 2: "Cláusula segunda"})
        blocks = extract_text(content, "application/pdf")

        assert len(blocks) == 2
        assert blocks[0].page == 1
        assert "Contrato" in blocks[0].text
        assert blocks[1].page == 2

    def test_extract_docx_text(self):
        content = _make_docx(["Artículo 1. Objeto", "El presente contrato regula..."])
        blocks = extract_text(content, None)

        assert len(blocks) == 1
        assert "Artículo 1" in blocks[0].text
        assert blocks[0].page is None

    def test_extract_plain_text(self):
        content = b"Hola mundo legal"
        blocks = extract_text(content, "text/plain")

        assert blocks == [TextBlock(text="Hola mundo legal", page=None)]

    def test_rejects_empty_content(self):
        with pytest.raises(ExtractionError, match="vacío"):
            extract_text(b"", "application/pdf")

    def test_rejects_unsupported_mime(self):
        with pytest.raises(ExtractionError, match="no soportado"):
            extract_text(b"\x89PNG\r\n", "image/png")

    def test_split_legal_sections(self):
        text = (
            "Introducción general.\n\n"
            "Artículo 1. Objeto\n"
            "Regula la relación contractual.\n\n"
            "Artículo 2. Duración\n"
            "Será de un año."
        )
        sections = split_legal_sections(text)

        assert any("Artículo 1" in section for section in sections)
        assert any("Artículo 2" in section for section in sections)


class TestChunker:
    def test_respects_paragraph_boundaries(self, settings: Settings):
        text = "Primer párrafo legal.\n\nSegundo párrafo legal."
        blocks = [TextBlock(text=text, page=1)]
        chunks = chunk_text(blocks, chunk_size=80, chunk_overlap=0, settings=settings)

        assert len(chunks) >= 1
        assert all(chunk.chunk_index == index for index, chunk in enumerate(chunks))

    def test_applies_overlap(self, settings: Settings):
        paragraph = "Palabra " * 120
        blocks = [TextBlock(text=paragraph.strip(), page=1)]
        chunks = chunk_text(blocks, chunk_size=200, chunk_overlap=40, settings=settings)

        assert len(chunks) > 1
        assert chunks[1].text.startswith(chunks[0].text[-40:].strip()[:20])

    def test_legal_section_starts_new_chunk_group(self, settings: Settings):
        text = (
            "Contexto inicial del expediente.\n\n"
            "Artículo 10. Responsabilidad\n"
            "El arrendador responderá por los daños causados."
        )
        blocks = [TextBlock(text=text, page=3)]
        chunks = chunk_text(blocks, chunk_size=512, chunk_overlap=0, settings=settings)

        assert len(chunks) >= 1
        assert chunks[0].page == 3
        assert "Artículo 10" in chunks[-1].text

    def test_rejects_invalid_overlap(self, settings: Settings):
        blocks = [TextBlock(text="Texto corto", page=1)]
        with pytest.raises(ValueError, match="chunk_overlap"):
            chunk_text(blocks, chunk_size=64, chunk_overlap=64, settings=settings)


class TestEmbedder:
    def test_embed_texts_uses_lazy_model(self, settings: Settings):
        reset_embedder_cache()
        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.1, 0.2], [0.3, 0.4]]

        with patch(
            "app.pipeline.embedder._get_model",
            return_value=mock_model,
        ):
            vectors = embed_texts(["uno", "dos"], settings=settings)

        assert vectors == [[0.1, 0.2], [0.3, 0.4]]
        mock_model.encode.assert_called_once()

    def test_embed_texts_empty_list(self):
        assert embed_texts([]) == []


class TestQdrantHelpers:
    def test_chunk_point_id_is_deterministic(self):
        document_id = str(uuid.uuid4())
        first = chunk_point_id(document_id, 0)
        second = chunk_point_id(document_id, 0)
        third = chunk_point_id(document_id, 1)

        assert first == second
        assert first != third

    def test_upsert_chunks_builds_points(self):
        client = MagicMock()
        document_id = str(uuid.uuid4())
        records = [
            ChunkRecord(
                case_id=str(uuid.uuid4()),
                document_id=document_id,
                chunk_index=0,
                text="Fragmento legal",
                page=1,
                vector=[0.1] * 768,
            )
        ]

        upsert_chunks(client, "case_document_chunks", records)

        client.upsert.assert_called_once()
        points = client.upsert.call_args.kwargs["points"]
        assert len(points) == 1
        assert points[0].id == chunk_point_id(document_id, 0)
        assert points[0].payload["text"] == "Fragmento legal"
        assert points[0].payload["page"] == 1

    def test_delete_document_vectors_filters_by_document(self):
        client = MagicMock()
        client.collection_exists.return_value = True
        document_id = str(uuid.uuid4())

        delete_document_vectors(client, "case_document_chunks", document_id)

        client.delete.assert_called_once()
        selector = client.delete.call_args.kwargs["points_selector"]
        assert selector.must[0].match.value == document_id

    def test_delete_document_vectors_skips_missing_collection(self):
        client = MagicMock()
        client.collection_exists.return_value = False

        delete_document_vectors(client, "case_document_chunks", str(uuid.uuid4()))

        client.delete.assert_not_called()


class TestIndexer:
    def test_index_document_chunks_delegates_to_qdrant(self, settings: Settings):
        client = MagicMock()
        case_id = str(uuid.uuid4())
        document_id = str(uuid.uuid4())

        with patch("app.pipeline.indexer.upsert_chunks") as mock_upsert:
            from app.pipeline.chunker import TextChunk

            chunks = [TextChunk(text="Texto", chunk_index=0, page=2)]
            vectors = [[0.0] * 768]
            index_document_chunks(
                client,
                case_id=case_id,
                document_id=document_id,
                chunks=chunks,
                vectors=vectors,
                settings=settings,
            )

        mock_upsert.assert_called_once()
        records = mock_upsert.call_args.args[2]
        assert records[0].case_id == case_id
        assert records[0].document_id == document_id

    def test_remove_document_vectors_delegates(self, settings: Settings):
        client = MagicMock()
        document_id = str(uuid.uuid4())

        with patch("app.pipeline.indexer.delete_document_vectors") as mock_delete:
            remove_document_vectors(client, document_id, settings=settings)

        mock_delete.assert_called_once_with(
            client,
            settings.qdrant_collection,
            document_id,
        )


class TestDocumentPipelineWorker:
    @pytest.mark.asyncio
    async def test_process_document_indexes_chunks(self, settings: Settings):
        document_id = str(uuid.uuid4())
        case_id = str(uuid.uuid4())
        pdf_content = _make_pdf({1: "Demanda principal del procedimiento civil."})

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={
                "id": document_id,
                "case_id": case_id,
                "storage_path": "user/case/doc.pdf",
                "mime_type": "application/pdf",
            }
        )
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data={}
        )

        mock_storage = MagicMock()
        mock_storage.download.return_value = pdf_content

        mock_qdrant = MagicMock()
        mock_qdrant.collection_exists.return_value = True

        with (
            patch(
                "app.workers.tasks.document_pipeline.get_supabase_admin",
                return_value=mock_client,
            ),
            patch(
                "app.workers.tasks.document_pipeline.get_qdrant_client",
                return_value=mock_qdrant,
            ),
            patch(
                "app.workers.tasks.document_pipeline.StorageService",
                return_value=mock_storage,
            ),
            patch(
                "app.workers.tasks.document_pipeline.remove_document_vectors",
            ) as mock_remove,
            patch(
                "app.workers.tasks.document_pipeline.ensure_collection",
            ),
            patch(
                "app.pipeline.embedder.embed_texts",
                return_value=[[0.0] * 768],
            ),
            patch(
                "app.workers.tasks.document_pipeline.index_document_chunks",
            ) as mock_index,
        ):
            from app.workers.tasks.document_pipeline import process_document

            result = await process_document({"job_try": 1}, document_id)

        assert result["status"] == "ready"
        assert result["chunk_count"] >= 1
        mock_remove.assert_called_once()
        mock_index.assert_called_once()
        mock_storage.download.assert_called_once_with("user/case/doc.pdf")

    @pytest.mark.asyncio
    async def test_process_document_not_found(self):
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )

        with patch(
            "app.workers.tasks.document_pipeline.get_supabase_admin",
            return_value=mock_client,
        ):
            from app.workers.tasks.document_pipeline import process_document

            result = await process_document({"job_try": 1}, str(uuid.uuid4()))

        assert result["status"] == "not_found"
