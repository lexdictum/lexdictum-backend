from unittest.mock import MagicMock, patch

from app.config import Settings
from app.core.telemetry import init_telemetry, link_request_id, trace_span


class TestTelemetryNoOp:
    def test_init_disabled_is_noop(self, settings: Settings):
        disabled = settings.model_copy(update={"otel_enabled": False})
        init_telemetry(disabled)

        with trace_span("test.span", foo="bar") as span:
            assert span is None or hasattr(span, "is_recording")

    def test_link_request_id_when_disabled(self, settings: Settings):
        disabled = settings.model_copy(update={"otel_enabled": False})
        init_telemetry(disabled)
        link_request_id("req-123")

    def test_trace_span_yields_without_crash(self, settings: Settings):
        disabled = settings.model_copy(update={"otel_enabled": False})
        init_telemetry(disabled)

        with trace_span("rag.retrieve", case_id="abc") as span:
            if span is not None:
                assert hasattr(span, "is_recording")

    def test_init_without_deps_is_noop(self, settings: Settings, caplog):
        enabled = settings.model_copy(
            update={"otel_enabled": True, "otel_exporter_endpoint": None}
        )
        import app.core.telemetry as telemetry

        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("mock missing otel")
            return real_import(name, *args, **kwargs)

        telemetry._initialized = False
        telemetry._tracing_active = False
        with caplog.at_level("WARNING"):
            with patch("builtins.__import__", side_effect=guarded_import):
                init_telemetry(enabled)

        assert any("OpenTelemetry" in record.message for record in caplog.records)

    def test_link_request_id_on_active_span(self, settings: Settings):
        mock_trace = MagicMock()
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_trace.get_current_span.return_value = mock_span
        fake_otel = MagicMock()
        fake_otel.trace = mock_trace

        import app.core.telemetry as telemetry

        with patch.object(telemetry, "_tracing_active", True):
            with patch.dict("sys.modules", {"opentelemetry": fake_otel}):
                link_request_id("trace-req-1")

        mock_span.set_attribute.assert_called_once_with("request.id", "trace-req-1")
