import typing


def format_consumer_destination(headers: typing.Dict) -> str:
    """
    Helper function to format the consumer destination according to opentelemetry specification.
    https://opentelemetry.io/docs/specs/semconv/messaging/rabbitmq/

    The specified format is:
    {exchange}:{routing_key}:{queue}
    In case the routing_key is the same as the queue, the format is:
    {exchange}:{routing_key}
    """
    destination = headers.get("destination", "")
    dop_destination = headers.get("dop-msg-destination", "")
    split_destination = dop_destination.split("/")
    routing_key = split_destination[-1]
    exchange = split_destination[-2]
    queue = destination.split("/")[-1]
    return f"{exchange}:{routing_key}:{queue}" if routing_key != queue else f"{exchange}:{routing_key}"


def format_publisher_destination(destination: str) -> str:
    """
    Helper function to format the publisher destination according to opentelemetry specification.
    https://opentelemetry.io/docs/specs/semconv/messaging/rabbitmq/
    The specified format is:
    {exchange}:{routing_key}
    """
    split_destination = destination.split("/")
    routing_key = split_destination[-1]
    exchange = split_destination[-2]
    return f"{exchange}:{routing_key}"
