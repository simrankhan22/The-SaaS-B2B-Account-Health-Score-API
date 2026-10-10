"""Train and evaluate the baseline on a forward-in-time holdout."""

from __future__ import annotations

import json
from datetime import date

import joblib
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .data import build_training_data
from .model import (
    LOW_RISK_MAX,
    MEDIUM_RISK_MAX,
    MODEL_PATH,
    build_pipeline,
    build_tree_pipeline,
)


EVALUATION_START = date(2025, 7, 1)


def main() -> None:
    features, labels, snapshot_dates = build_training_data()
    # Purge snapshots whose 90-day label window reaches into the evaluation era.
    train_rows = [
        i
        for i, snapshot in enumerate(snapshot_dates)
        if snapshot.toordinal() + 90 < EVALUATION_START.toordinal()
    ]
    eval_rows = [i for i, snapshot in enumerate(snapshot_dates) if snapshot >= EVALUATION_START]
    if not train_rows or not eval_rows:
        raise ValueError("The point-in-time data must contain both training and later evaluation months.")

    x_train = [features[i] for i in train_rows]
    y_train = [labels[i] for i in train_rows]
    x_eval = [features[i] for i in eval_rows]
    y_eval = [labels[i] for i in eval_rows]
    if len(set(y_train)) < 2 or len(set(y_eval)) < 2:
        raise ValueError("Both time partitions need positive and negative labels.")

    model_builders = {
        "logistic_regression": build_pipeline,
        "random_forest": build_tree_pipeline,
    }
    comparison: dict[str, dict[str, object]] = {}
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    for model_name, build in model_builders.items():
        pipeline = build()
        pipeline.fit(x_train, y_train)
        probabilities = pipeline.predict_proba(x_eval)[:, 1]
        predictions = [int(value >= MEDIUM_RISK_MAX) for value in probabilities]
        metrics = {
            "model": model_name,
            "prediction_horizon_days": 90,
            "target_definition": "account_churn_date_within_90d",
            "evaluation_start": EVALUATION_START.isoformat(),
            "training_rows": len(train_rows),
            "training_positive_rate": sum(y_train) / len(y_train),
            "evaluation_rows": len(eval_rows),
            "evaluation_positive_rate": sum(y_eval) / len(y_eval),
            "roc_auc": roc_auc_score(y_eval, probabilities),
            "average_precision": average_precision_score(y_eval, probabilities),
            "brier_score": brier_score_loss(y_eval, probabilities),
            "precision_at_high_risk_threshold": precision_score(
                y_eval, predictions, zero_division=0
            ),
            "recall_at_high_risk_threshold": recall_score(
                y_eval, predictions, zero_division=0
            ),
            "high_risk_threshold": MEDIUM_RISK_MAX,
            "risk_tier_thresholds": {
                "low_below": LOW_RISK_MAX,
                "medium_below": MEDIUM_RISK_MAX,
            },
        }
        comparison[model_name] = metrics
        bundle = {
            "pipeline": pipeline,
            "prediction_horizon_days": 90,
            "feature_names": list(features[0]),
            "metrics": metrics,
        }
        candidate_path = MODEL_PATH.with_name(f"churn_model_{model_name}.joblib")
        joblib.dump(bundle, candidate_path)
        if model_name == "logistic_regression":
            joblib.dump(bundle, MODEL_PATH)
            (MODEL_PATH.parent / "metrics.json").write_text(
                json.dumps(metrics, indent=2), encoding="utf-8"
            )
        print(json.dumps(metrics, indent=2))
        print(f"Saved model: {candidate_path}")

    comparison_path = MODEL_PATH.parent / "model_comparison.json"
    comparison_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(f"Saved comparison: {comparison_path}")


if __name__ == "__main__":
    main()
