from django.test import TestCase
from opentelemetry import trace
from opentelemetry.util._once import Once

from opentelemetry_instrumentation_django_outbox_pattern import DjangoOutboxPatternInstrumentor
from tests.support.otel_helpers import FinishedTestSpans
from tests.support.otel_helpers import instrument_app


class CustomFakeException(Exception):
    pass


class TestBase(TestCase):
    """Base test class with setup and teardown for telemetry parameters"""

    tracer_provider = None
    memory_exporter = None
    publisher_hook = None
    consumer_hook = None

    def setUp(self):
        super().setUp()
        self.tracer_provider, self.memory_exporter = instrument_app(
            publisher_hook=getattr(self, "publisher_hook", None),
            consumer_hook=getattr(self, "consumer_hook", None),
        )

    def tearDown(self):
        self.force_clean_memory_exporter()
        self.reset_trace_globals()
        DjangoOutboxPatternInstrumentor().uninstrument()

    def get_finished_spans(self):
        return FinishedTestSpans(self, self.memory_exporter.get_finished_spans())

    def reset_trace(self):
        self.force_clean_memory_exporter()
        self.reset_trace_globals()

    def force_clean_memory_exporter(self) -> None:
        self.memory_exporter._finished_spans.clear()

    @staticmethod
    def reset_trace_globals() -> None:
        """WARNING: only use this for tests."""
        trace._TRACER_PROVIDER_SET_ONCE = Once()
        trace._TRACER_PROVIDER = None
        trace._PROXY_TRACER_PROVIDER = trace.ProxyTracerProvider()
