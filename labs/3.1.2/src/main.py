"""API del laboratorio 3.1.2: predicción y prescripción académica."""

from __future__ import annotations

import os
from typing import Annotated

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from model import MODEL_PATH, train_and_save_model

app = FastAPI(
    title="Student Success Predictor & Prescriptor",
    description=(
        "Microservicio académico que estima la probabilidad de aprobar con tres "
        "notas y, si el resultado es negativo, calcula una acción concreta para "
        "alcanzar el promedio mínimo de 4.0."
    ),
    version="1.0.0",
)

# El contenedor entrena el modelo antes de levantar Uvicorn; esta salvaguarda
# permite ejecutar la API directamente con `uvicorn main:app` durante el taller.
if not os.path.exists(MODEL_PATH):
    print("Modelo no encontrado. Entrenando...")
    train_and_save_model()

model = joblib.load(MODEL_PATH)

Grade = Annotated[float, Field(ge=1.0, le=7.0)]


class StudentGrades(BaseModel):
    """Tres notas parciales en escala chilena de 1.0 a 7.0."""

    grades: Annotated[list[Grade], Field(min_length=3, max_length=3)]


class PredictionResponse(BaseModel):
    prediction: str
    pass_probability: float
    input_grades: list[float]
    prescription: list[str]


@app.get("/", tags=["metadatos"])
def root() -> dict[str, str]:
    """Ruta de bienvenida con enlaces útiles para la revisión del laboratorio."""

    return {
        "service": "Student Success Predictor & Prescriptor",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["metadatos"])
def health() -> dict[str, str]:
    """Verificación simple usada por Docker Compose y por el smoke test."""

    return {"status": "ok", "model": "RandomForestClassifier"}


@app.post(
    "/predict_and_prescribe",
    response_model=PredictionResponse,
    tags=["predicción y prescripción"],
)
def analyze_student(data: StudentGrades) -> PredictionResponse:
    """Predice si el estudiante aprueba y prescribe cómo mejorar si no lo hace."""

    if len(data.grades) != 3:
        raise HTTPException(status_code=400, detail="Se requieren exactamente 3 notas.")

    input_data = np.array([data.grades], dtype=float)

    # 1. Predicción: el modelo entrega la clase y la probabilidad de aprobar.
    prediction = int(model.predict(input_data)[0])
    probability = float(model.predict_proba(input_data)[0][1])
    result = "Aprobado" if prediction == 1 else "Reprobado"

    # 2. Prescripción: traducimos el resultado a una acción concreta y factible.
    recommendations: list[str] = []
    if prediction == 1:
        recommendations.append(
            "El rendimiento actual es suficiente. Mantener el ritmo de estudio."
        )
    else:
        current_average = float(np.mean(data.grades))
        target_average = 4.0
        gap = target_average - current_average

        if gap > 0:
            min_grade_index = int(np.argmin(data.grades))
            min_grade_value = float(data.grades[min_grade_index])

            # Si la nota más baja se repite, el resto se mantiene:
            # (nota_nueva + resto) / 3 = 4.0  =>  nota_nueva = 12 - resto.
            current_sum_others = float(sum(data.grades) - min_grade_value)
            needed_grade = (target_average * 3.0) - current_sum_others

            recommendations.append(
                f"Crítico: el promedio actual es {current_average:.2f}. "
                f"Para aprobar, conviene enfocar los esfuerzos en la nota más baja "
                f"({min_grade_value:.2f}). Si se repite esa evaluación, se necesita "
                f"obtener al menos un {needed_grade:.2f}."
            )

            if needed_grade <= 7.0:
                recommendations.append(
                    "Estrategia: solicitar tutoría de refuerzo en la materia "
                    "correspondiente a la nota más baja y fijar una meta de evaluación."
                )
            else:
                recommendations.append(
                    "La meta supera la nota máxima de 7.0: no basta con mejorar una "
                    "sola evaluación. Se requiere un plan de recuperación en más de "
                    "una asignatura y acompañamiento académico."
                )

    return PredictionResponse(
        prediction=result,
        pass_probability=round(probability, 4),
        input_grades=data.grades,
        prescription=recommendations,
    )
