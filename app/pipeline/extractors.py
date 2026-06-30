import io
import re
from dataclasses import dataclass

from app.core.exceptions import LexDictumError

PDF_MIME = "application/pdf"
DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
TEXT_MIME = "text/plain"
JPEG_MIME = "image/jpeg"
PNG_MIME = "image/png"
WEBP_MIME = "image/webp"

IMAGE_MIME_TYPES = frozenset({JPEG_MIME, PNG_MIME, WEBP_MIME})

LEGAL_SECTION_PATTERN = re.compile(
    r"(?m)^(?:"
    r"Art(?:ículo|\.)?\s*\d+"
    r"|Cap(?:ítulo|\.)?\s+[IVXLCDM\d]+"
    r"|Sección\s+\d+"
    r"|Título\s+[IVXLCDM\d]+"
    r"|Disposición\s+(?:adicional|transitoria|final|derogatoria)"
    r")\b.*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextBlock:
    text: str
    page: int | None = None


class ExtractionError(LexDictumError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


def extract_text(
    content: bytes,
    mime_type: str | None,
    *,
    ocr_enabled: bool = False,
    tesseract_lang: str = "spa",
) -> list[TextBlock]:
    if not content:
        raise ExtractionError("El documento está vacío")

    mime = (mime_type or "").lower()
    if mime == PDF_MIME or content.startswith(b"%PDF"):
        return _extract_pdf(content, ocr_enabled=ocr_enabled, tesseract_lang=tesseract_lang)
    if mime == DOCX_MIME or content.startswith(b"PK\x03\x04"):
        return _extract_docx(content)
    if mime.startswith("text/") or mime == TEXT_MIME:
        return _extract_plain_text(content)
    if mime in IMAGE_MIME_TYPES:
        if not ocr_enabled:
            raise ExtractionError(
                "Las imágenes requieren OCR. Active OCR_ENABLED para procesarlas."
            )
        return _extract_image(content, tesseract_lang=tesseract_lang)

    raise ExtractionError(
        "Tipo de archivo no soportado para extracción de texto. Use PDF o DOCX."
    )


def _extract_pdf(
    content: bytes,
    *,
    ocr_enabled: bool,
    tesseract_lang: str,
) -> list[TextBlock]:
    import fitz

    blocks: list[TextBlock] = []
    with fitz.open(stream=content, filetype="pdf") as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                blocks.append(TextBlock(text=text, page=page_number))
            elif ocr_enabled:
                ocr_text = _ocr_pdf_page(page, tesseract_lang)
                if ocr_text:
                    blocks.append(TextBlock(text=ocr_text, page=page_number))

    if not blocks:
        if ocr_enabled:
            raise ExtractionError(
                "No se pudo extraer texto del PDF, ni siquiera con OCR."
            )
        raise ExtractionError("No se pudo extraer texto del PDF")

    return blocks


def _ocr_pdf_page(page, lang: str) -> str:
    pixmap = page.get_pixmap()
    return _run_tesseract(pixmap.tobytes("png"), lang)


def _extract_image(content: bytes, *, tesseract_lang: str) -> list[TextBlock]:
    text = _run_tesseract(content, tesseract_lang)
    if not text:
        raise ExtractionError("No se pudo extraer texto de la imagen con OCR.")
    return [TextBlock(text=text, page=1)]


def _run_tesseract(image_bytes: bytes, lang: str) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ExtractionError(
            "OCR no está disponible. Instale pytesseract y Pillow "
            "(uv sync --extra ocr) o desactive OCR_ENABLED."
        ) from exc

    image = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(image, lang=lang).strip()


def _extract_docx(content: bytes) -> list[TextBlock]:
    from docx import Document

    document = Document(io.BytesIO(content))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    text = "\n\n".join(paragraph for paragraph in paragraphs if paragraph)

    if not text:
        raise ExtractionError("No se pudo extraer texto del DOCX")

    return [TextBlock(text=text, page=None)]


def _extract_plain_text(content: bytes) -> list[TextBlock]:
    for encoding in ("utf-8", "latin-1"):
        try:
            text = content.decode(encoding).strip()
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ExtractionError("No se pudo decodificar el texto plano")

    if not text:
        raise ExtractionError("El documento de texto está vacío")

    return [TextBlock(text=text, page=None)]


def split_legal_sections(text: str) -> list[str]:
    """Split text at legal section headings while preserving boundaries."""
    matches = list(LEGAL_SECTION_PATTERN.finditer(text))
    if not matches:
        return [segment.strip() for segment in re.split(r"\n\s*\n", text) if segment.strip()]

    sections: list[str] = []
    cursor = 0
    for match in matches:
        if match.start() > cursor:
            prefix = text[cursor : match.start()].strip()
            if prefix:
                sections.extend(
                    segment.strip()
                    for segment in re.split(r"\n\s*\n", prefix)
                    if segment.strip()
                )
        cursor = match.start()

    tail = text[cursor:].strip()
    if tail:
        sections.append(tail)

    return sections
