from pathlib import Path

from app.core.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError

INVALID_FILENAME_MESSAGE = "Nombre de archivo no válido"

ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx"})
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})

EXTENSION_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

DEFAULT_ALLOWED_MIME_TYPES = frozenset(
    {
        EXTENSION_TO_MIME[".pdf"],
        EXTENSION_TO_MIME[".docx"],
    }
)

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


def _allowed_extensions(allowed_mime_types: frozenset[str] | set[str]) -> frozenset[str]:
    extensions = set(ALLOWED_EXTENSIONS)
    image_mimes = {
        EXTENSION_TO_MIME[ext]
        for ext in IMAGE_EXTENSIONS
        if ext in EXTENSION_TO_MIME
    }
    if image_mimes & set(allowed_mime_types):
        extensions.update(IMAGE_EXTENSIONS)
    return frozenset(extensions)


def validate_filename(filename: str) -> str:
    if not filename or not filename.strip():
        raise UnsupportedMediaTypeError(INVALID_FILENAME_MESSAGE)

    cleaned = filename.strip()
    if "\x00" in cleaned or ".." in cleaned:
        raise UnsupportedMediaTypeError(INVALID_FILENAME_MESSAGE)

    if cleaned.startswith(("/", "\\")) or "/" in cleaned or "\\" in cleaned:
        raise UnsupportedMediaTypeError(INVALID_FILENAME_MESSAGE)

    basename = Path(cleaned).name
    if not basename or basename != cleaned:
        raise UnsupportedMediaTypeError(INVALID_FILENAME_MESSAGE)

    return basename


def validate_upload_file(
    filename: str,
    content: bytes,
    mime_type: str | None,
    *,
    max_size_bytes: int,
    allowed_mime_types: frozenset[str] | set[str] | None = None,
) -> str:
    filename = validate_filename(filename)

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
    allowed_ext = _allowed_extensions(allowed)

    if normalized and normalized in allowed:
        return normalized

    if extension in allowed_ext:
        return EXTENSION_TO_MIME[extension]

    if any(mime.startswith("image/") for mime in allowed):
        detail = "Tipo de archivo no permitido. Use PDF, DOCX o imagen (JPEG/PNG/WebP)."
    else:
        detail = "Tipo de archivo no permitido. Use PDF o DOCX."

    raise UnsupportedMediaTypeError(detail)
