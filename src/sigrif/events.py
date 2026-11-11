import json
import logging
import time
from typing import Any

import boto3

from .config import settings

logger = logging.getLogger(__name__)

TOPIC_NAME = "sigrif-datos"
QUEUE_NAME = "sigrif-lecturas"
DLQ_NAME = "sigrif-lecturas-dlq"
_QUEUE_CACHE: tuple[float, int | None] | None = None


class MessagingDisabled(RuntimeError):
    """Se lanza cuando el despliegue no usa la mensajería asíncrona."""


def _client(service: str) -> Any:
    return boto3.client(
        service,
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url,
    )


def ensure_resources() -> tuple[str, str]:
    """Devuelve los recursos configurados o los crea en un entorno local.

    En producción Terraform crea SNS/SQS y entrega los ARNs por variables de
    entorno. Así el arranque de la API no intenta crear infraestructura.
    """

    if not settings.messaging_enabled:
        return "", ""
    if settings.sns_topic_arn and settings.sqs_queue_url:
        return settings.sns_topic_arn, settings.sqs_queue_url

    sns = _client("sns")
    sqs = _client("sqs")
    topic_arn = sns.create_topic(Name=TOPIC_NAME)["TopicArn"]
    dlq_url = sqs.create_queue(QueueName=DLQ_NAME)["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    queue_url = sqs.create_queue(
        QueueName=QUEUE_NAME,
        Attributes={
            "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"})
        },
    )["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]
    sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
    return topic_arn, queue_url


def publish_reading(payload: dict[str, Any]) -> None:
    if not settings.messaging_enabled:
        raise MessagingDisabled("La mensajería asíncrona está deshabilitada en este despliegue")
    topic_arn = settings.sns_topic_arn
    if not topic_arn:
        topic_arn, _ = ensure_resources()
    _client("sns").publish(
        TopicArn=topic_arn,
        Message=json.dumps(payload),
        MessageAttributes={"event": {"DataType": "String", "StringValue": "lectura.creada"}},
    )


def publish_alert(payload: dict[str, Any]) -> bool:
    """Publica una alerta operativa en el tópico SNS de alertas.

    No es una dependencia dura de la evaluación: si el tópico no está
    configurado o falla, se registra el problema y la evaluación continúa.
    """

    topic_arn = settings.alert_topic_arn
    if not topic_arn:
        logger.info("alert_topic_arn no configurado; alerta no enviada")
        return False
    try:
        _client("sns").publish(
            TopicArn=topic_arn,
            Subject="SIGRIF: zona en riesgo Alto",
            Message=json.dumps(payload, ensure_ascii=False),
        )
    except Exception:
        logger.exception("No se pudo publicar la alerta SNS")
        return False
    return True


def queue_depth() -> int | None:
    """Cantidad aproximada de mensajes visibles y en vuelo, con caché corta."""

    global _QUEUE_CACHE
    queue_url = settings.sqs_queue_url
    if not queue_url:
        return None
    now = time.monotonic()
    if _QUEUE_CACHE and now - _QUEUE_CACHE[0] < 30:
        return _QUEUE_CACHE[1]
    try:
        attrs = _client("sqs").get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
            ],
        )["Attributes"]
        depth = int(attrs.get("ApproximateNumberOfMessages", 0)) + int(
            attrs.get("ApproximateNumberOfMessagesNotVisible", 0)
        )
    except Exception:
        logger.exception("No se pudo leer la profundidad de la cola")
        depth = None
    _QUEUE_CACHE = (now, depth)
    return depth


def unwrap_message(body: dict[str, Any]) -> dict[str, Any]:
    if isinstance(body.get("Message"), str):
        return json.loads(body["Message"])
    return body


def receive_readings(max_messages: int = 5) -> list[dict[str, Any]]:
    queue_url = settings.sqs_queue_url
    if not queue_url:
        _, queue_url = ensure_resources()
    response = _client("sqs").receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=2,
        MessageAttributeNames=["All"],
    )
    messages = []
    for message in response.get("Messages", []):
        messages.append(
            {
                "receipt": message["ReceiptHandle"],
                "payload": unwrap_message(json.loads(message["Body"])),
            }
        )
    return messages


def delete_message(receipt: str) -> None:
    queue_url = settings.sqs_queue_url
    if not queue_url:
        _, queue_url = ensure_resources()
    _client("sqs").delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
