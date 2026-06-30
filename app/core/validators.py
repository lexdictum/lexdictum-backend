from pathlib import Path

from app.core.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError

ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx", ".jpg", ".jpeg", ".png", ".webp"})

EXTENSION_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

DEFAULT_ALLOWED_MIME_TYPES = frozenset(EXTENSION_TO_MIME.values())

GENERIC_MIME_TYPES = frozenset(
    {"application/octet-stream", "binary/octet-stream", "application/x-msdownload"}
)


def normalize_mime_type(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    return mime_type.split(";", 1)[0].strip().lower()


def resolve_content_type(filename: str, mime_type: str | None) -> str:
    normalized = normalize_mime_type(mime_type)
    if normalized and normalized not in GENERIC_MIME_TYPES:
        return normalized

    extension = Path(filename).suffix.lower()
    return EXTENSION_TO_MIME.get(extension, normalized or "application/octet-stream")


def validate_upload_file(
    filename: str,
    content: bytes,
    mime_type: str | None,
    *,
    max_size_bytes: int,
    allowed_mime_types: frozenset[str] | set[str] | None = None,
) -> str:
    if len(content) == 0:
        raise UnsupportedMediaTypeError("El archivo está vacío")

    if len(content) > max_size_bytes:
        max_mb = max_size_bytes // (1024 * 1024)
        raise PayloadTooLargeError(
            f"El archivo supera el tamaño máximo permitido ({max_mb} MB)"
        )

    allowed = allowed_mime_types or DEFAULT_ALLOWED_MIME_TYPES
    extension = Path(filename).suffix.lower()
    normalized = normalize_mime_type(mime_type)

    if normalized and normalized in allowed:
        return normalized

    if extension in ALLOWED_EXTENSIONS:
        return EXTENSION_TO_MIME[extension]

    raise UnsupportedMediaTypeError(
        "Tipo de archivo no permitido. Use PDF, DOCX o imágenes (JPEG, PNG, WebP)."
    )
