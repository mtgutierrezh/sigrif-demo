import httpx
import pytest

from sigrif.ia.client import (
    CircuitBreaker,
    IAUnavailable,
    ocr_image,
    predict_risk,
    reset_circuit_breaker,
)

FEATURES = {
    "temperature": 31.0,
    "humidity": 22.0,
    "wind_speed": 45.0,
    "vegetation": 0.7,
    "historical_fires": 6,
    "slope": 30.0,
}


@pytest.fixture(autouse=True)
def _reset_breaker():
    reset_circuit_breaker()


PREDICTION = {
    "risk_level": "Alto",
    "risk_score": 0.91,
    "probabilities": {"Bajo": 0.02, "Medio": 0.07, "Alto": 0.91},
    "model_version": "random-forest-0.2.0",
    "factors": [],
    "scenario": None,
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ia")


def test_predict_risk_returns_prediction() -> None:
    with _client(lambda request: httpx.Response(200, json=PREDICTION)) as client:
        result = predict_risk(FEATURES, client=client)

    assert result["risk_level"] == "Alto"
    assert result["risk_score"] == 0.91


def test_predict_risk_retries_server_errors(monkeypatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(500, json={"detail": "temporal"})
        return httpx.Response(200, json=PREDICTION)

    monkeypatch.setattr("sigrif.ia.client.time.sleep", lambda _: None)
    with _client(handler) as client:
        result = predict_risk(FEATURES, client=client, attempts=2)

    assert calls["count"] == 2
    assert result["risk_level"] == "Alto"


def test_predict_risk_does_not_retry_client_errors() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(422, json={"detail": "inválido"})

    with _client(handler) as client, pytest.raises(IAUnavailable):
        predict_risk(FEATURES, client=client, attempts=3)

    assert calls["count"] == 1


def test_predict_risk_raises_after_transport_failures(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin conexión", request=request)

    monkeypatch.setattr("sigrif.ia.client.time.sleep", lambda _: None)
    with _client(handler) as client, pytest.raises(IAUnavailable):
        predict_risk(FEATURES, client=client, attempts=2)


def test_predict_risk_sends_request_id() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request_id"] = request.headers.get("X-Request-ID")
        return httpx.Response(200, json=PREDICTION)

    with _client(handler) as client:
        predict_risk(FEATURES, client=client, request_id="req-ia-123")

    assert seen["request_id"] == "req-ia-123"


def test_circuit_breaker_opens_and_short_circuits(monkeypatch) -> None:
    monkeypatch.setattr("sigrif.ia.client.time.sleep", lambda _: None)
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=30)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.ConnectError("sin conexión", request=request)

    with _client(handler) as client:
        for _ in range(2):
            with pytest.raises(IAUnavailable):
                predict_risk(FEATURES, client=client, attempts=1, breaker=breaker)
        with pytest.raises(IAUnavailable, match="Circuito"):
            predict_risk(FEATURES, client=client, attempts=1, breaker=breaker)

    assert calls["count"] == 2
    assert breaker.snapshot()["state"] == "open"


def test_circuit_breaker_allows_one_probe_after_timeout(monkeypatch) -> None:
    clock = {"now": 100.0}
    monkeypatch.setattr("sigrif.ia.client.time.monotonic", lambda: clock["now"])
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10)
    breaker.record_failure()
    assert breaker.allow_request() is False

    clock["now"] = 111.0
    assert breaker.allow_request() is True
    assert breaker.allow_request() is False

    breaker.record_success()
    assert breaker.allow_request() is True
    assert breaker.snapshot()["state"] == "closed"


OCR_RESULT = {
    "text": "PTCL-23\nCHILE",
    "model_id": "amazon.nova-lite-v1:0",
    "latency_ms": 850.0,
    "usage": {"input_tokens": 1200, "output_tokens": 18},
    "truncated": False,
    "cached": False,
    "image_sha256": "a" * 64,
}
PNG = b"\x89PNG\r\n\x1a\n" + b"ficha" * 8


def test_ocr_image_sends_multipart_and_request_id() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content_type"] = request.headers.get("content-type", "")
        seen["body"] = request.content
        seen["request_id"] = request.headers.get("X-Request-ID")
        return httpx.Response(200, json=OCR_RESULT)

    with _client(handler) as client:
        result = ocr_image(
            PNG,
            "ficha.png",
            "image/png",
            client=client,
            request_id="req-ocr-123",
        )

    assert result["text"] == "PTCL-23\nCHILE"
    assert seen["content_type"].startswith("multipart/form-data")
    assert b"ficha.png" in seen["body"]
    assert seen["request_id"] == "req-ocr-123"


def test_ocr_image_retries_server_errors(monkeypatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(500, json={"detail": "temporal"})
        return httpx.Response(200, json=OCR_RESULT)

    monkeypatch.setattr("sigrif.ia.client.time.sleep", lambda _: None)
    with _client(handler) as client:
        result = ocr_image(PNG, "ficha.png", "image/png", client=client, attempts=2)

    assert calls["count"] == 2
    assert result["model_id"] == "amazon.nova-lite-v1:0"


def test_ocr_image_does_not_retry_client_errors() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(415, json={"detail": "formato"})

    with _client(handler) as client, pytest.raises(IAUnavailable):
        ocr_image(PNG, "ficha.png", "image/png", client=client, attempts=3)

    assert calls["count"] == 1
