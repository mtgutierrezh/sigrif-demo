from sigrif.prescription import build_prescription


def _features(**overrides: float) -> dict[str, float]:
    values = {
        "temperature": 32.0,
        "humidity": 25.0,
        "wind_speed": 48.0,
        "vegetation": 0.7,
        "historical_fires": 6,
        "slope": 28.0,
    }
    values.update(overrides)
    return values


def _prediction(level: str, score: float = 0.8) -> dict:
    return {
        "risk_level": level,
        "risk_score": score,
        "factors": [{"label": "Temperatura"}],
    }


def test_high_risk_includes_all_conditional_actions() -> None:
    actions = build_prescription(_features(), _prediction("Alto"))
    codes = {action["code"] for action in actions}

    assert codes == {
        "patrullaje_inmediato",
        "restriccion_acceso",
        "reduccion_combustible",
        "inspeccion_prioritaria",
        "revision_evacuacion",
    }
    assert all(action["rationale"] for action in actions)


def test_high_risk_keeps_only_five_actions() -> None:
    actions = build_prescription(_features(), _prediction("Alto"))

    assert len(actions) == 5
    assert actions[0]["priority"] == "inmediata"


def test_medium_risk_adds_fuel_maintenance_when_vegetation_is_high() -> None:
    actions = build_prescription(_features(vegetation=0.6), _prediction("Medio", 0.55))
    codes = {action["code"] for action in actions}

    assert "patrullaje_preventivo" in codes
    assert "mantencion_combustible" in codes
    assert "verificacion_acceso" in codes


def test_low_risk_recommends_routine_monitoring() -> None:
    actions = build_prescription(_features(), _prediction("Bajo", 0.2))

    assert [action["code"] for action in actions] == [
        "monitoreo_rutinario",
        "mantencion_preventiva",
    ]
    assert "score 0.20" in actions[0]["rationale"]
