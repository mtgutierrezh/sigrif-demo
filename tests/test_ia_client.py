import httpx
import pytest

from sigrif.ia.client import IAUnavailable, predict_risk

FEATURES = {
    "temperature": 31.0,
    "humidity": 22.0,
    "wind_speed": 45.0,
    "vegetation": 0.7,
    "historical_fires": 6,
    "slope": 30.0,
}
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
