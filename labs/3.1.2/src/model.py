"""Entrenamiento de un modelo académico para el laboratorio 3.1.2.

El objetivo es replicar el ejemplo de la guía: un clasificador simple que
aprende a partir de tres notas sintéticas si un estudiante aprueba o reprueba.
No se usan datos reales ni se pretende predecir el rendimiento de estudiantes
reales; es un ejercicio para entender el paso de entrenamiento y el consumo del
modelo mediante una API.
"""

from __future__ import annotations

import os

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

MODEL_PATH = "student_model.pkl"
RANDOM_STATE = 42
N_SAMPLES = 1000


def train_and_save_model(model_path: str = MODEL_PATH) -> RandomForestClassifier:
    """Genera datos sintéticos, entrena un Random Forest y guarda el artefacto."""

    # Datos sintéticos: tres notas parciales en escala chilena 1.0 a 7.0.
    rng = np.random.default_rng(RANDOM_STATE)
    features = rng.uniform(1.0, 7.0, (N_SAMPLES, 3))

    # Regla académica del ejercicio: se aprueba con promedio mayor o igual a 4.0.
    averages = np.mean(features, axis=1)
    labels = (averages >= 4.0).astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=labels,
    )

    classifier = RandomForestClassifier(
        n_estimators=100,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    classifier.fit(x_train, y_train)

    accuracy = classifier.score(x_test, y_test)
    print(f"Modelo entrenado. Precisión en test: {accuracy:.2f}")

    joblib.dump(classifier, model_path)
    print(f"Modelo guardado en {os.path.abspath(model_path)}")
    return classifier


if __name__ == "__main__":
    train_and_save_model()
