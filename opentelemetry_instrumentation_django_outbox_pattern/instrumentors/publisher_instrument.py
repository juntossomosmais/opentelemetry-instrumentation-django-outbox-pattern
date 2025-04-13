import logging

import wrapt

from django_outbox_pattern.producers import Producer
from django_outbox_pattern import headers
from opentelemetry import propagate
from opentelemetry import trace
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.sdk.trace import Tracer
from opentelemetry.trace import SpanKind

from opentelemetry_instrumentation_django_stomp.utils.shared_types import CallbackHookT
from opentelemetry_instrumentation_django_stomp.utils.span import get_span


_logger = logging.getLogger(__name__)


class PublisherInstrument:
    @staticmethod
    def instrument(tracer: Tracer, callback_hook: CallbackHookT = None):
        """Instrumentor to create span and instrument publisher"""

        def on_send_message(wrapped, instance, args, kwargs):
            try:
                host, port = settings.DJANGO_OUTBOX_PATTERN["DEFAULT_STOMP_HOST_AND_PORTS"][0]
                destination = kwargs.get("destination")
                headers = kwargs.get("headers", {})

            except Exception as e:
                logger.warn("Could not trace Publisher: {}".format(e))
                return wrapped(**kwargs)

            span = get_span(
                tracer=tracer,
                destination=destination,
                span_kind=SpanKind.PRODUCER,
                headers=headers,
                body=body,
                span_name="PUBLISHER",
            )

            with trace.use_span(span, end_on_exit=True):
                if span.is_recording():
                    propagate.inject(headers)
                    if callback_hook:
                        try:
                            callback_hook(span, body, headers)
                        except Exception as hook_exception:  # pylint: disable=W0703
                            _logger.exception(hook_exception)
                return wrapped(*args, **kwargs)

        original_get_message_headers = headers.get_message_headers

        def on_get_message_headers(message):
            headers = original_get_message_headers(message)
            try:
                host, port = settings.DJANGO_OUTBOX_PATTERN["DEFAULT_STOMP_HOST_AND_PORTS"][0]
                destination = headers.get("destination")
            except Exception as e:
                logger.warn("autodynatrace - Could not trace Publisher.send: {}".format(e))
                return headers

            span = get_span(
                tracer=tracer,
                destination=destination,
                span_kind=SpanKind.PRODUCER,
                headers=headers,
                body=body,
                span_name="PUBLISHER",
            )

            with trace.use_span(span, end_on_exit=True):
                if span.is_recording():
                    propagate.inject(headers)
                    if callback_hook:
                        try:
                            callback_hook(span, body, headers)
                        except Exception as hook_exception:  # pylint: disable=W0703
                            _logger.exception(hook_exception)
                return wrapped(*args, **kwargs)

        wrapt.wrap_function_wrapper(Producer, "_send_with_retry", on_send_message)
        setattr(headers, "get_message_headers", on_get_message_headers)

    @staticmethod
    def uninstrument():
        """Uninstrument publisher functions from django-outbox-pattern"""
        unwrap(Producer, "_send_with_retry")
