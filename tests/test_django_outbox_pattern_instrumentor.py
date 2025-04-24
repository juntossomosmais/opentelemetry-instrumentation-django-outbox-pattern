from unittest.mock import MagicMock
from unittest.mock import patch

from django.test import TestCase
from django.test import override_settings

from opentelemetry_instrumentation_django_outbox_pattern import DjangoOutboxPatternInstrumentor
from opentelemetry_instrumentation_django_outbox_pattern.instrumentors.consumer_instrument import ConsumerInstrument
from opentelemetry_instrumentation_django_outbox_pattern.instrumentors.publisher_instrument import PublisherInstrument


class TestDjangoOutboxPatternInstrumentor(TestCase):
    """Tests for the DjangoOutboxPatternInstrumentor class."""

    @override_settings(OTEL_PYTHON_DJANGO_OUTBOX_PATTERN_INSTRUMENT=False)
    @patch.object(ConsumerInstrument, "instrument")
    @patch.object(PublisherInstrument, "instrument")
    def test_instrument_returns_none_when_setting_is_false(self, mock_publisher_instrument, mock_consumer_instrument):
        """Test that _instrument returns None when OTEL_PYTHON_DJANGO_OUTBOX_PATTERN_INSTRUMENT is False."""
        # Arrange
        instrumentor = DjangoOutboxPatternInstrumentor()
        tracer_provider = MagicMock()

        # Act
        result = instrumentor._instrument(tracer_provider=tracer_provider)

        # Assert
        self.assertIsNone(result)
        mock_consumer_instrument.assert_not_called()
        mock_publisher_instrument.assert_not_called()
