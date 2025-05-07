from io import StringIO
from unittest.mock import PropertyMock
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command
from django_outbox_pattern.management.commands.publish import Command
from django_outbox_pattern.models import Published
from opentelemetry.semconv.trace import SpanAttributes
from request_id_django_log import local_threading

from opentelemetry_instrumentation_django_outbox_pattern.instrumentors.publisher_instrument import (
    _logger as publisher_logger,
)
from opentelemetry_instrumentation_django_outbox_pattern.utils.formatters import format_publisher_destination
from tests.support.helpers_tests import TestBase
from tests.support.otel_helpers import CustomFakeException
from tests.support.otel_helpers import get_traceparent_from_span


class PublisherInstrumentBase(TestBase):
    test_queue_name = None
    correlation_id = None
    fake_payload_body = None

    def setUp(self):
        self.test_queue_name = f"/exchange/test-exchange/test-publisher-queue-{uuid4()}"
        self.correlation_id = f"{uuid4()}"
        local_threading.request_id = self.correlation_id
        self.fake_payload_body = {"fake": "body"}
        super().setUp()

    def expected_span_attributes(self, mock_payload_size):
        from django.conf import settings as django_settings

        host, port = django_settings.DJANGO_OUTBOX_PATTERN["DEFAULT_STOMP_HOST_AND_PORTS"][0]
        return {
            SpanAttributes.MESSAGING_DESTINATION_NAME: self.test_queue_name,
            SpanAttributes.MESSAGING_MESSAGE_CONVERSATION_ID: self.correlation_id,
            SpanAttributes.MESSAGING_MESSAGE_PAYLOAD_SIZE_BYTES: mock_payload_size("x"),
            SpanAttributes.NET_PEER_NAME: host,
            SpanAttributes.NET_PEER_PORT: port,
            SpanAttributes.MESSAGING_SYSTEM: "rabbitmq",
        }


class TestPublisherSaveInstrument(PublisherInstrumentBase):

    @patch("sys.getsizeof", return_value=1)
    def test_should_match_traceparent_header_message_equals_to_traceparent_context_span(self, mock_payload_size):
        # Act
        published_create = Published.objects.create(
            destination=self.test_queue_name,
            body=self.fake_payload_body,
        )

        # Assert
        finished_spans = self.get_finished_spans()
        publisher_span = finished_spans.by_name(f"save published {self.test_queue_name}")
        self.assertEqual(published_create.headers["traceparent"], get_traceparent_from_span(publisher_span))
        self.assertEqual(dict(publisher_span.attributes), self.expected_span_attributes(mock_payload_size))


class TestPublisherSaveInstrumentRaises(PublisherInstrumentBase):

    @patch("sys.getsizeof", return_value=1)
    def test_should_log_exception_if_it_was_raised_inside_hook_function(self, mock_payload_size):
        # Arrange
        body = {"raise_publisher_hook_exception": True, **self.fake_payload_body}

        # Act
        with self.assertLogs(logger=publisher_logger, level="WARNING") as publisher_log:
            published_create = Published.objects.create(
                destination=self.test_queue_name,
                body=body,
            )

        # Assert
        finished_spans = self.get_finished_spans()
        publisher_span = finished_spans.by_name(f"save published {self.test_queue_name}")
        self.assertEqual(published_create.headers["traceparent"], get_traceparent_from_span(publisher_span))
        self.assertEqual(dict(publisher_span.attributes), self.expected_span_attributes(mock_payload_size))
        self.assertEqual(len(publisher_log.output), 1)
        self.assertIn("An exception occurred in the callback hook.", publisher_log.output[0])
        self.assertIn('CustomFakeException("fake exception")', publisher_log.output[0])

    @patch(
        "opentelemetry_instrumentation_django_outbox_pattern.instrumentors.publisher_instrument.get_span",
        side_effect=CustomFakeException("fake high level exception"),
    )
    @patch("sys.getsizeof", return_value=1)
    def test_should_log_exception_if_it_was_raised_to_instrument(self, mock_payload_size, mock_get_span):
        # Act
        with self.assertLogs(logger=publisher_logger, level="WARNING") as publisher_log:
            published_create = Published.objects.create(
                destination=self.test_queue_name,
                body=self.fake_payload_body,
            )

        # Assert
        finished_spans = self.get_finished_spans()
        self.assertEqual(len(finished_spans), 0)
        self.assertNotIn("traceparent", published_create.headers)
        self.assertEqual(len(publisher_log.output), 1)
        self.assertIn("An exception occurred in the on_get_message_headers wrap.", publisher_log.output[0])
        self.assertIn("CustomFakeException: fake high level exception", publisher_log.output[0])


