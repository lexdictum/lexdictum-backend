"""Minimal HTTP embedding microservice for EMBEDDING_PROVIDER=http."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.config import get_settings

app = FastAPI(title="LexDictum Embedding Server", version="0.1.0")


class EmbedRequest(BaseModel):
    texts: list[str] = Field(default_factory=list)


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest) -> EmbedResponse:
    from app.pipeline.embedder import embed_texts

    settings = get_settings()
    vectors = embed_texts(request.texts, settings=settings)
    return EmbedResponse(embeddings=vectors)
