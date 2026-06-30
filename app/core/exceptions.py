from fastapi import HTTPException, status


class LexDictumError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(LexDictumError):
    def __init__(self, message: str = "Recurso no encontrado"):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class UnauthorizedError(LexDictumError):
    def __init__(self, message: str = "No autorizado"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(LexDictumError):
    def __init__(self, message: str = "Acceso denegado"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class PayloadTooLargeError(LexDictumError):
    def __init__(
        self,
        message: str = "El archivo supera el tamaño máximo permitido",
    ):
        super().__init__(message, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)


class UnsupportedMediaTypeError(LexDictumError):
    def __init__(
        self,
        message: str = (
            "Tipo de archivo no permitido. Use PDF, DOCX o imágenes (JPEG, PNG, WebP)."
        ),
    ):
        super().__init__(
            message, status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        )


class StorageError(LexDictumError):
    def __init__(self, message: str = "Error al almacenar el archivo"):
        super().__init__(message, status_code=status.HTTP_502_BAD_GATEWAY)


def http_exception_from_error(error: LexDictumError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.message)
