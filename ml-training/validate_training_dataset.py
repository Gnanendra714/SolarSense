from pathlib import Path
import sys
import pandas as pd

DATA = Path(__file__).parent / "datasets" / "solarsense_labelled_training.csv"
REQUIRED = [
    "timestamp", "reading_id", "session_id", "source",
    "voltage_v", "current_a", "panel_temp_c", "light_lux",
    "label"
]
CLASSES = {"normal", "partial_shading", "dust_accumulation", "electrical_fault"}

def main():
    if not DATA.exists():
        print(f"Training file not found: {DATA}")
        return 2

    df = pd.read_csv(DATA)
    missing_cols = [c for c in REQUIRED if c not in df.columns]
    if missing_cols:
        print("Missing required columns:", ", ".join(missing_cols))
        return 2

    print("\n===== SOLARSENSE TRAINING DATA READINESS =====")
    print("Rows:", len(df))
    print("Sources:", df["source"].value_counts(dropna=False).to_dict())
    print("Labels:", df["label"].value_counts(dropna=False).to_dict())

    numeric = ["voltage_v", "current_a", "panel_temp_c", "light_lux"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    problems = []
    if df[REQUIRED].isna().any().any():
        problems.append("Missing values exist in required fields.")
    if df["reading_id"].duplicated().any():
        problems.append("Duplicate reading_id values exist.")
    if (df["current_a"] < 0).any():
        problems.append("Negative current values exist.")
    unknown = set(df["label"].dropna().astype(str).unique()) - CLASSES
    if unknown:
        problems.append(f"Unknown labels: {sorted(unknown)}")
    if set(df["source"].dropna().astype(str).unique()) != {"hardware"}:
        problems.append("Only source=hardware rows are accepted for real-world classifier training.")

    counts = df["label"].value_counts()
    for label in sorted(CLASSES):
        count = int(counts.get(label, 0))
        print(f"{label}: {count}")
        if count < 5:
            problems.append(f"Class '{label}' has {count} rows; at least 5 are required for a basic split.")
    if df["session_id"].nunique(dropna=True) < 2:
        problems.append("At least two distinct session_id groups are required for group-based evaluation.")

    if problems:
        print("\nSTATUS: NOT READY")
        for item in problems:
            print("-", item)
        print("\nDo not train a classifier on this dataset yet.")
        return 1

    print("\nSTATUS: BASIC DATA CHECKS PASSED")
    print("This is only a readiness check; review class balance and experimental ground truth before training.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
