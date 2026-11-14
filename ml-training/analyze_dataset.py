import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path("ml-training/datasets")
INPUT = BASE / "solarsense_readings_unlabelled.csv"
OUTPUT = BASE / "solarsense_features_unlabelled.csv"
REPORT = BASE / "dataset_analysis_report.txt"

df = pd.read_csv(INPUT)

numeric = [
    "voltage_v", "current_a", "power_w",
    "panel_temp_c", "light_lux", "energy_wh"
]

for col in numeric:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
df = df.dropna(subset=["timestamp"] + numeric)
df = df.sort_values(["source", "timestamp"]).reset_index(drop=True)

# Physical consistency check: P = V x I
df["calculated_power_w"] = df["voltage_v"] * df["current_a"]
df["power_error_w"] = df["power_w"] - df["calculated_power_w"]
df["absolute_power_error_w"] = df["power_error_w"].abs()

# Time interval and change features, calculated separately by source
groups = df.groupby("source", sort=False)

df["sample_interval_s"] = groups["timestamp"].diff().dt.total_seconds()

for col, feature in [
    ("voltage_v", "voltage_delta_v"),
    ("current_a", "current_delta_a"),
    ("power_w", "power_delta_w"),
    ("panel_temp_c", "temperature_delta_c"),
    ("light_lux", "light_delta_lux")
]:
    df[feature] = groups[col].diff()

# IQR-based potential outlier flags (not fault labels)
outlier_columns = []
for col in numeric:
    q1 = df[col].quantile(0.25)
    q3 = df[col].quantile(0.75)
    iqr = q3 - q1
    flag = f"{col}_potential_outlier"
    df[flag] = (df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)
    outlier_columns.append(flag)

# Export without replacing or inventing labels
df["timestamp"] = df["timestamp"].astype(str)
df.to_csv(OUTPUT, index=False)

lines = []
lines.append("SOLARSENSE - DATASET ANALYSIS REPORT")
lines.append("=" * 50)
lines.append(f"Rows analysed: {len(df)}")
lines.append(f"Sources: {df['source'].value_counts().to_dict()}")
lines.append(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
lines.append(f"Duplicate reading IDs: {df['reading_id'].duplicated().sum()}")
lines.append(f"Missing values: {df.isna().sum().to_dict()}")

lines.append("\nNUMERICAL SUMMARY")
lines.append(df.groupby("source")[numeric].agg(["mean", "std", "min", "max"]).to_string())

lines.append("\nPOWER CONSISTENCY")
lines.append(f"Mean absolute difference between recorded and V x I power: {df['absolute_power_error_w'].mean():.6f} W")
lines.append(f"Maximum absolute difference: {df['absolute_power_error_w'].max():.6f} W")

lines.append("\nSAMPLING INTERVALS")
lines.append(df.groupby("source")["sample_interval_s"].agg(["count", "mean", "median", "min", "max"]).to_string())

lines.append("\nPOTENTIAL OUTLIERS (IQR METHOD)")
for col in outlier_columns:
    lines.append(f"{col}: {int(df[col].sum())}")

lines.append("\nIMPORTANT")
lines.append("IQR flags indicate statistical extremes, not confirmed equipment faults.")
lines.append("Simulated and legacy readings are kept separate.")
lines.append("No fault labels have been invented.")
lines.append("BH1750 measurements are lux, not irradiance in W/m2.")

REPORT.write_text("\n".join(lines), encoding="utf-8")

print("\n===== SOLARSENSE EDA COMPLETE =====")
print("Rows analysed:", len(df))
print("\nSource distribution:")
print(df["source"].value_counts())
print("\nMean absolute power difference:", round(df["absolute_power_error_w"].mean(), 6), "W")
print("\nSampling intervals:")
print(df.groupby("source")["sample_interval_s"].median())
print("\nPotential outliers:")
for col in outlier_columns:
    print(col, ":", int(df[col].sum()))
print("\nFEATURE DATASET:", OUTPUT.resolve())
print("ANALYSIS REPORT:", REPORT.resolve())
print("===================================")
