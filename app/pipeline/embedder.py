from app.config import Settings, get_settings

_model = None


def embed_texts(
    texts: list[str],
    *,
    settings: Settings | None = None,
) -> list[list[float]]:
    if not texts:
        return []

    model = _get_model(settings)
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    if hasattr(vectors, "tolist"):
        return vectors.tolist()
    return [list(row) for row in vectors]


def _get_model(settings: Settings | None = None):
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        settings = settings or get_settings()
        _model = SentenceTransformer(settings.embedding_model_name)
    return _model


def reset_embedder_cache() -> None:
    global _model
    _model = None
