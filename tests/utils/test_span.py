from unittest.mock import MagicMock
from unittest.mock import patch

from django.test import TestCase
from django.test import override_settings
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import SpanKind

from opentelemetry_instrumentation_django_outbox_pattern.utils.span import enrich_span
from opentelemetry_instrumentation_django_outbox_pattern.utils.span import enrich_span_with_host_data
from opentelemetry_instrumentation_django_outbox_pattern.utils.span import get_messaging_ack_nack_span
from opentelemetry_instrumentation_django_outbox_pattern.utils.span import get_span


class SpanUtilsTestCase(TestCase):
    @override_settings(
        DJANGO_OUTBOX_PATTERN={
            "DEFAULT_STOMP_HOST_AND_PORTS": [("test-host", 61613)],
        },
        STOMP_SYSTEM="test-system",
    )
    def test_enrich_span_with_host_data(self):
        """Test that enrich_span_with_host_data adds the correct attributes to the span"""
        mock_span = MagicMock()

        enrich_span_with_host_data(mock_span)

        mock_span.set_attributes.assert_called_once_with(
            {
                SpanAttributes.NET_PEER_NAME: "test-host",
                SpanAttributes.NET_PEER_PORT: 61613,
                SpanAttributes.MESSAGING_SYSTEM: "test-system",
            }
        )

    @patch("opentelemetry_instrumentation_django_outbox_pattern.utils.span.enrich_span_with_host_data")
    def test_enrich_span_with_operation(self, mock_enrich_span_with_host_data):
        """Test that enrich_span adds the correct attributes to the span when operation is provided"""
        mock_span = MagicMock()
        operation = "test-operation"
        destination = "test-destination"
        headers = {"dop-correlation-id": "test-correlation-id"}
        body = {"test": "body"}

        enrich_span(mock_span, operation, destination, headers, body)

        # Check that the correct attributes were set
        attributes = mock_span.set_attributes.call_args[0][0]
        self.assertEqual(attributes[SpanAttributes.MESSAGING_DESTINATION_NAME], destination)
        self.assertEqual(attributes[SpanAttributes.MESSAGING_MESSAGE_CONVERSATION_ID], "test-correlation-id")
        self.assertEqual(attributes[SpanAttributes.MESSAGING_OPERATION], operation)
        self.assertIn(SpanAttributes.MESSAGING_MESSAGE_PAYLOAD_SIZE_BYTES, attributes)

        # Check that enrich_span_with_host_data was called
        mock_enrich_span_with_host_data.assert_called_once_with(mock_span)

    @patch("opentelemetry_instrumentation_django_outbox_pattern.utils.span.enrich_span_with_host_data")
    def test_enrich_span_without_operation(self, mock_enrich_span_with_host_data):
        """Test that enrich_span adds the correct attributes to the span when operation is not provided"""
        mock_span = MagicMock()
        operation = None
        destination = "test-destination"
        headers = {"correlation-id": "test-correlation-id"}
        body = {"test": "body"}

        enrich_span(mock_span, operation, destination, headers, body)

        # Check that the correct attributes were set
        attributes = mock_span.set_attributes.call_args[0][0]
        self.assertEqual(attributes[SpanAttributes.MESSAGING_DESTINATION_NAME], destination)
        self.assertEqual(attributes[SpanAttributes.MESSAGING_MESSAGE_CONVERSATION_ID], "test-correlation-id")
        self.assertNotIn(SpanAttributes.MESSAGING_OPERATION, attributes)
        self.assertIn(SpanAttributes.MESSAGING_MESSAGE_PAYLOAD_SIZE_BYTES, attributes)

        # Check that enrich_span_with_host_data was called
        mock_enrich_span_with_host_data.assert_called_once_with(mock_span)

    @patch("opentelemetry_instrumentation_django_outbox_pattern.utils.span.enrich_span")
    def test_get_span(self, mock_enrich_span):
        """Test that get_span creates a span and calls enrich_span"""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_span.is_recording.return_value = True

        destination = "test-destination"
        span_kind = SpanKind.PRODUCER
        headers = {"test": "headers"}
        body = {"test": "body"}
        span_name = "test-span"
        operation = "test-operation"

        result = get_span(mock_tracer, destination, span_kind, headers, body, span_name, operation)

        # Check that the span was created correctly
        mock_tracer.start_span.assert_called_once_with(name=span_name, kind=span_kind)

        # Check that enrich_span was called with the correct arguments
        mock_enrich_span.assert_called_once_with(
            span=mock_span,
            operation=operation,
            destination=destination,
            headers=headers,
            body=body,
        )

        # Check that the correct span was returned
        self.assertEqual(result, mock_span)

    @patch("opentelemetry_instrumentation_django_outbox_pattern.utils.span.enrich_span_with_host_data")
    def test_get_messaging_ack_nack_span(self, mock_enrich_span_with_host_data):
        """Test that get_messaging_ack_nack_span creates a span and sets the correct attributes"""
        for operation in ["ack", "nack"]:
            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_span.return_value = mock_span
            mock_span.is_recording.return_value = True

            destination = "test-destination"

            mock_process_span = MagicMock()
            mock_process_span._attributes = {
                SpanAttributes.MESSAGING_DESTINATION_NAME: destination,
                SpanAttributes.MESSAGING_MESSAGE_CONVERSATION_ID: "test-correlation-id",
            }

            operation = operation
            span_name = f"{operation} test-destination"
            result = get_messaging_ack_nack_span(mock_tracer, operation, mock_process_span)

            # Check that the span was created correctly
            mock_tracer.start_span.assert_called_once_with(name=span_name, kind=SpanKind.CONSUMER)

            # Check that the correct attributes were set
            attributes = mock_span.set_attributes.call_args[0][0]
            self.assertEqual(attributes[SpanAttributes.MESSAGING_OPERATION], operation)
            self.assertEqual(attributes[SpanAttributes.MESSAGING_DESTINATION_NAME], destination)
            self.assertEqual(attributes[SpanAttributes.MESSAGING_MESSAGE_CONVERSATION_ID], "test-correlation-id")

            # Check that enrich_span_with_host_data was called
            mock_enrich_span_with_host_data.assert_called_once_with(mock_span)

            self.assertEqual(result, mock_span)

            # reset mock objects for the next iteration
            mock_enrich_span_with_host_data.reset_mock()
