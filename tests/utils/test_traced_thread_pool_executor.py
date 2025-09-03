import logging

from unittest import mock

from opentelemetry import context as otel_context
from opentelemetry import trace

from opentelemetry_instrumentation_django_outbox_pattern.utils.traced_thread_pool_executor import (
    TracedThreadPoolExecutor,
)
from opentelemetry_instrumentation_django_outbox_pattern.utils.traced_thread_pool_executor import with_otel_context
from tests.support.helpers_tests import TestBase

_logger = logging.getLogger(__name__)


class TestTracedThreadPoolExecutor(TestBase):
    @staticmethod
    def dummy_function(*args, **kwargs):
        """Fake function to run in submit on TracedThreadPoolExecutor"""
        tracer = args[0]["tracer"]
        with tracer.start_as_current_span("dummy_function", end_on_exit=True):
            _logger.info("dummy_function executed")

    def test_with_otel_context_function(self):
        """Test that with_otel_context correctly attaches context (lines 10-11)"""
        # Arrange
        test_context = otel_context.Context()
        test_fn = mock.MagicMock(return_value="test_result")

        # Mock attach to verify it's called with the right context
        with mock.patch.object(otel_context, "attach") as mock_attach:
            # Act
            result = with_otel_context(test_context, test_fn)

            # Assert
            mock_attach.assert_called_once_with(test_context)
            test_fn.assert_called_once()
            self.assertEqual(result, "test_result")

    def test_traced_pool_executor_no_context_branch(self):
        """Test the else branch of submit when no context exists (line 29)"""
        # Arrange
        traced_pool_executor = TracedThreadPoolExecutor(tracer=trace.get_tracer(__name__), max_workers=1)

        test_fn = mock.MagicMock()

        # Mock get_current to return None (no current context)
        with mock.patch.object(otel_context, "get_current", return_value=None):
            # Act
            future = traced_pool_executor.submit(test_fn, "arg1", kwarg1="value")
            future.result(timeout=5)

            # Assert
            test_fn.assert_called_once_with("arg1", kwarg1="value")

        traced_pool_executor.shutdown(wait=True)

    def test_traced_pool_executor_propagate_span_to_thread(self):
        # Arrange
        traced_pool_executor = TracedThreadPoolExecutor(
            tracer=trace.get_tracer(__name__),
            thread_name_prefix="test_pool",
            max_workers=1,
        )

        # Act
        tracer = self.tracer_provider.get_tracer(__name__)
        with tracer.start_as_current_span("TRACED_THREAD_POOL_EXECUTOR", end_on_exit=True):
            future = traced_pool_executor.submit(self.dummy_function, {"simple": "parameter", "tracer": tracer})
            future.result(timeout=5)

        traced_pool_executor.shutdown(wait=True)

        # Assert
        finished_spans = self.get_finished_spans()
        finished_thread_span = finished_spans.by_name("TRACED_THREAD_POOL_EXECUTOR")
        finished_function_span = finished_spans.by_name("dummy_function")
        self.assertEqual(finished_function_span.parent.trace_id, finished_thread_span.context.trace_id)
        self.assertEqual(finished_function_span.parent.span_id, finished_thread_span.context.span_id)
        self.assertEqual(len(finished_spans), 2)

    def test_traced_pool_executor_without_propagate_span_to_thread(self):
        # Arrange
        traced_pool_executor = TracedThreadPoolExecutor(
            tracer=trace.get_tracer(__name__),
            thread_name_prefix="test_pool",
            max_workers=1,
        )
        tracer = self.tracer_provider.get_tracer(__name__)

        # Act
        future = traced_pool_executor.submit(self.dummy_function, {"simple": "parameter", "tracer": tracer})
        future.result(timeout=5)
        traced_pool_executor.shutdown(wait=True)

        # Assert
        finished_spans = self.get_finished_spans()
        self.assertEqual(len(finished_spans), 1)
        self.assertIsNotNone(finished_spans.by_name("dummy_function"))
