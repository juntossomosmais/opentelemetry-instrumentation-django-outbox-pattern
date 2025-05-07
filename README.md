# Opentelemetry auto instrumentation for django outbox pattern library

[//]: # ([![Build Status]&#40;https://dev.azure.com/juntos-somos-mais-loyalty/python/_apis/build/status/juntossomosmais.opentelemetry-instrumentation-django-outbox-pattern?branchName=main&#41;]&#40;https://dev.azure.com/juntos-somos-mais-loyalty/python/_build/latest?definitionId=272&branchName=main&#41;)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=juntossomosmais_opentelemetry-instrumentation-django-outbox-pattern&metric=sqale_rating&token=80cebbac184a793f8d0be7a3bbe9792f47a6ef23)](https://sonarcloud.io/summary/new_code?id=juntossomosmais_opentelemetry-instrumentation-django-outbox-pattern)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=juntossomosmais_opentelemetry-instrumentation-django-outbox-pattern&metric=coverage&token=80cebbac184a793f8d0be7a3bbe9792f47a6ef23)](https://sonarcloud.io/summary/new_code?id=juntossomosmais_opentelemetry-instrumentation-django-outbox-pattern)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=juntossomosmais_opentelemetry-instrumentation-django-outbox-pattern&metric=alert_status&token=80cebbac184a793f8d0be7a3bbe9792f47a6ef23)](https://sonarcloud.io/summary/new_code?id=juntossomosmais_opentelemetry-instrumentation-django-outbox-pattern)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![PyPI version](https://badge.fury.io/py/opentelemetry-instrumentation-django-outbox-pattern.svg)](https://badge.fury.io/py/opentelemetry-instrumentation-django-outbox-pattern)
[![GitHub](https://img.shields.io/github/license/mashape/apistatus.svg)](https://github.com/juntossomosmais/opentelemetry-instrumentation-django-outbox-pattern/blob/main/LICENSE)

This library will help you to use opentelemetry traces and metrics on [Django outbox pattern](https://github.com/juntossomosmais/django-outbox-pattern) usage library.

![Django outbox pattern instrumentation](docs/all_trace_example.png?raw=true)


####  Installation
pip install `opentelemetry-instrumentation-django-outbox-pattern`

#### How to use ?

You can use the `DjangoOutboxPatternInstrumentor().instrument()` for example in `manage.py` file.


```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import typing

from opentelemetry_instrumentation_django_outbox_pattern import DjangoOutboxPatternInstrumentor

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.trace.span import Span


def publisher_hook(span: Span, body: typing.Dict, headers: typing.Dict):
    # Custom code in your project here we can see span attributes and make custom logic with then.
    pass


def consumer_hook(span: Span, body: typing.Dict, headers: typing.Dict):
    # Custom code in your project here we can see span attributes and make custom logic with then.
    pass


provider = TracerProvider()
trace.set_tracer_provider(provider)
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "application.settings")
    DjangoOutboxPatternInstrumentor().instrument(
        trace_provider=trace,
        publisher_hook=publisher_hook,
        consumer_hook=consumer_hook,
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

The code above will create telemetry wrappers inside django-outbox-pattern code and creates automatic spans with broker data.

The `DjangoOutboxPatternInstrumentor` can receive three optional parameters:
- **trace_provider**: The tracer provider to use in open-telemetry spans.
- **publisher_hook**: The callable function on publisher action to call before the original function call, use this to override, enrich the span or get span information in the main project.
- **consumer_hook**: The callable function on consumer action to call before the original function call, use this to override, enrich the span or get span information in the main project.

:warning: The hook function will not raise an exception when an error occurs inside hook function, only a warning log is generated

### Span Generated

#### save published {destination}

With the django-outbox-pattern, when you create on `Published` objects one object is saved and this saved is instrumentalized.

```python
from django_outbox_pattern.models import Published

Published.objects.create(
    destination='destination',
    body={
        "random": "body"
    },
)
    
```

The outbox save span had `save published {destination}` name.

![save example](docs/save_trace.png?raw=true)

#### send {destination}

After save the object in `Published` model the `publish` command will get all pending messages and publish there to broker

```bash
python manage.py publish
```

The outbox publish span had `publish {destination}` name.

![publisher example](docs/send_trace.png?raw=true)

#### Consumer

Using the django-outbox-pattern, we create a simple consumer using subscribe management command, using this command
we can see the consumer spans.

```bash
   python manage.py subscribe 'dotted.path.to.callback' 'destination' 'queue_name'
```

Consumer spans can generate up to three types:

- process {destination}
![process trace](docs/process_trace.png?raw=true)
- ack {destination}
![ack trace](docs/ack_trace.png?raw=true)
- nack {destination}
![nack trace](docs/nack_trace.png?raw=true)

#### Supress django-outbox-pattern traces and metrics
When the flag `OTEL_PYTHON_DJANGO_OUTBOX_PATTERN_INSTRUMENT` has `False` value traces and metrics will not be generated.
Use this to supress the django-outbox-pattern-instrumentation instrumentation.

#### HOW TO CONTRIBUTE ?
Look the [contributing](./CONTRIBUTING.md) specs
