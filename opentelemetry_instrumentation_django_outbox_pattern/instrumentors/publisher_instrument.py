import json
import logging

import wrapt

from django.core.serializers.json import DjangoJSONEncoder
from django_outbox_pattern import headers as outbox_headers_module
from django_outbox_pattern.producers import Producer
from opentelemetry import context
from opentelemetry import propagate
from opentelemetry import trace
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.sdk.trace import Tracer
from opentelemetry.semconv.trace import MessagingOperationValues
from opentelemetry.trace import SpanKind

from ..utils.django_outbox_pattern_getter import DjangoOutboxPatternGetter
from ..utils.formatters import format_publisher_destination
from ..utils.shared_types import CallbackHookT
from ..utils.span import get_span

_django_outbox_pattern_getter = DjangoOutboxPatternGetter()

_logger = logging.getLogger(__name__)


class PublisherInstrument:
    @staticmethod
    def instrument(tracer: Tracer, callback_hook: CallbackHookT = None):
        """Instrumentor to create span and instrument publisher"""

        def on_send_message(wrapped, instance, args, kwargs):
            try:
                destination = format_publisher_destination(destination=kwargs.get("destination"))
                message_headers = kwargs.get("headers", {})
                body = kwargs.get("body", {})

                ctx = propagate.extract(message_headers, getter=_django_outbox_pattern_getter)
                if not ctx:
                    ctx = context.get_current()
                token = context.attach(ctx)

                span = get_span(
                    tracer=tracer,
                    destination=destination,
                    span_kind=SpanKind.PRODUCER,
                    headers=message_headers,
                    body=body,
                    span_name=f"send {destination}",
                    operation=str(MessagingOperationValues.PUBLISH.value),
                )
                with trace.use_span(span, end_on_exit=True):
                    if span.is_recording():
                        propagate.inject(message_headers)
                        if callback_hook:
                            try:
                                callback_hook(span, body, message_headers)
                            except Exception as hook_exception:
                                _logger.warning("An exception occurred in the callback hook.", exc_info=hook_exception)
                    if token:
                        context.detach(token)
                    return wrapped(**kwargs)
            except Exception as unmapped_exception:
                _logger.warning("An exception occurred in the on_send_message wrap.", exc_info=unmapped_exception)
                return wrapped(**kwargs)

        def on_get_message_headers(wrapped, instance, args, kwargs):
            message_headers = wrapped(*args, **kwargs)
            try:
                published = args[0]
                destination = published.destination
                body = json.loads(json.dumps(published.body, cls=DjangoJSONEncoder))
                span = get_span(
                    tracer=tracer,
                    destination=destination,
                    span_kind=SpanKind.PRODUCER,
                    headers=message_headers,
                    body=body,
                    span_name=f"save published {destination}",
                )
                with trace.use_span(span, end_on_exit=True):
                    if span.is_recording():
                        propagate.inject(message_headers)
                        if callback_hook:
                            try:
                                callback_hook(span, body, message_headers)
                            except Exception as hook_exception:
                                _logger.warning("An exception occurred in the callback hook.", exc_info=hook_exception)
                    return message_headers
            except Exception as unmapped_exception:
                _logger.warning(
                    "An exception occurred in the on_get_message_headers wrap.", exc_info=unmapped_exception
                )
                return message_headers

        wrapt.wrap_function_wrapper(Producer, "_send_with_retry", on_send_message)
        wrapt.wrap_function_wrapper(outbox_headers_module, "generate_headers", on_get_message_headers)

    @staticmethod
    def uninstrument():
        """Uninstrument publisher functions from django-outbox-pattern"""
        unwrap(Producer, "_send_with_retry")
        unwrap(outbox_headers_module, "generate_headers")
