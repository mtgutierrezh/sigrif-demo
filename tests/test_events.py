import json

from sigrif import events


class FakeSNS:
    def __init__(self):
        self.published = None
        self.subscribed = None

    def create_topic(self, Name):
        return {"TopicArn": f"arn:aws:sns:us-east-1:1:{Name}"}

    def subscribe(self, **kwargs):
        self.subscribed = kwargs

    def publish(self, **kwargs):
        self.published = kwargs


class FakeSQS:
    def __init__(self, messages=None):
        self.messages = messages or []
        self.deleted = None

    def create_queue(self, QueueName, Attributes=None):
        return {"QueueUrl": f"http://queue/{QueueName}"}

    def get_queue_attributes(self, QueueUrl, AttributeNames):
        return {
            "Attributes": {"QueueArn": f"arn:aws:sqs:us-east-1:1:{QueueUrl.rsplit('/', 1)[-1]}"}
        }

    def receive_message(self, **kwargs):
        return {"Messages": self.messages}

    def delete_message(self, **kwargs):
        self.deleted = kwargs


def test_unwrap_sns_envelope():
    body = {"Type": "Notification", "Message": '{"zone_id": 1, "temperature": 30.0}'}
    assert events.unwrap_message(body) == {"zone_id": 1, "temperature": 30.0}


def test_unwrap_plain_payload():
    body = {"zone_id": 2, "temperature": 22.0}
    assert events.unwrap_message(body) == body


def test_ensure_resources(monkeypatch):
    sns = FakeSNS()
    sqs = FakeSQS()
    monkeypatch.setattr(events, "_client", lambda service: sns if service == "sns" else sqs)
    topic, queue = events.ensure_resources()
    assert topic.endswith("sigrif-datos")
    assert queue.endswith("sigrif-lecturas")
    assert sns.subscribed["Protocol"] == "sqs"


def test_publish_reading_uses_topic(monkeypatch):
    sns = FakeSNS()
    monkeypatch.setattr(events.settings, "sns_topic_arn", "arn:aws:sns:us-east-1:1:sigrif-datos")
    monkeypatch.setattr(events, "_client", lambda service: sns)
    events.publish_reading({"zone_id": 1})
    assert sns.published["TopicArn"].endswith("sigrif-datos")
    assert json.loads(sns.published["Message"]) == {"zone_id": 1}


def test_receive_and_delete_message(monkeypatch):
    body = {"Type": "Notification", "Message": '{"zone_id": 3}'}
    sqs = FakeSQS(messages=[{"ReceiptHandle": "abc", "Body": json.dumps(body)}])
    monkeypatch.setattr(events.settings, "sqs_queue_url", "http://queue/sigrif-lecturas")
    monkeypatch.setattr(events, "_client", lambda service: sqs)
    messages = events.receive_readings()
    assert messages[0]["payload"] == {"zone_id": 3}
    events.delete_message("abc")
    assert sqs.deleted["ReceiptHandle"] == "abc"
