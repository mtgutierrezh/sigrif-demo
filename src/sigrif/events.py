import json
from typing import Any

import boto3

from .config import settings

TOPIC_NAME = "sigrif-datos"
QUEUE_NAME = "sigrif-lecturas"
DLQ_NAME = "sigrif-lecturas-dlq"


def _client(service: str) -> Any:
    return boto3.client(
        service,
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url,
    )


def ensure_resources() -> tuple[str, str]:
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
    topic_arn = settings.sns_topic_arn
    if not topic_arn:
        topic_arn, _ = ensure_resources()
    _client("sns").publish(
        TopicArn=topic_arn,
        Message=json.dumps(payload),
        MessageAttributes={"event": {"DataType": "String", "StringValue": "lectura.creada"}},
    )


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