class TestPublisherToBrokerInstrument(PublisherInstrumentBase):

    def expected_span_attributes(self, mock_payload_size):
        from django.conf import settings as django_settings

        host, port = django_settings.DJANGO_OUTBOX_PATTERN["DEFAULT_STOMP_HOST_AND_PORTS"][0]
        return {
            SpanAttributes.MESSAGING_DESTINATION_NAME: format_publisher_destination(self.test_queue_name),
            SpanAttributes.MESSAGING_MESSAGE_CONVERSATION_ID: self.correlation_id,
            SpanAttributes.MESSAGING_MESSAGE_PAYLOAD_SIZE_BYTES: mock_payload_size("x"),
            SpanAttributes.MESSAGING_OPERATION: "publish",
            SpanAttributes.NET_PEER_NAME: host,
            SpanAttributes.NET_PEER_PORT: port,
            SpanAttributes.MESSAGING_SYSTEM: "rabbitmq",
        }

    @patch("sys.getsizeof", return_value=1)
    def test_should_publish_with_trace_traceparent_header_and_create_publish_span(self, mock_payload_size):
        # Act save
        published_create = Published.objects.create(
            destination=self.test_queue_name,
            body=self.fake_payload_body,
        )

        # Assert save
        self.assertIn("traceparent", published_create.headers)

        # Arrange send
        Command.running = PropertyMock(side_effect=[True, False])
        out = StringIO()
        self.reset_trace()

        # Act send
        call_command("publish", stdout=out)
        self.assertIn("Message published with body", out.getvalue())

        # Assert send
        finished_spans = self.get_finished_spans()
        publish_span = finished_spans.by_name(f"send {format_publisher_destination(self.test_queue_name)}")
        self.assertEqual(dict(publish_span.attributes), self.expected_span_attributes(mock_payload_size))


class TestPublisherToBrokerRaisesInstrument(PublisherInstrumentBase):
    def expected_span_attributes(self, mock_payload_size):
        from django.conf import settings as django_settings

        host, port = django_settings.DJANGO_OUTBOX_PATTERN["DEFAULT_STOMP_HOST_AND_PORTS"][0]
        return {
            SpanAttributes.MESSAGING_DESTINATION_NAME: format_publisher_destination(self.test_queue_name),
            SpanAttributes.MESSAGING_MESSAGE_CONVERSATION_ID: self.correlation_id,
            SpanAttributes.MESSAGING_MESSAGE_PAYLOAD_SIZE_BYTES: mock_payload_size("x"),
            SpanAttributes.MESSAGING_OPERATION: "publish",
            SpanAttributes.NET_PEER_NAME: host,
            SpanAttributes.NET_PEER_PORT: port,
            SpanAttributes.MESSAGING_SYSTEM: "rabbitmq",
        }

    @patch("sys.getsizeof", return_value=1)
    def test_should_publish_with_trace_traceparent_when_callback_hook_fails(self, mock_payload_size):
        # Arrange save
        body = {"raise_publisher_hook_exception": True, **self.fake_payload_body}

        # Act save
        published_create = Published.objects.create(
            destination=self.test_queue_name,
            body=body,
        )

        # Assert save
        self.assertIn("traceparent", published_create.headers)

        # Arrange send
        Command.running = PropertyMock(side_effect=[True, False])
        out = StringIO()
        self.reset_trace()

        # Act send
        with self.assertLogs(logger=publisher_logger, level="WARNING") as publisher_log:
            call_command("publish", stdout=out)
        self.assertIn("Message published with body", out.getvalue())

        # Assert send
        finished_spans = self.get_finished_spans()
        publish_span = finished_spans.by_name(f"send {format_publisher_destination(self.test_queue_name)}")
        self.assertEqual(dict(publish_span.attributes), self.expected_span_attributes(mock_payload_size))
        self.assertIn("An exception occurred in the callback hook.", publisher_log.output[0])
        self.assertIn('CustomFakeException("fake exception")', publisher_log.output[0])

    @patch(
        "opentelemetry_instrumentation_django_outbox_pattern.instrumentors.publisher_instrument.format_publisher_destination",  # noqa: E501
        side_effect=CustomFakeException("fake high level exception"),
    )
    @patch("sys.getsizeof", return_value=1)
    def test_should_publish_when_exception_occurs_on_instrument(
        self, mock_payload_size, mock_format_publisher_destination
    ):
        # Act save
        published_create = Published.objects.create(
            destination=self.test_queue_name,
            body=self.fake_payload_body,
        )

        # Assert save
        self.assertIn("traceparent", published_create.headers)

        # Arrange send
        self.reset_trace()
        Command.running = PropertyMock(side_effect=[True, False])
        out = StringIO()

        # Act send
        with self.assertLogs(logger=publisher_logger, level="WARNING") as publisher_log:
            call_command("publish", stdout=out)
        self.assertIn("Message published with body", out.getvalue())

        # Assert
        finished_spans = self.get_finished_spans()
        self.assertNotIn(f"send {format_publisher_destination(self.test_queue_name)}", finished_spans)
        self.assertEqual(len(publisher_log.output), 1)
        self.assertIn("An exception occurred in the on_send_message wrap.", publisher_log.output[0])
        self.assertIn("CustomFakeException: fake high level exception", publisher_log.output[0])
