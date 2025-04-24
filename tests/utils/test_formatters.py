from django.test import TestCase

from opentelemetry_instrumentation_django_outbox_pattern.utils.formatters import format_consumer_destination
from opentelemetry_instrumentation_django_outbox_pattern.utils.formatters import format_publisher_destination


class FormattersTestCase(TestCase):
    def test_format_consumer_destination_different_routing_key_and_queue(self):
        """Test format_consumer_destination when routing_key is different from queue"""
        headers = {
            "destination": "/queue/test-queue",
            "dop-msg-destination": "/exchange/test-exchange/test-routing-key",
        }
        result = format_consumer_destination(headers)
        self.assertEqual(result, "test-exchange:test-routing-key:test-queue")

    def test_format_consumer_destination_same_routing_key_and_queue(self):
        """Test format_consumer_destination when routing_key is the same as queue"""
        headers = {
            "destination": "/queue/test-queue",
            "dop-msg-destination": "/exchange/test-exchange/test-queue",
        }
        result = format_consumer_destination(headers)
        self.assertEqual(result, "test-exchange:test-queue")

    def test_format_publisher_destination(self):
        """Test format_publisher_destination"""
        destination = "/exchange/test-exchange/test-routing-key"
        result = format_publisher_destination(destination)
        self.assertEqual(result, "test-exchange:test-routing-key")
