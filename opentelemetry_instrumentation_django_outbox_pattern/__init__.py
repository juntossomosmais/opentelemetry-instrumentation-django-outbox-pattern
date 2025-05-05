"""
This library supports the `django-outbox-pattern` library, it can be enabled by
using ``DjangoOutboxPatternInstrumentor``.

*****************************************
USAGE
-----
In project manage.py you can include the example code below

.. code-block:: python
    from opentelemetry_instrumentation_django_outbox_pattern import DjangoOutboxPatternInstrumentor

    def publisher_hook(span: Span, body: Dict, headers: Dict):
        # Custom code
        pass

    def consumer_hook(span: Span, body: Dict, headers: Dict):
        # Custom code
        pass

    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    DjangoOutboxPatternInstrumentor().instrument(
        trace_provider=trace,
        publisher_hook=publisher_hook,
        consumer_hook=consumer_hook,
    )

*****************************************
CONSUMER
-----
With the django-outbox-pattern, we create a simple consumer using the pubsub subscribe command. The `consumer_hook`
provided to the `DjangoOutboxPatternInstrumentor` is used to enrich or override spans with telemetry data for
consumer operations. This allows you to customize the telemetry data for each consumed message.

.. code-block:: python
   python manage.py subscribe 'dotted.path.to.callback` 'destination' 'queue_name'

*****************************************
PUBLISHER
-----
With the django-outbox-pattern we create a publication job that will publish a message from database to broker
and the instrumentor can include a span with telemetry data in this function utilization.

.. code-block:: python
   python manage.py publish
"""

import threading
import typing

from django.conf import settings
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace import TracerProvider

from .instrumentors.consumer_instrument import ConsumerInstrument
from .instrumentors.publisher_instrument import PublisherInstrument
from .package import _instruments
from .utils.shared_types import CallbackHookT
from .version import __version__

_CTX_KEY = "__otel_django_outbox_pattern_span"

local_threading = threading.local()


class DjangoOutboxPatternInstrumentor(BaseInstrumentor):
    def instrumentation_dependencies(self) -> typing.Collection[str]:
        """
        Function to check compatibility with dependencies package(django-outbox-pattern)
        """
        return _instruments

    def _uninstrument(self, **kwargs):
        """
        Function to unwrap publisher and consumer functions from django-outbox-pattern
        """
        if hasattr(self, "__opentelemetry_tracer_provider"):
            delattr(self, "__opentelemetry_tracer_provider")
        ConsumerInstrument().uninstrument()
        PublisherInstrument().uninstrument()

    def _instrument(self, **kwargs) -> None:
        """
        Instrument function to initialize wrappers in publisher and consumer functions from django-outbox-pattern.

        Args:
            kwargs (typing.Dict[str, typing.Any]):
                trace_provider (Optional[TracerProvider]): The tracer provider to use in open-telemetry spans.
                publisher_hook (CallbackHookT): The callable function to call before original function call, use
                this to override or enrich the span created in main project.
                consumer_hook (CallbackHookT): The callable function to call before original function call, use
                this to override or enrich the span created in main project.

        Returns:
        """
        instrument_django_outbox_pattern = getattr(settings, "OTEL_PYTHON_DJANGO_OUTBOX_PATTERN_INSTRUMENT", True)
        if not instrument_django_outbox_pattern:
            return None

        tracer_provider: typing.Optional[TracerProvider] = kwargs.get("tracer_provider", None)
        publisher_hook: CallbackHookT = kwargs.get("publisher_hook", None)
        consumer_hook: CallbackHookT = kwargs.get("consumer_hook", None)

        self.__setattr__("__opentelemetry_tracer_provider", tracer_provider)
        tracer = trace.get_tracer(__name__, __version__, tracer_provider)

        ConsumerInstrument().instrument(tracer=tracer, callback_hook=consumer_hook)
        PublisherInstrument().instrument(tracer=tracer, callback_hook=publisher_hook)
