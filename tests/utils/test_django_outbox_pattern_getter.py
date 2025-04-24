from django.test import TestCase

from opentelemetry_instrumentation_django_outbox_pattern.utils.django_outbox_pattern_getter import (
    DjangoOutboxPatternGetter,
)


class DjangoOutboxPatternGetterTestCase(TestCase):
    def setUp(self):
        self.getter = DjangoOutboxPatternGetter()
        self.carrier = {"test-key": "test-value"}

    def test_get_existing_key(self):
        """Test that get returns a list with the value when the key exists in the carrier"""
        result = self.getter.get(self.carrier, "test-key")
        self.assertEqual(result, ["test-value"])

    def test_get_non_existing_key(self):
        """Test that get returns None when the key does not exist in the carrier"""
        result = self.getter.get(self.carrier, "non-existing-key")
        self.assertIsNone(result)

    def test_keys(self):
        """Test that keys returns an empty list"""
        result = self.getter.keys(self.carrier)
        self.assertEqual(result, [])
