"""Model construction and reusable account scoring helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "artifacts" / "churn_model.joblib"
# Provisional demo boundaries, expressed as 90-day account churn probability.
# Revisit these with Customer Success capacity and a stronger validation set.
LOW_RISK_MAX = 0.12
MEDIUM_RISK_MAX = 0.16


def build_pipeline() -> Pipeline:
    """Create a compact, explainable logistic-regression pipeline."""
    return Pipeline(
        steps=[
            ("encode", DictVectorizer(sparse=False)),
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=2_000)),
        ]
    )


def build_tree_pipeline() -> Pipeline:
    """Build a restrained random forest candidate for nonlinear comparisons."""
    return Pipeline(
        steps=[
            ("encode", DictVectorizer(sparse=False)),
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=5,
                    min_samples_leaf=20,
                    class_weight="balanced_subsample",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def risk_tier(probability: float) -> str:
    if probability < LOW_RISK_MAX:
        return "Low"
    if probability < MEDIUM_RISK_MAX:
        return "Medium"
    return "High"


def load_bundle() -> dict[str, Any]:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model artifact not found at {MODEL_PATH}. Run `python -m src.saas_health.train`."
        )
    return joblib.load(MODEL_PATH)


def score_features(bundle: dict[str, Any], features: dict[str, Any]) -> float:
    probability = bundle["pipeline"].predict_proba([features])[0][1]
    return float(probability)
