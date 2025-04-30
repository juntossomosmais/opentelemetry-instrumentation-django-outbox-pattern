from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.test import TransactionTestCase
from django_outbox_pattern.factories import factory_consumer
from django_outbox_pattern.headers import get_message_headers
from django_outbox_pattern.models import Published
from opentelemetry.semconv.trace import MessagingOperationValues
from opentelemetry.semconv.trace import SpanAttributes
from request_id_django_log import local_threading
from stomp.listener import TestListener

from tests.support.helpers_tests import TestBase


def get_callback(raise_except=False):
    def callback(payload):
        if raise_except:
            raise KeyError("Test exception")
        payload.save()

    return callback


class ConsumerInstrumentBase(TestBase, TransactionTestCase):
    test_queue_name = None
    correlation_id = None
    fake_payload_body = None

    def setUp(self):
        self.test_queue_name = "/topic/consumer.v1"
        self.correlation_id = f"{uuid4()}"
        local_threading.request_id = self.correlation_id
        self.fake_payload_body = {"message": "mock message"}
        cache.set("remove_old_messages_django_outbox_pattern_consumer", True)
        super().setUp()

    def expected_span_attributes(self, mock_payload_size, custom_attributes_override: dict | None = None):
        from django.conf import settings as django_settings

        custom_attributes_override = custom_attributes_override if custom_attributes_override else {}

        host, port = django_settings.DJANGO_OUTBOX_PATTERN["DEFAULT_STOMP_HOST_AND_PORTS"][0]
        return {
            SpanAttributes.MESSAGING_DESTINATION_NAME: self.test_queue_name,
            SpanAttributes.MESSAGING_MESSAGE_CONVERSATION_ID: self.correlation_id,
            SpanAttributes.MESSAGING_MESSAGE_PAYLOAD_SIZE_BYTES: mock_payload_size("x"),
            SpanAttributes.NET_PEER_NAME: host,
            SpanAttributes.NET_PEER_PORT: port,
            SpanAttributes.MESSAGING_SYSTEM: "rabbitmq",
            **custom_attributes_override,
        }


class TestConsumerInstrument(ConsumerInstrumentBase):

    def setUp(self):
        super().setUp()
        self.consumer = factory_consumer()
        self.consumer.set_listener("test_listener", TestListener(print_to_log=True))
        self.listener = self.consumer.get_listener("test_listener")

    @patch("sys.getsizeof", return_value=1)
    def test_should_consumer_create_span_with_ack(self, mock_payload_size):
        # Arrange
        headers = get_message_headers(
            Published(
                destination=self.test_queue_name,
                body=self.fake_payload_body,
            )
        )
        callback = get_callback()
        self.consumer.start(callback, self.test_queue_name)
        self.consumer.connection.send(
            destination=self.test_queue_name,
            body='{"message": "mock message"}',
            headers=headers,
        )
        self.listener.wait_for_message()
        self.consumer.stop()

        # Assert Consumer
        finished_spans = self.get_finished_spans()

        # Check publisher span
        publisher_span = finished_spans.by_name(f"save published {self.test_queue_name}")
        self.assertEqual(dict(publisher_span.attributes), self.expected_span_attributes(mock_payload_size))

        # Check consumer span
        process = finished_spans.by_name("process topic:consumer.v1")
        self.assertEqual(
            dict(process.attributes),
            self.expected_span_attributes(
                mock_payload_size,
                {
                    SpanAttributes.MESSAGING_OPERATION: str(MessagingOperationValues.RECEIVE.value),
                    SpanAttributes.MESSAGING_DESTINATION_NAME: "topic:consumer.v1",
                },
            ),
        )

        # Check that the consumer span has the same trace as the publisher span
        self.assertEqual(process.context.trace_id, publisher_span.context.trace_id)

        ack_span = finished_spans.by_name("ack topic:consumer.v1")
        ack_expected_attributes = self.expected_span_attributes(
            mock_payload_size,
            {
                SpanAttributes.MESSAGING_OPERATION: "ack",
                SpanAttributes.MESSAGING_DESTINATION_NAME: "topic:consumer.v1",
            },
        )
        del ack_expected_attributes["messaging.message.payload_size_bytes"]
        self.assertEqual(dict(ack_span.attributes), ack_expected_attributes)

    @patch("sys.getsizeof", return_value=1)
    def test_should_consumer_create_span_with_nack(self, mock_payload_size):
        # Arrange
        callback = get_callback(raise_except=True)
        headers = get_message_headers(
            Published(
                destination=self.test_queue_name,
                body=self.fake_payload_body,
            )
        )
        self.consumer.start(callback, self.test_queue_name)
        self.consumer.connection.send(
            destination=self.test_queue_name,
            body='{"message": "mock message"}',
            headers=headers,
        )
        self.listener.wait_for_message()
        self.consumer.stop()

        # Assert Consumer
        finished_spans = self.get_finished_spans()

        # Check publisher span
        publisher_span = finished_spans.by_name(f"save published {self.test_queue_name}")
        self.assertEqual(dict(publisher_span.attributes), self.expected_span_attributes(mock_payload_size))

        # Check consumer span
        process = finished_spans.by_name("process topic:consumer.v1")
        self.assertEqual(
            dict(process.attributes),
            self.expected_span_attributes(
                mock_payload_size,
                {
                    SpanAttributes.MESSAGING_OPERATION: str(MessagingOperationValues.RECEIVE.value),
                    SpanAttributes.MESSAGING_DESTINATION_NAME: "topic:consumer.v1",
                },
            ),
        )

        # Check that the consumer span has the same trace as the publisher span
        self.assertEqual(process.context.trace_id, publisher_span.context.trace_id)

        nack_span = finished_spans.by_name("nack topic:consumer.v1")
        nack_expected_attributes = self.expected_span_attributes(
            mock_payload_size,
            {
                SpanAttributes.MESSAGING_OPERATION: "nack",
                SpanAttributes.MESSAGING_DESTINATION_NAME: "topic:consumer.v1",
            },
        )
        del nack_expected_attributes["messaging.message.payload_size_bytes"]
        self.assertEqual(dict(nack_span.attributes), nack_expected_attributes)
