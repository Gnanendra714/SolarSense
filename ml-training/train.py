"""Train and evaluate the SolarSense Random Forest classifier.

Required CSV columns:
timestamp, session_id, source, voltage_v, current_a, panel_temp_c, light_lux, label

Only physical hardware readings are accepted. Simulated and legacy records are rejected.
Only labelled, real measurements should be used for real-world evaluation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, classification_report, ConfusionMatrixDisplay,
    confusion_matrix, f1_score, precision_score, recall_score,
)
from sklearn.model_selection import GroupShuffleSplit

REQUIRED = [
    "timestamp", "session_id", "source", "voltage_v", "current_a", "panel_temp_c", "light_lux", "label"
]
BASE_FEATURES = ["voltage_v", "current_a", "panel_temp_c", "light_lux", "power_w"]
VALID_LABELS = {
    "normal", "partial_shading", "dust_accumulation", "electrical_fault"
}


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}\n"
            "Add labelled CSV measurements under datasets/ before training."
        )
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required CSV columns: {missing}")
    df = df.copy()
    df["source"] = df["source"].astype("string").str.strip().str.lower()
    non_hardware = sorted(set(df["source"].dropna()) - {"hardware"})
    if non_hardware:
        raise ValueError(f"Training accepts hardware data only; found sources: {non_hardware}")
    numeric = ["voltage_v", "current_a", "panel_temp_c", "light_lux"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["session_id"] = df["session_id"].astype("string").str.strip()
    df["label"] = df["label"].astype("string").str.strip().str.lower()
    df = df.dropna(subset=REQUIRED)
    df = df[np.isfinite(df[numeric]).all(axis=1)]
    df = df[(df["current_a"] >= 0) & (df["voltage_v"] >= 0) & (df["light_lux"] >= 0)]
    if (df["session_id"] == "").any():
        raise ValueError("Every labelled hardware reading must have a non-empty session_id.")
    df["power_w"] = df["voltage_v"] * df["current_a"]
    unknown = sorted(set(df["label"].dropna()) - VALID_LABELS)
    if unknown:
        raise ValueError(f"Unsupported labels: {unknown}. Allowed: {sorted(VALID_LABELS)}")
    if df.empty:
        raise ValueError("No valid labelled rows remain after validation.")
    return df


def split_data(df: pd.DataFrame, test_size: float, seed: int):
    X = df[BASE_FEATURES]
    y = df["label"]
    groups = df["session_id"].astype(str)
    for label in sorted(VALID_LABELS):
        sessions = df.loc[df["label"] == label, "session_id"].nunique()
        if sessions < 2:
            raise ValueError(
                f"Class '{label}' needs readings from at least 2 independent physical sessions; found {sessions}."
            )
    splitter = GroupShuffleSplit(n_splits=100, test_size=test_size, random_state=seed)
    for train_idx, test_idx in splitter.split(X, y, groups):
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        if set(y_train) == VALID_LABELS and set(y_test) == VALID_LABELS:
            return X.iloc[train_idx], X.iloc[test_idx], y_train, y_test, "grouped_by_session"
    raise ValueError(
        "Could not create a session-independent split containing all four classes in both partitions. "
        "Collect more independent labelled hardware sessions per class."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="datasets/solarsense_readings.csv")
    parser.add_argument("--output", default="artifacts")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = root / data_path
    out = Path(args.output)
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)

    df = load_dataset(data_path)
    counts = df["label"].value_counts()
    absent = sorted(VALID_LABELS - set(counts.index))
    if absent:
        raise ValueError(f"Training data must contain all four classes. Missing: {absent}")
    if counts.min() < 5:
        raise ValueError("Each class needs at least 5 labelled samples for a meaningful initial split.")

    X_train, X_test, y_train, y_test, split_method = split_data(df, args.test_size, args.seed)
    if set(y_train) != VALID_LABELS or set(y_test) != VALID_LABELS:
        raise ValueError(
            "The selected split does not contain every class in both partitions. "
            "Collect more labelled sessions per class and retry."
        )

    model = RandomForestClassifier(
        n_estimators=300, max_depth=None, min_samples_leaf=2,
        class_weight="balanced_subsample", random_state=args.seed,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    labels = sorted(VALID_LABELS)

    metrics = {
        "dataset_rows": int(len(df)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "split_method": split_method,
        "class_counts": {k: int(v) for k, v in counts.items()},
        "accuracy": float(accuracy_score(y_test, pred)),
        "macro_precision": float(precision_score(y_test, pred, labels=labels, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_test, pred, labels=labels, average="macro", zero_division=0)),
        "macro_f1": float(f1_score(y_test, pred, labels=labels, average="macro", zero_division=0)),
        "classification_report": classification_report(
            y_test, pred, labels=labels, output_dict=True, zero_division=0
        ),
        "feature_importance": {
            name: float(value) for name, value in zip(BASE_FEATURES, model.feature_importances_)
        },
        "dataset_file": data_path.name,
        "data_source_note": "Metrics are only as representative as the labelled dataset and split design.",
    }

    # This is the exact artifact shape and feature order consumed by the backend predictor.
    joblib.dump(model, out / "model.joblib")
    metadata = {
        "model_version": "1.0.0",
        "feature_names": BASE_FEATURES,
        "classes": labels,
        "training_source": "physical_hardware_only",
        "split_method": split_method,
        "metrics_file": "metrics.json",
    }
    (out / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out / "classification_report.txt").write_text(
        classification_report(y_test, pred, labels=labels, zero_division=0),
        encoding="utf-8",
    )
    cm = confusion_matrix(y_test, pred, labels=labels)
    disp = ConfusionMatrixDisplay(cm, display_labels=labels)
    fig, ax = plt.subplots(figsize=(8, 6))
    disp.plot(ax=ax, xticks_rotation=25, colorbar=False)
    fig.tight_layout()
    fig.savefig(out / "confusion_matrix.png", dpi=160)
    plt.close(fig)

    print(json.dumps({
        "status": "TRAINING_COMPLETE",
        "metrics": {k: metrics[k] for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "split_method")},
        "artifacts": str(out),
        "warning": "Do not interpret synthetic/demo-data metrics as real-world accuracy.",
    }, indent=2))


if __name__ == "__main__":
    main()
