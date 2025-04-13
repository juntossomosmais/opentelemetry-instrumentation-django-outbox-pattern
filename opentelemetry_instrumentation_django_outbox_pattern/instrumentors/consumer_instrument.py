import logging
import typing

import wrapt

from django_stomp.services.consumer import Listener
from django_stomp.settings import STOMP_PROCESS_MSG_WORKERS
from opentelemetry import context
from opentelemetry import propagate
from opentelemetry import trace
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.sdk.trace import Tracer
from opentelemetry.semconv.trace import MessagingOperationValues
from opentelemetry.trace import SpanKind

from opentelemetry_instrumentation_django_outbox_pattern.utils.django_stomp_getter import DjangoStompGetter
from opentelemetry_instrumentation_django_outbox_pattern.utils.shared_types import CallbackHookT
from opentelemetry_instrumentation_django_outbox_pattern.utils.span import enrich_span_with_host_data
from opentelemetry_instrumentation_django_outbox_pattern.utils.span import get_span

from stomp.connect import StompConnection12
from django_outbox_pattern.management.commands import subscribe

_django_outbox_pattern_getter = DjangoOutboxPatternGetter()

_logger = logging.getLogger(__name__)


class ConsumerInstrument:
    @staticmethod
    def instrument(tracer: Tracer, callback_hook: CallbackHookT = None):
        """Instrumentor function to create span and instrument consumer"""
        def wrapped_import_string(dotted_path):
            callback_function = import_string(dotted_path)
            
            def instrument_callback(payload):

                try:
                    headers = payload.headers
                    host, port = settings.DJANGO_OUTBOX_PATTERN["DEFAULT_STOMP_HOST_AND_PORTS"][0]
                    destination = headers.get("destination")
                except Exception as e:
                    logger.warn("Could not trace Consumer(import_string): {}".format(e))
                    return callback_function(payload)

                ctx = propagate.extract(headers, getter=_django_outbox_pattern_getter)
                if not ctx:
                    ctx = context.get_current()
                token = context.attach(ctx)

                span = get_span(
                    tracer=tracer,
                    destination=destination,
                    span_kind=SpanKind.CONSUMER,
                    headers=headers,
                    body=body,
                    span_name="CONSUMER",
                    operation=str(MessagingOperationValues.RECEIVE.value),
                )

                try:
                    with trace.use_span(span, end_on_exit=True):
                        if callback_hook:
                            try:
                                callback_hook(span, body, headers)
                            except Exception as hook_exception:  # pylint: disable=W0703
                                _logger.exception(hook_exception)
                        return callback_function(payload)
                finally:
                    context.detach(token)

            return instrumented_callback

        def common_ack_or_nack_span(span_name: str, wrapped_function: typing.Callable):
            span = tracer.start_span(name=span_name, kind=SpanKind.CONSUMER)
            enrich_span_with_host_data(span)
            with trace.use_span(span, end_on_exit=True):
                return wrapped_function

        def wrapper_nack(wrapped, instance, args, kwargs):
            return common_ack_or_nack_span("NACK", wrapped(*args, **kwargs))

        def wrapper_ack(wrapped, instance, args, kwargs):
            return common_ack_or_nack_span("ACK", wrapped(*args, **kwargs))

        setattr(subscribe, "_import_from_string", wrapper_import_from_string)
        wrapt.wrap_function_wrapper(StompConnection12, "nack", wrapper_nack)
        wrapt.wrap_function_wrapper(StompConnection12, "ack", wrapper_ack)

    @staticmethod
    def uninstrument():
        unwrap(Listener, "on_message")
        unwrap(StompConnection12, "nack")
        unwrap(StompConnection12, "ack")
