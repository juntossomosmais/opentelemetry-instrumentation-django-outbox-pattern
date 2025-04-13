import os
import uuid

import pytest

from django.conf import settings


@pytest.fixture
def mock_payload_size(mocker):
    """Mock function to get size in bytes of payload queue"""
    get_sizeof_value = 1
    mocker.patch("sys.getsizeof").return_value = get_sizeof_value
    return get_sizeof_value


def pytest_configure():
    settings.configure(
        INSTALLED_APPS=["opentelemetry_instrumentation_django_outbox_pattern", "django_outbox_pattern"],
        DJANGO_OUTBOX_PATTERN = {
            "DEFAULT_STOMP_HOST_AND_PORTS": [(os.getenv("STOMP_SERVER_HOST"), os.getenv("STOMP_SERVER_PORT"))],
            "DEFAULT_STOMP_USERNAME": os.getenv("STOMP_SERVER_USER"),
            "DEFAULT_STOMP_PASSCODE": os.getenv("STOMP_SERVER_PASSWORD"),
            "DEFAULT_STOMP_USE_SSL": os.getenv("STOMP_USE_SSL"),
            "DEFAULT_STOMP_VHOST": os.getenv("DEFAULT_STOMP_VHOST")
            "DEFAULT_CONNECTION_CLASS": "stomp.StompConnection12",
        },
        DATABASES={
            "default": {
                "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
                "NAME": os.getenv("DB_DATABASE", f"test_db-{uuid.uuid4()}"),
                "USER": os.getenv("DB_USER"),
                "HOST": os.getenv("DB_HOST"),
                "PORT": os.getenv("DB_PORT"),
                "PASSWORD": os.getenv("DB_PASSWORD"),
                "TEST": {"NAME": os.getenv("DB_DATABASE", f"test_db-{uuid.uuid4()}")},
            }
        },
    )
