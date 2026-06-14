"""
Meridian Ops Intelligence — Fraud Detection Model
Champion/challenger comparison: Logistic Regression vs Random Forest,
trained on transaction-level features to predict is_flagged.

Feature selection deliberately excludes the rule_* columns and
rules_triggered_count / any_rule_triggered, since those are derived from
near-identical logic to the is_flagged generation process and would cause
target leakage (mirrors the leakage issue identified in the IFRS 9 project).

Outputs:
  - ml/output/fraud_model_champion.pkl (best model)
  - ml/output/fraud_model_metrics.json (AUC, precision/recall, feature importance)
  - ml/output/roc_curve_data.csv (for dashboard plotting)
  - ml/output/precision_recall_data.csv
  - ml/output/feature_importance.csv
"""

import duckdb
import pandas as pd
import numpy as np
import json
import os
import pickle

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, roc_curve, precision_recall_curve, classification_report

DB_PATH = "data/meridian.duckdb"
OUTPUT_DIR = "ml/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Feature selection ──────────────────────────────────────────────────────
# Observable, pre-decision features only. Excludes rule_* flags and
# rules_triggered_count/any_rule_triggered (target-leakage risk — these are
# constructed from logic that overlaps heavily with is_flagged generation).
NUMERIC_FEATURES = [
    "amount_gbp",
    "user_baseline_amount",
    "amount_to_baseline_ratio",
    "velocity_count_1h",
    "is_late_night",
    "is_new_account_tx",
    "is_round_amount",
    "is_high_risk_merchant",
    "is_high_risk_geography",
]
CATEGORICAL_FEATURES = [
    "transaction_type",
    "merchant_category",
    "geography",
]
TARGET = "is_flagged"


def load_data():
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute("select * from analytics.int_transaction_fraud_features").df()
    con.close()
    return df


def build_pipeline(model):
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", "passthrough", NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def get_feature_names(pipeline):
    preprocessor = pipeline.named_steps["preprocess"]
    cat_encoder = preprocessor.named_transformers_["cat"]
    cat_names = list(cat_encoder.get_feature_names_out(CATEGORICAL_FEATURES))
    return NUMERIC_FEATURES + cat_names


def main():
    print("Loading data...")
    df = load_data()
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    print(f"Train: {len(X_train):,} | Test: {len(X_test):,} | Positive rate (train): {y_train.mean():.4f}")

    # ── Champion: Logistic Regression ──────────────────────────────────────
    print("\nTraining Logistic Regression...")
    lr_pipeline = build_pipeline(LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42))
    lr_pipeline.fit(X_train, y_train)
    lr_probs = lr_pipeline.predict_proba(X_test)[:, 1]
    lr_auc = roc_auc_score(y_test, lr_probs)
    print(f"  Logistic Regression AUC: {lr_auc:.4f}")

    # ── Challenger: Random Forest ──────────────────────────────────────────
    print("\nTraining Random Forest...")
    rf_pipeline = build_pipeline(RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=20,
        class_weight="balanced", random_state=42, n_jobs=-1
    ))
    rf_pipeline.fit(X_train, y_train)
    rf_probs = rf_pipeline.predict_proba(X_test)[:, 1]
    rf_auc = roc_auc_score(y_test, rf_probs)
    print(f"  Random Forest AUC:       {rf_auc:.4f}")

    # ── Select champion ─────────────────────────────────────────────────────
    if rf_auc >= lr_auc:
        champion_name, champion_pipeline, champion_probs, champion_auc = "random_forest", rf_pipeline, rf_probs, rf_auc
        challenger_name, challenger_auc = "logistic_regression", lr_auc
    else:
        champion_name, champion_pipeline, champion_probs, champion_auc = "logistic_regression", lr_pipeline, lr_probs, lr_auc
        challenger_name, challenger_auc = "random_forest", rf_auc

    print(f"\nChampion model: {champion_name} (AUC {champion_auc:.4f} vs {challenger_name} AUC {challenger_auc:.4f})")

    # ── ROC curve data (for both models, for dashboard comparison) ─────────
    fpr_lr, tpr_lr, _ = roc_curve(y_test, lr_probs)
    fpr_rf, tpr_rf, _ = roc_curve(y_test, rf_probs)

    roc_df = pd.concat([
        pd.DataFrame({"model": "logistic_regression", "fpr": fpr_lr, "tpr": tpr_lr}),
        pd.DataFrame({"model": "random_forest", "fpr": fpr_rf, "tpr": tpr_rf}),
    ])
    roc_df.to_csv(f"{OUTPUT_DIR}/roc_curve_data.csv", index=False)

    # ── Feature importance ───────────────────────────────────────────────────
    feature_names = get_feature_names(champion_pipeline)
    model_step = champion_pipeline.named_steps["model"]

    if champion_name == "random_forest":
        importances = model_step.feature_importances_
    else:
        importances = np.abs(model_step.coef_[0])

    importance_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importances
    }).sort_values("importance", ascending=False)
    importance_df.to_csv(f"{OUTPUT_DIR}/feature_importance.csv", index=False)

    print("\nTop 10 features:")
    print(importance_df.head(10).to_string(index=False))

    # ── Classification report at default 0.5 threshold ──────────────────────
    preds = (champion_probs >= 0.5).astype(int)
    report = classification_report(y_test, preds, output_dict=True)

    # ── Precision-recall curve (useful given class imbalance) ────────────────
    prec, rec, pr_thresholds = precision_recall_curve(y_test, champion_probs)
    pr_df = pd.DataFrame({
        "precision": prec[:-1], "recall": rec[:-1], "threshold": pr_thresholds
    })
    pr_df.to_csv(f"{OUTPUT_DIR}/precision_recall_data.csv", index=False)

    # ── Save model and metrics ───────────────────────────────────────────────
    with open(f"{OUTPUT_DIR}/fraud_model_champion.pkl", "wb") as f:
        pickle.dump(champion_pipeline, f)

    metrics = {
        "champion_model": champion_name,
        "champion_auc": round(champion_auc, 4),
        "challenger_model": challenger_name,
        "challenger_auc": round(challenger_auc, 4),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "positive_rate": round(float(y.mean()), 4),
        "classification_report": report,
        "top_features": importance_df.head(10).to_dict(orient="records"),
    }
    with open(f"{OUTPUT_DIR}/fraud_model_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\nSaved model + metrics to {OUTPUT_DIR}/")
    return metrics


if __name__ == "__main__":
    main()
