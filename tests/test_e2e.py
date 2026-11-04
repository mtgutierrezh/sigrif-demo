import os
import time

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SIGRIF_E2E") != "1",
    reason="requiere la demo local en ejecucion",
)

BASE_URL = os.getenv("SIGRIF_BASE_URL", "http://localhost:8080")
TOKEN = os.getenv("SIGRIF_E2E_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


def test_health():
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_risk_flow():
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        zones = client.get("/api/v1/zones")
        assert zones.status_code == 200
        assert zones.json()

        simulation = client.post("/api/v1/simulate", headers=HEADERS)
        if simulation.status_code == 401 and not TOKEN:
            pytest.skip("AUTH_ENABLED=true; define SIGRIF_E2E_TOKEN para probar el flujo")
        assert simulation.status_code == 202

        zone_id = simulation.json().get("zone_id", zones.json()[0]["id"])
        time.sleep(3)

        zone = client.get(f"/api/v1/zones/{zone_id}")
        assert zone.status_code == 200
        assert zone.json()["updated_at"]
