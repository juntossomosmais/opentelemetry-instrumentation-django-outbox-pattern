import logging
import threading
import typing

import wrapt

from django_outbox_pattern.consumers import Consumer
from opentelemetry import context
from opentelemetry import propagate
from opentelemetry import trace
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.sdk.trace import Tracer
from opentelemetry.semconv.trace import MessagingOperationValues
from opentelemetry.trace import SpanKind
from opentelemetry.trace import Status
from opentelemetry.trace import StatusCode
from stomp.connect import StompConnection12

from ..utils.django_outbox_pattern_getter import DjangoOutboxPatternGetter
from ..utils.formatters import format_consumer_destination
from ..utils.shared_types import CallbackHookT
from ..utils.span import get_messaging_ack_nack_span
from ..utils.span import get_span

_django_outbox_pattern_getter = DjangoOutboxPatternGetter()

_logger = logging.getLogger(__name__)

_thread_local = threading.local()


class ConsumerInstrument:
    @staticmethod
    def instrument(tracer: Tracer, callback_hook: CallbackHookT = None):
        """Instrumentor function to create span and instrument consumer"""

        def common_ack_or_nack_span(span_event_name: str, span_status: Status, wrapped_function: typing.Callable):
            token = None
            try:
                span = getattr(_thread_local, "span", None)
                span_ctx = getattr(_thread_local, "span_context", None)

                if span and span.is_recording():
                    token = context.attach(span_ctx)
                    span.add_event(span_event_name)
                    span.set_status(span_status)
                    span.end()
            except Exception as unmapped_exception:
                _logger.warning("An exception occurred while trying to set ack/nack span.", exc_info=unmapped_exception)
                return wrapped_function
            finally:
                if token:
                    context.detach(token)

        def wrapper_nack(wrapped, instance, args, kwargs):
            token = None
            try:
                ctx = getattr(_thread_local, "span_context", None)
                destination = getattr(_thread_local, "destination", None)
                headers = getattr(_thread_local, "headers", {})
                token = context.attach(ctx)

                span = get_messaging_ack_nack_span(
                    tracer=tracer,
                    span_kind=SpanKind.CONSUMER,
                    span_name=f"nack {destination}",
                    operation="nack",
                    destination=destination,
                    headers=headers,
                )
                if span and span.is_recording():
                    span.add_event("message.nack")
                    span.set_status(Status(StatusCode.ERROR))
                    span.end()
                return common_ack_or_nack_span("message.nack", Status(StatusCode.ERROR), wrapped(*args, **kwargs))
            except Exception as unmapped_exception:
                _logger.warning("An exception occurred while trying to set nack span.", exc_info=unmapped_exception)
                return common_ack_or_nack_span("message.nack", Status(StatusCode.ERROR), wrapped(*args, **kwargs))
            finally:
                if token:
                    context.detach(token)

        def wrapper_ack(wrapped, instance, args, kwargs):
            token = None
            try:
                ctx = getattr(_thread_local, "span_context", None)
                destination = getattr(_thread_local, "destination", None)
                headers = getattr(_thread_local, "headers", {})
                token = context.attach(ctx)

                span = get_messaging_ack_nack_span(
                    tracer=tracer,
                    span_kind=SpanKind.CONSUMER,
                    span_name=f"ack {destination}",
                    operation="ack",
                    destination=destination,
                    headers=headers,
                )
                if span and span.is_recording():
                    span.add_event("message.ack")
                    span.set_status(Status(StatusCode.OK))
                    span.end()
                return common_ack_or_nack_span("message.nack", Status(StatusCode.OK), wrapped(*args, **kwargs))
            except Exception as exception:
                _logger.warning("An exception occurred while trying to set ack span.", exc_info=exception)
                return common_ack_or_nack_span("message.ack", Status(StatusCode.OK), wrapped(*args, **kwargs))
            finally:
                if token:
                    context.detach(token)

        def wrapped_message_handler(wrapped, instance, args, kwargs):
            try:
                body = args[0]
                headers = args[1]
                destination = format_consumer_destination(headers)
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
                    span_name=f"process {destination}",
                    operation=str(MessagingOperationValues.RECEIVE.value),
                )

                # Store the span and context in thread-local storage to get this in ack or nack functions
                _thread_local.span = span
                _thread_local.span_context = trace.set_span_in_context(span)
                _thread_local.headers = headers
                _thread_local.destination = destination
            except Exception as unmapped_exception:
                _logger.warning("An exception occurred in the instrument_callback wrap.", exc_info=unmapped_exception)
                return wrapped(*args, **kwargs)

            try:
                with trace.use_span(span):
                    if callback_hook:
                        try:
                            callback_hook(span, body, headers)
                        except Exception as hook_exception:
                            _logger.warning("An exception occurred in the callback hook.", exc_info=hook_exception)
                    return wrapped(*args, **kwargs)
            finally:
                context.detach(token)

        wrapt.wrap_function_wrapper(Consumer, "message_handler", wrapped_message_handler)
        wrapt.wrap_function_wrapper(StompConnection12, "ack", wrapper_ack)
        wrapt.wrap_function_wrapper(StompConnection12, "nack", wrapper_nack)

    @staticmethod
    def uninstrument():
        unwrap(Consumer, "message_handler")
        unwrap(StompConnection12, "ack")
        unwrap(StompConnection12, "nack")
