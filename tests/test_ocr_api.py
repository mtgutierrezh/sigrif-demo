from fastapi.testclient import TestClient

from sigrif.config import settings
from sigrif.ia import main as ia_main

PNG = b"\x89PNG\r\n\x1a\n" + b"ficha" * 8
OCR_RESULT = {
    "text": "PTCL-23\nCHILE",
    "model_id": "amazon.nova-lite-v1:0",
    "latency_ms": 850.0,
    "usage": {"input_tokens": 1200, "output_tokens": 18},
    "truncated": False,
    "cached": False,
    "image_sha256": "a" * 64,
}

client = TestClient(ia_main.app)


def test_ocr_disabled(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_enabled", False)
    response = client.post(
        "/ocr",
        files={"file": ("ficha.png", PNG, "image/png")},
    )
    assert response.status_code == 503
    assert "no está habilitado" in response.json()["detail"]


def test_ocr_success(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_enabled", True)
    monkeypatch.setattr(ia_main, "extract_text", lambda data, content_type: OCR_RESULT)
    response = client.post(
        "/ocr",
        files={"file": ("ficha.png", PNG, "image/png")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "PTCL-23\nCHILE"
    assert payload["filename"] == "ficha.png"
    assert payload["content_type"] == "image/png"
    assert payload["usage"]["input_tokens"] == 1200


def test_ocr_rejects_unsupported_type(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_enabled", True)
    response = client.post(
        "/ocr",
        files={"file": ("ficha.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert response.status_code == 415


def test_ocr_rejects_spoofed_type(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_enabled", True)
    response = client.post(
        "/ocr",
        files={"file": ("ficha.png", b"\xff\xd8\xff" + b"jpeg", "image/png")},
    )
    assert response.status_code == 415
    assert "no coincide" in response.json()["detail"]
