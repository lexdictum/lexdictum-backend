"""OpenTelemetry tracing with graceful no-op when disabled or deps missing."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

_tracing_active = False
_initialized = False


def init_telemetry(settings) -> None:
    """Configure OTLP exporter and tracer provider when otel_enabled."""
    global _tracing_active, _initialized

    if _initialized:
        return
    _initialized = True

    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "Paquetes OpenTelemetry no instalados; omitiendo trazas "
            "(uv sync --extra observability)"
        )
        return

    resource = Resource.create(
        {
            "service.name": settings.app_name,
            "deployment.environment": settings.app_env,
        }
    )
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        logger.warning(
            "OTEL_ENABLED=true pero OTEL_EXPORTER_ENDPOINT no está configurado"
        )

    trace.set_tracer_provider(provider)
    _tracing_active = True


def instrument_fastapi(app) -> None:
    if not _tracing_active:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        logger.warning("Instrumentación FastAPI OTel no disponible")
        return

    FastAPIInstrumentor.instrument_app(app)


def link_request_id(request_id: str | None) -> None:
    """Attach X-Request-ID to the current span when tracing is active."""
    if not request_id or not _tracing_active:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("request.id", request_id)
    except ImportError:
        return


@contextmanager
def trace_span(name: str, **attributes: Any) -> Iterator[Any]:
    """Minimal span helper; no-op when tracing is disabled."""
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer(__name__)
    except ImportError:
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        if span.is_recording():
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
        yield span
