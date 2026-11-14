import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path("ml-training/datasets")
INPUT = BASE / "solarsense_readings_unlabelled.csv"
OUTPUT = BASE / "solarsense_features_v2.csv"
REPORT = BASE / "ml_data_quality_report.txt"

df = pd.read_csv(INPUT)

# Validate and prepare
required = [
    "timestamp", "reading_id", "source", "voltage_v",
    "current_a", "power_w", "panel_temp_c", "light_lux", "energy_wh"
]
missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"Missing required columns: {missing}")

df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

numeric = [
    "voltage_v", "current_a", "power_w",
    "panel_temp_c", "light_lux", "energy_wh"
]
for col in numeric:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df.dropna(subset=["timestamp"] + numeric + ["source"])
df = df.sort_values("timestamp").reset_index(drop=True)

# Explicitly identify interval energy
df = df.rename(columns={"energy_wh": "interval_energy_wh"})

numeric = [
    "voltage_v", "current_a", "power_w",
    "panel_temp_c", "light_lux", "interval_energy_wh"
]

# Verify power = voltage x current
df["calculated_power_w"] = df["voltage_v"] * df["current_a"]
df["power_error_w"] = df["power_w"] - df["calculated_power_w"]

# Reconstruct expected interval energy using chronological readings
df["elapsed_seconds"] = df["timestamp"].diff().dt.total_seconds()
df["previous_power_w"] = df["power_w"].shift(1)

valid_interval = (
    df["elapsed_seconds"].gt(0) &
    df["elapsed_seconds"].le(900)
)

df["expected_interval_energy_wh"] = 0.0
df.loc[valid_interval, "expected_interval_energy_wh"] = (
    (df.loc[valid_interval, "previous_power_w"] +
     df.loc[valid_interval, "power_w"]) / 2
    * df.loc[valid_interval, "elapsed_seconds"] / 3600
).clip(lower=0)

df["interval_energy_error_wh"] = (
    df["interval_energy_wh"] - df["expected_interval_energy_wh"]
)
df["interval_energy_match"] = (
    df["interval_energy_error_wh"].abs() <= 0.000001
)

# Time-series features, separately within each source
groups = df.groupby("source", sort=False)

for col, feature in [
    ("voltage_v", "voltage_delta_v"),
    ("current_a", "current_delta_a"),
    ("power_w", "power_delta_w"),
    ("panel_temp_c", "temperature_delta_c"),
    ("light_lux", "light_delta_lux")
]:
    df[feature] = groups[col].diff()

# Rolling power features: past readings only
df["power_rolling_mean_3"] = groups["power_w"].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean()
)
df["power_rolling_std_3"] = groups["power_w"].transform(
    lambda x: x.shift(1).rolling(3, min_periods=2).std()
)

# Statistical flags are not fault labels
for col in numeric:
    source_q = df.groupby("source")[col]
    q1 = source_q.transform(lambda x: x.quantile(0.25))
    q3 = source_q.transform(lambda x: x.quantile(0.75))
    iqr = q3 - q1
    df[f"{col}_potential_outlier"] = (
        (df[col] < q1 - 1.5 * iqr) |
        (df[col] > q3 + 1.5 * iqr)
    )

# Never invent labels
df["label"] = ""

df["timestamp"] = df["timestamp"].astype(str)
df.to_csv(OUTPUT, index=False)

# Quality report
lines = [
    "SOLARSENSE ML DATA QUALITY REPORT",
    "=" * 55,
    f"Rows retained: {len(df)}",
    f"Source distribution: {df['source'].value_counts().to_dict()}",
    f"Duplicate IDs: {df['reading_id'].duplicated().sum()}",
    f"Missing values: {df.isna().sum().to_dict()}",
    "",
    "POWER CONSISTENCY",
    f"Mean absolute power error: {df['power_error_w'].abs().mean():.9f} W",
    "",
    "INTERVAL ENERGY VERIFICATION",
    f"Comparable intervals: {int(valid_interval.sum())}",
    f"Matching intervals: {int(df.loc[valid_interval, 'interval_energy_match'].sum())}",
    f"Mismatching intervals: {int((~df.loc[valid_interval, 'interval_energy_match']).sum())}",
    f"Mean absolute energy error: {df.loc[valid_interval, 'interval_energy_error_wh'].abs().mean():.9f} Wh",
    "",
    "SAMPLING INTERVALS",
    str(df.groupby("source")["elapsed_seconds"].agg(
        ["count", "median", "min", "max"]
    )),
    "",
    "POTENTIAL OUTLIERS BY SOURCE",
    str(df.groupby("source")[
        [f"{c}_potential_outlier" for c in numeric]
    ].sum()),
    "",
    "NOTES",
    "Energy is interval energy, not a cumulative counter.",
    "Energy verification uses adjacent chronological readings.",
    "The first reading and invalid or long intervals are assigned zero expected energy.",
    "Outlier flags are not confirmed faults.",
    "No fault labels have been invented.",
    "Lux is not calibrated irradiance in W/m2.",
    "Rolling features use previous readings only."
]

REPORT.write_text("\n".join(lines), encoding="utf-8")

print("\n===== SOLARSENSE ML PREPARATION =====")
print("Rows:", len(df))
print("Sources:", df["source"].value_counts().to_dict())
print("Power error:", round(df["power_error_w"].abs().mean(), 9), "W")
print("Comparable energy intervals:", int(valid_interval.sum()))
print("Energy matches:", int(df.loc[valid_interval, "interval_energy_match"].sum()))
print("Energy mismatches:", int((~df.loc[valid_interval, "interval_energy_match"]).sum()))
print("Duplicate IDs:", df["reading_id"].duplicated().sum())
print("Missing values:", int(df.isna().sum().sum()))
print("\nFEATURE DATASET:", OUTPUT.resolve())
print("QUALITY REPORT:", REPORT.resolve())
print("====================================")
