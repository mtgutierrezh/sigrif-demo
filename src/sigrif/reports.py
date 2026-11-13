"""Reportes descargables por zona en CSV y PDF.

Los documentos resumen la última evaluación disponible y dejan explícito su
carácter académico: no reemplazan las plataformas oficiales de CONAF ni
SENAPRED.
"""

from __future__ import annotations

import csv
import io
import unicodedata
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Evaluation, Reading, Zone

DISCLAIMER = (
    "Reporte académico generado por SIGRIF. No reemplaza los sistemas oficiales "
    "de CONAF ni SENAPRED; úsese como apoyo a la priorización operativa y "
    "contrástese con la información de terreno."
)

VARIABLES: tuple[tuple[str, str, str], ...] = (
    ("temperature", "Temperatura", "°C"),
    ("humidity", "Humedad", "%"),
    ("wind_speed", "Viento", "km/h"),
    ("vegetation", "Vegetación", "índice"),
    ("historical_fires", "Incendios históricos", "eventos"),
    ("slope", "Pendiente", "°"),
)

CSV_HEADER = (
    "Zona",
    "Comuna",
    "Nivel de riesgo",
    "Score",
    "Modelo",
    "Fuente",
    "Fecha",
    "Variables",
    "Factores",
    "Escenario",
    "Acciones",
)

