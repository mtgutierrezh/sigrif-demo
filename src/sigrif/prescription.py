"""Motor de prescripción operativa para SIGRIF.

Las variables meteorológicas no son accionables: no tiene sentido recomendar
"bajar la temperatura". Por eso las acciones se traducen a medidas factibles de
gestión territorial y respuesta operativa. El motor es determinista y
auditable; no usa un LLM para decidir.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

Action = dict[str, str]


def _action(
    code: str,
    title: str,
    description: str,
    priority: str,
    horizon: str,
    rationale: str,
) -> Action:
    return {
        "code": code,
        "title": title,
        "description": description,
        "priority": priority,
        "horizon": horizon,
        "rationale": rationale,
    }


def build_prescription(
    features: Mapping[str, float],
    prediction: Mapping[str, Any],
) -> list[Action]:
    """Construye hasta cinco acciones ordenadas por urgencia."""

    risk_level = str(prediction["risk_level"])
    risk_score = float(prediction["risk_score"])
    factors = prediction.get("factors") or []
    factor_text = (
        f" El factor con mayor peso local fue {factors[0]['label'].lower()}." if factors else ""
    )
    base_rationale = (
        f"El modelo estimó riesgo {risk_level} con score {risk_score:.2f}.{factor_text}"
    )

    actions: list[Action] = []

    if risk_level == "Alto":
        actions.append(
            _action(
                "patrullaje_inmediato",
                "Reforzar patrullaje en el sector",
                "Asignar una ronda terrestre prioritaria y registrar novedades en el parte diario.",
                "inmediata",
                "24 h",
                base_rationale,
            )
        )
        if features["wind_speed"] >= 40:
            actions.append(
                _action(
                    "restriccion_acceso",
                    "Restringir acceso y suspender quemas",
                    "Cerrar senderos o accesos vulnerables y suspender autorizaciones de quema "
                    "mientras se mantenga el viento fuerte.",
                    "inmediata",
                    "24 h",
                    "El viento supera 40 km/h, lo que favorece la propagación y reduce el margen "
                    "de respuesta.",
                )
            )
        if features["vegetation"] >= 0.6:
            actions.append(
                _action(
                    "reduccion_combustible",
                    "Programar reducción de combustible",
                    "Priorizar cortafuegos, despeje de material seco y mantención de fajas en el "
                    "borde urbano-forestal.",
                    "preventiva",
                    "7 días",
                    "La vegetación combustible está sobre 0.60 y es una variable que sí se puede "
                    "gestionar.",
                )
            )
        if features["historical_fires"] >= 5:
            actions.append(
                _action(
                    "inspeccion_prioritaria",
                    "Inspeccionar puntos de recurrencia histórica",
                    "Revisar los sectores con mayor cantidad de incendios previos y actualizar el "
                    "mapa de puntos críticos.",
                    "preventiva",
                    "7 días",
                    "El sector acumula cinco o más incendios históricos en la ventana de "
                    "referencia.",
                )
            )
        if features["slope"] >= 25:
            actions.append(
                _action(
                    "revision_evacuacion",
                    "Revisar rutas de evacuación",
                    "Verificar accesos, señalización y tiempos de salida en las laderas con "
                    "pendiente superior a 25 grados.",
                    "preventiva",
                    "7 días",
                    "La pendiente dificulta el acceso de brigadas y la evacuación; conviene "
                    "validarla en terreno.",
                )
            )
        actions.append(
            _action(
                "preposicionamiento_brigadas",
                "Coordinar preposicionamiento de brigadas",
                "Acordar con el organismo responsable el preposicionamiento de recursos y un "
                "canal directo de alerta para el sector.",
                "inmediata",
                "24 h",
                "Un riesgo Alto justifica reducir el tiempo de primera respuesta.",
            )
        )

    elif risk_level == "Medio":
        actions.append(
            _action(
                "patrullaje_preventivo",
                "Mantener patrullaje preventivo",
                "Incorporar el sector en la ronda semanal y registrar cambios de vegetación o "
                "acceso.",
                "preventiva",
                "7 días",
                base_rationale,
            )
        )
        if features["vegetation"] >= 0.5:
            actions.append(
                _action(
                    "mantencion_combustible",
                    "Mantener fajas de combustible",
                    "Revisar el estado de las fajas existentes y programar despeje si hay "
                    "acumulación de material seco.",
                    "preventiva",
                    "7 días",
                    "La vegetación combustible supera 0.50 y puede elevar el riesgo si empeora "
                    "el viento.",
                )
            )
        actions.append(
            _action(
                "verificacion_acceso",
                "Verificar accesos y señalización",
                "Comprobar que los accesos de emergencia estén despejados y correctamente "
                "señalizados.",
                "seguimiento",
                "30 días",
                "Mantener la accesibilidad reduce el tiempo de respuesta si el riesgo sube.",
            )
        )

    else:
        actions.append(
            _action(
                "monitoreo_rutinario",
                "Mantener monitoreo rutinario",
                "Continuar con la revisión periódica del sector y actualizar las variables cuando "
                "lleguen nuevos datos meteorológicos.",
                "seguimiento",
                "30 días",
                base_rationale,
            )
        )
        actions.append(
            _action(
                "mantencion_preventiva",
                "Mantener trabajo preventivo de temporada",
                "Aprovechar la ventana de bajo riesgo para revisar combustibles, accesos y "
                "coordinación con brigadas.",
                "preventiva",
                "temporada",
                "Las acciones preventivas en periodo de bajo riesgo reducen el costo de respuesta "
                "futura.",
            )
        )

    return actions[:5]
