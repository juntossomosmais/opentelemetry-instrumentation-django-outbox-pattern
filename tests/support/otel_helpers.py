from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace import export
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import format_span_id
from opentelemetry.trace import format_trace_id

from opentelemetry_instrumentation_django_outbox_pattern import DjangoOutboxPatternInstrumentor

_tracer_provider = None
_memory_exporter = None


def create_global_tracer_provider():
    """Create and register the global tracer provider once"""
    global _tracer_provider, _memory_exporter

    if _tracer_provider is None or _memory_exporter is None:
        _tracer_provider = TracerProvider()
        _memory_exporter = InMemorySpanExporter()
        span_processor = export.SimpleSpanProcessor(_memory_exporter)
        _tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(_tracer_provider)

    return _tracer_provider, _memory_exporter


def instrument_app(publisher_hook=None, consumer_hook=None):
    """Instrument the app with the given hooks"""
    tracer_provider, memory_exporter = create_global_tracer_provider()

    # Re-instrument with potentially new hooks
    DjangoOutboxPatternInstrumentor().instrument(
        tracer_provider=tracer_provider, publisher_hook=publisher_hook, consumer_hook=consumer_hook
    )

    return tracer_provider, memory_exporter


def get_traceparent_from_span(span):
    """Helper function to get traceparent for propagator, used to create header on publish message"""
    trace_id_formatted = format_trace_id(span.context.trace_id)
    span_id_formatted = format_span_id(span.context.span_id)
    trace_flags = span.context.trace_flags
    return f"00-{trace_id_formatted}-{span_id_formatted}-{trace_flags:02x}"


class FinishedTestSpans(list):
    """Helper class to find finished spans in tests to make assertions"""

    def __init__(self, test, spans):
        super().__init__(spans)
        self.test = test

    def by_name(self, name):
        for span in self:
            if span.name == name:
                return span
        self.test.fail(f"Did not find span with name {name}")
        return None

    def by_attr(self, key, value):
        for span in self:
            if span.attributes.get(key) == value:
                return span
        self.test.fail(f"Did not find span with attrs {key}={value}")
        return None
