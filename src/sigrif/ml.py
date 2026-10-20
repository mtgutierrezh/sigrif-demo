import numpy as np
from sklearn.ensemble import RandomForestClassifier

LABELS = ("Bajo", "Medio", "Alto")


def _synthetic_dataset(size: int = 600, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    temperature = rng.uniform(5, 40, size)
    humidity = rng.uniform(10, 90, size)
    wind_speed = rng.uniform(0, 80, size)
    vegetation = rng.uniform(0, 1, size)
    slope = rng.uniform(0, 45, size)
    score = (
        0.35 * (temperature / 40)
        + 0.25 * (1 - humidity / 100)
        + 0.20 * (wind_speed / 80)
        + 0.15 * vegetation
        + 0.05 * (slope / 45)
    )
    labels = np.where(score > 0.62, 2, np.where(score > 0.42, 1, 0))
    features = np.column_stack([temperature, humidity, wind_speed, vegetation, slope])
    return features, labels


class RiskModel:
    def __init__(self) -> None:
        features, labels = _synthetic_dataset()
        self._model = RandomForestClassifier(
            n_estimators=120, max_depth=8, random_state=42, n_jobs=-1
        )
        self._model.fit(features, labels)

    def predict(self, values: list[float]) -> tuple[str, float]:
        probabilities = self._model.predict_proba([values])[0]
        index = int(probabilities.argmax())
        return LABELS[index], round(float(probabilities[index]), 4)


risk_model = RiskModel()
