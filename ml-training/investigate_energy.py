import pandas as pd
from pathlib import Path

BASE = Path("ml-training/datasets")
INPUT = BASE / "solarsense_features_unlabelled.csv"
OUTPUT = BASE / "energy_investigation.csv"
REPORT = BASE / "energy_investigation_report.txt"

df = pd.read_csv(INPUT)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
df["energy_wh"] = pd.to_numeric(df["energy_wh"], errors="coerce")

df = df.dropna(subset=["timestamp", "energy_wh"])
df = df.sort_values(["source", "timestamp"]).reset_index(drop=True)

# Inspect energy changes separately for each source
groups = df.groupby("source", sort=False)
df["energy_change_wh"] = groups["energy_wh"].diff()

df["energy_reset_candidate"] = df["energy_change_wh"] < 0
df["energy_unchanged"] = df["energy_change_wh"] == 0
df["energy_increase"] = df["energy_change_wh"] > 0

# Identify records previously flagged by the IQR method
flag_col = "energy_wh_potential_outlier"
if flag_col in df.columns:
    flagged = df[df[flag_col].astype(str).str.lower().isin(["true", "1"])]
else:
    flagged = pd.DataFrame()

# Save all records with energy diagnostics
df.to_csv(OUTPUT, index=False)

lines = [
    "SOLARSENSE ENERGY INVESTIGATION",
    "=" * 50,
    f"Total records: {len(df)}",
    f"Sources: {df['source'].value_counts().to_dict()}",
    "",
    "ENERGY CHANGE SUMMARY",
    str(df.groupby("source")["energy_change_wh"].agg(
        ["count", "mean", "median", "min", "max"]
    )),
    "",
    "ENERGY BEHAVIOUR",
    f"Energy increases: {int(df['energy_increase'].sum())}",
    f"Energy unchanged: {int(df['energy_unchanged'].sum())}",
    f"Energy decreases / reset candidates: {int(df['energy_reset_candidate'].sum())}",
    "",
    "PREVIOUSLY FLAGGED ENERGY OUTLIERS",
    f"Flagged records: {len(flagged)}",
    flagged[[
        "timestamp", "source", "energy_wh",
        "energy_change_wh", "energy_reset_candidate"
    ]].to_string(index=False) if not flagged.empty else "No flagged records found.",
    "",
    "SOURCE-WISE RESET CANDIDATES",
    str(df.groupby("source")["energy_reset_candidate"].sum()),
    "",
    "IMPORTANT",
    "A decrease is only a possible counter reset, not proof of one.",
    "Energy behaviour must be interpreted using the backend's accumulation logic.",
    "No readings have been deleted or modified."
]

REPORT.write_text("\n".join(lines), encoding="utf-8")

print("\n===== ENERGY INVESTIGATION =====")
print("Total records:", len(df))
print("\nEnergy changes by source:")
print(df.groupby("source")["energy_change_wh"].agg(
    ["count", "mean", "median", "min", "max"]
))
print("\nEnergy increases:", int(df["energy_increase"].sum()))
print("Energy unchanged:", int(df["energy_unchanged"].sum()))
print("Energy decreases/reset candidates:", int(df["energy_reset_candidate"].sum()))
print("\nPreviously flagged energy records:", len(flagged))

if not flagged.empty:
    print(flagged[[
        "timestamp", "source", "energy_wh",
        "energy_change_wh", "energy_reset_candidate"
    ]].to_string(index=False))

print("\nDetailed CSV:", OUTPUT.resolve())
print("Report:", REPORT.resolve())
print("================================")
