import os
import uuid

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "opentelemetry_instrumentation_django_outbox_pattern",
    "django_outbox_pattern",
]

SECRET_KEY = "test-secret-key"

DJANGO_OUTBOX_PATTERN = {
    "DEFAULT_STOMP_HOST_AND_PORTS": [("rabbitmq", "61613")],
    "DEFAULT_STOMP_USERNAME": "guest",
    "DEFAULT_STOMP_PASSCODE": "guest",
    "DEFAULT_STOMP_USE_SSL": False,
    "DEFAULT_STOMP_VHOST": "/",
    "DEFAULT_CONNECTION_CLASS": "stomp.StompConnection12",
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": f"test_db-{uuid.uuid4()}",
        "USER": os.getenv("DB_USER"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "TEST": {
            "NAME": f"test_db-{uuid.uuid4()}",
        },
    }
}
