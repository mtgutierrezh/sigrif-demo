import pytest

from sigrif.ia import main


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_consume_processes_and_deletes(monkeypatch):
    seen = []

    def messages():
        yield {"payload": {"zone_id": 1}, "receipt": "r1"}
        raise KeyboardInterrupt

    monkeypatch.setattr(main, "receive_readings", messages)
    monkeypatch.setattr(main, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        main,
        "apply_reading",
        lambda session, payload: seen.append(("apply", payload)) or True,
    )
    monkeypatch.setattr(
        main,
        "delete_message",
        lambda receipt: seen.append(("delete", receipt)),
    )

    with pytest.raises(KeyboardInterrupt):
        main.consume()

    assert seen == [("apply", {"zone_id": 1}), ("delete", "r1")]