SUMMARY_HEADER = (
    "Zona",
    "Comuna",
    "Nivel de riesgo",
    "Score",
    "Modelo",
    "Fuente",
    "Fecha",
    "Acciones",
)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _float_text(value: Any, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _text(value)
    return f"{number:.{digits}f}"


def _date_text(evaluation: Evaluation, reading: Reading | None) -> str:
    value = getattr(reading, "observed_at", None) if reading is not None else None
    if value is None:
        value = getattr(evaluation, "created_at", None)
    if isinstance(value, datetime):
        return value.isoformat()
    return _text(value)


def _variables_text(features: dict[str, Any]) -> str:
    labels = {key: (label, unit) for key, label, unit in VARIABLES}
    parts = []
    for key, value in features.items():
        label, unit = labels.get(key, (key.replace("_", " ").capitalize(), ""))
        suffix = f" {unit}" if unit else ""
        parts.append(f"{label}: {_float_text(value)}{suffix}")
    return " | ".join(parts)


def _variable_rows(features: dict[str, Any]) -> list[list[str]]:
    labels = {key: (label, unit) for key, label, unit in VARIABLES}
    rows = []
    for key, value in features.items():
        label, unit = labels.get(key, (key.replace("_", " ").capitalize(), ""))
        rows.append([label, _float_text(value), unit])
    return rows


def _factors_text(factors: Sequence[dict[str, Any]]) -> str:
    parts = []
    for factor in factors:
        label = _text(factor.get("label") or factor.get("feature"))
        direction = _text(factor.get("direction"))
        impact = _float_text(factor.get("impact"))
        parts.append(f"{label}: {direction} (impacto {impact})")
    return "; ".join(part for part in parts if part.strip())


def _scenario_text(scenario: dict[str, Any] | None) -> str:
    if not scenario:
        return ""
    description = _text(scenario.get("description"))
    level = _text(scenario.get("risk_level"))
    score = _float_text(scenario.get("risk_score"))
    delta = _float_text(scenario.get("delta"))
    return f"{description} (nivel {level}, score {score}, delta {delta})"


def _actions_text(actions: Sequence[dict[str, Any]]) -> str:
    parts = []
    for action in actions:
        title = _text(action.get("title"))
        priority = _text(action.get("priority"))
        horizon = _text(action.get("horizon"))
        parts.append(f"{title} [{priority}, {horizon}]")
    return "; ".join(part for part in parts if part.strip())


def _csv_bytes(header: Sequence[str], rows: Sequence[Sequence[Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def zone_csv_bytes(
    zone: Zone,
    evaluation: Evaluation,
    reading: Reading | None,
    prescription: Sequence[dict[str, Any]],
) -> bytes:
    """Entrega una fila con el resumen completo de la última evaluación."""

    actions = prescription or evaluation.prescription or []
    row = [
        zone.name,
        zone.comuna,
        evaluation.risk_level,
        _float_text(evaluation.risk_score),
        evaluation.model_version,
        evaluation.source,
        _date_text(evaluation, reading),
        _variables_text(evaluation.features or {}),
        _factors_text(evaluation.factors or []),
        _scenario_text(evaluation.scenario),
        _actions_text(actions),
    ]
    return _csv_bytes(CSV_HEADER, [row])


def zones_summary_csv_bytes(rows: Sequence[tuple[Zone, Evaluation | None]]) -> bytes:
    """Exporta todas las zonas con las columnas resumidas del panel."""

    output = []
    for zone, evaluation in rows:
        if evaluation is None:
            output.append([zone.name, zone.comuna, "Sin evaluación", "", "", "", "", ""])
            continue
        output.append(
            [
                zone.name,
                zone.comuna,
                evaluation.risk_level,
                _float_text(evaluation.risk_score),
                evaluation.model_version,
                evaluation.source,
                _date_text(evaluation, None),
                _actions_text(evaluation.prescription or []),
            ]
        )
    return _csv_bytes(SUMMARY_HEADER, output)


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in normalized)
    return "-".join(part for part in cleaned.split("-") if part)


def report_filename(zone: Zone | None, extension: str, *, prefix: str = "sigrif") -> str:
    if zone is None:
        return f"{prefix}-zonas.{extension}"
    slug = _slug(zone.name) or f"zona-{zone.id}"
    return f"{prefix}-{slug}.{extension}"


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def zone_pdf_bytes(
    zone: Zone,
    evaluation: Evaluation,
    reading: Reading | None,
    prescription: Sequence[dict[str, Any]],
) -> bytes:
    """Construye un informe PDF legible con variables y acciones sugeridas."""

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"SIGRIF · {zone.name}",
        author="SIGRIF",
        subject="Reporte de riesgo de incendio",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SigrifTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#13140e"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "SigrifSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#555555"),
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "SigrifHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#13140e"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "SigrifBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#222222"),
        spaceAfter=5,
    )
    small_style = ParagraphStyle(
        "SigrifSmall",
        parent=body_style,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#555555"),
    )

    story: list[Any] = [
        Paragraph("SIGRIF", title_style),
        Paragraph("Reporte operativo de riesgo de incendio", subtitle_style),
    ]

    info_rows = [
        ["Comuna", _text(zone.comuna)],
        ["Zona", _text(zone.name)],
        ["Nivel de riesgo", _text(evaluation.risk_level)],
        ["Score", _float_text(evaluation.risk_score)],
        ["Fecha de evaluación", _date_text(evaluation, reading)],
        ["Fuente", _text(evaluation.source)],
        ["Modelo", _text(evaluation.model_version)],
    ]
    info_table = Table(info_rows, colWidths=[45 * mm, 125 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#222222")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ]
        )
    )
    story.append(info_table)

    story.append(Paragraph("Variables de la evaluación", heading_style))
    rows = _variable_rows(evaluation.features or {})
    if rows:
        variable_table = Table(
            [["Variable", "Valor", "Unidad"], *rows],
            colWidths=[80 * mm, 45 * mm, 45 * mm],
        )
        variable_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ebfc72")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(variable_table)
    else:
        story.append(_paragraph("Sin variables registradas.", body_style))

    story.append(Paragraph("Factores de mayor peso", heading_style))
    factors = evaluation.factors or []
    if factors:
        for factor in factors:
            label = _text(factor.get("label") or factor.get("feature"))
            direction = _text(factor.get("direction"))
            impact = _float_text(factor.get("impact"))
            story.append(
                _paragraph(f"• {label}: {direction} el riesgo (impacto {impact}).", body_style)
            )
    else:
        story.append(_paragraph("Sin factores registrados.", body_style))

    story.append(Paragraph("Escenario simulado", heading_style))
    scenario = _scenario_text(evaluation.scenario) or "Sin escenario simulado."
    story.append(_paragraph(scenario, body_style))

    story.append(Paragraph("Acciones prescriptivas", heading_style))
    actions = prescription or evaluation.prescription or []
    if actions:
        for index, action in enumerate(actions, start=1):
            title = _text(action.get("title"))
            priority = _text(action.get("priority"))
            horizon = _text(action.get("horizon"))
            description = _text(action.get("description"))
            rationale = _text(action.get("rationale"))
            story.append(
                _paragraph(
                    f"{index}. {title} [{priority}, {horizon}]",
                    ParagraphStyle(
                        "AccionTitulo",
                        parent=body_style,
                        fontName="Helvetica-Bold",
                        spaceAfter=1,
                    ),
                )
            )
            if description:
                story.append(_paragraph(description, body_style))
            if rationale:
                story.append(_paragraph(f"Justificación: {rationale}", small_style))
    else:
        story.append(_paragraph("Sin acciones prescriptivas registradas.", body_style))

    story.append(Spacer(1, 8 * mm))
    disclaimer = Table(
        [[_paragraph(DISCLAIMER, small_style)]],
        colWidths=[170 * mm],
    )
    disclaimer.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f2ec")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(disclaimer)

    document.build(story)
    return buffer.getvalue()
