from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router as api_router
from app.config import get_settings
from app.core.exceptions import LexDictumError, http_exception_from_error
from app.vector.qdrant import setup_qdrant


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_qdrant(settings)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(LexDictumError)
    async def lexdictum_error_handler(_: Request, exc: LexDictumError) -> JSONResponse:
        http_exc = http_exception_from_error(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content={"detail": http_exc.detail},
        )

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
