from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace import export
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import format_span_id
from opentelemetry.trace import format_trace_id

from opentelemetry_instrumentation_django_outbox_pattern import DjangoOutboxPatternInstrumentor

tracer_provider = None
memory_exporter = None


class CustomFakeException(Exception):
    pass


def publisher_hook(span, body, headers):
    """Hook to be called when a message is published"""
    assert headers.get("traceparent", None) == get_traceparent_from_span(span)
    if body.get("raise_publisher_hook_exception", False):
        raise CustomFakeException("fake exception")


def consumer_hook(span, body, headers):
    """Hook to be called when a message is consumed"""


def instrument_app():
    """Instrument the app with the given hooks"""
    global tracer_provider, memory_exporter

    if tracer_provider is None or memory_exporter is None:
        tracer_provider = TracerProvider()
        memory_exporter = InMemorySpanExporter()
        span_processor = export.SimpleSpanProcessor(memory_exporter)
        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)

        DjangoOutboxPatternInstrumentor().instrument(
            tracer_provider=tracer_provider,
            publisher_hook=publisher_hook,
            consumer_hook=consumer_hook,
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
