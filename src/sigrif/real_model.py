from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class TabularPreprocessor(BaseEstimator, TransformerMixin):
    """Imputación, escalado y one-hot para filas representadas como diccionarios."""

    def __init__(self, numeric_features: Sequence[str], categorical_features: Sequence[str]):
        self.numeric_features = numeric_features
        self.categorical_features = categorical_features

    def _numeric_matrix(self, rows: Sequence[dict[str, Any]]) -> np.ndarray:
        matrix = np.empty((len(rows), len(self.numeric_features)), dtype=float)
        for row_index, row in enumerate(rows):
            for column_index, name in enumerate(self.numeric_features):
                value = row.get(name)
                if value is None or value == "":
                    matrix[row_index, column_index] = np.nan
                else:
                    try:
                        matrix[row_index, column_index] = float(value)
                    except (TypeError, ValueError):
                        matrix[row_index, column_index] = np.nan
        return matrix

    def _categorical_matrix(self, rows: Sequence[dict[str, Any]]) -> np.ndarray:
        matrix = np.empty((len(rows), len(self.categorical_features)), dtype=object)
        for row_index, row in enumerate(rows):
            for column_index, name in enumerate(self.categorical_features):
                value = row.get(name)
                matrix[row_index, column_index] = (
                    "__MISSING__" if value in (None, "") else str(value)
                )
        return matrix

    def fit(self, X: Sequence[dict[str, Any]], y: Any = None) -> TabularPreprocessor:
        rows = list(X)
        if not rows:
            raise ValueError("No hay filas para ajustar el preprocesador")
        numeric = self._numeric_matrix(rows)
        self.numeric_imputer_ = SimpleImputer(strategy="median")
        numeric_imputed = self.numeric_imputer_.fit_transform(numeric)
        self.numeric_scaler_ = StandardScaler()
        self.numeric_scaler_.fit(numeric_imputed)
        categorical = self._categorical_matrix(rows)
        self.categorical_imputer_ = SimpleImputer(strategy="constant", fill_value="__MISSING__")
        categorical_imputed = self.categorical_imputer_.fit_transform(categorical)
        self.categorical_encoder_ = OneHotEncoder(
            handle_unknown="ignore",
            sparse_output=False,
            dtype=np.float64,
        )
        self.categorical_encoder_.fit(categorical_imputed)
        self.n_features_in_ = len(self.numeric_features) + len(self.categorical_features)
        self.feature_names_out_ = self._build_feature_names()
        return self

    def transform(self, X: Sequence[dict[str, Any]]) -> np.ndarray:
        rows = list(X)
        numeric = self._numeric_matrix(rows)
        numeric = self.numeric_imputer_.transform(numeric)
        numeric = self.numeric_scaler_.transform(numeric)
        categorical = self._categorical_matrix(rows)
        categorical = self.categorical_imputer_.transform(categorical)
        categorical = self.categorical_encoder_.transform(categorical)
        return np.hstack([numeric, categorical])

    def _build_feature_names(self) -> list[str]:
        numeric_names = [f"num__{name}" for name in list(self.numeric_features)]
        categorical_names = list(
            self.categorical_encoder_.get_feature_names_out(list(self.categorical_features))
        )
        return numeric_names + [f"cat__{name}" for name in categorical_names]

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray:
        if not hasattr(self, "feature_names_out_"):
            raise ValueError("El preprocesador no ha sido ajustado")
        return np.asarray(self.feature_names_out_, dtype=object)
