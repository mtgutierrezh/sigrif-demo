from typing import Any

import pytest
from botocore.exceptions import ClientError

from sigrif.ia.bedrock_ocr import (
    OcrUnavailable,
    clear_cache,
    detect_content_type,
    extract_text,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"ficha-de-terreno" * 4


class FakeBedrock:
    def __init__(self, text: str = "PTCL-23\nCHILE", stop_reason: str = "end_turn") -> None:
        self.text = text
        self.stop_reason = stop_reason
        self.calls = 0

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        return {
            "output": {"message": {"content": [{"text": self.text}]}},
            "usage": {"inputTokens": 1200, "outputTokens": 18},
            "stopReason": self.stop_reason,
        }


@pytest.fixture(autouse=True)
def clean_cache():
    clear_cache()
    yield
    clear_cache()


def test_detect_content_type_by_signature():
    assert detect_content_type(PNG) == "image/png"
    assert detect_content_type(b"\xff\xd8\xff" + b"jpeg") == "image/jpeg"
    assert detect_content_type(b"RIFF" + b"0000" + b"WEBP" + b"data") == "image/webp"
    assert detect_content_type(b"no-es-imagen") is None


def test_extract_text_success_and_cache():
    client = FakeBedrock()
    result = extract_text(PNG, "image/png", client=client)

    assert result["text"] == "PTCL-23\nCHILE"
    assert result["model_id"] == "amazon.nova-lite-v1:0"
    assert result["usage"] == {"input_tokens": 1200, "output_tokens": 18}
    assert result["cached"] is False
    assert result["truncated"] is False
    assert len(result["image_sha256"]) == 64

    second = extract_text(PNG, "image/png", client=client)
    assert second["cached"] is True
    assert second["latency_ms"] == 0.0
    assert client.calls == 1


def test_extract_text_empty_response():
    result = extract_text(PNG, "image/png", client=FakeBedrock(text="SIN_TEXTO"))
    assert result["text"] == ""


def test_extract_text_rejects_content_mismatch():
    with pytest.raises(OcrUnavailable, match="no coincide"):
        extract_text(PNG, "image/jpeg", client=FakeBedrock())


def test_extract_text_maps_access_denied():
    class Denied:
        def converse(self, **kwargs: Any) -> dict[str, Any]:
            raise ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "sin permiso"}},
                "Converse",
            )

    with pytest.raises(OcrUnavailable, match="permiso"):
        extract_text(PNG, "image/png", client=Denied())


def test_extract_text_marks_truncated():
    result = extract_text(PNG, "image/png", client=FakeBedrock(stop_reason="max_tokens"))
    assert result["truncated"] is True
