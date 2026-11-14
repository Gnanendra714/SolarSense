import pandas as pd
import pytest
from pathlib import Path

from train import load_dataset, split_data, VALID_LABELS


def frame(source="hardware"):
    rows = []
    for label in sorted(VALID_LABELS):
        for session in range(2):
            for sample in range(3):
                rows.append({
                    "timestamp": f"2026-11-{10 + session}T10:0{sample}:00Z",
                    "session_id": f"{label}-session-{session}",
                    "source": source,
                    "voltage_v": 8.0,
                    "current_a": 0.5,
                    "panel_temp_c": 30.0,
                    "light_lux": 12000.0,
                    "label": label,
                })
    return pd.DataFrame(rows)


def test_training_rejects_simulated_data(tmp_path):
    path = tmp_path / "readings.csv"
    frame("simulated").to_csv(path, index=False)
    with pytest.raises(ValueError, match="hardware data only"):
        load_dataset(path)


def test_training_requires_hardware_session_labels(tmp_path):
    path = tmp_path / "readings.csv"
    frame().to_csv(path, index=False)
    loaded = load_dataset(path)
    assert len(loaded) == 24
    assert set(loaded["source"]) == {"hardware"}


def test_group_split_keeps_independent_sessions_apart():
    loaded = frame()
    loaded["power_w"] = loaded["voltage_v"] * loaded["current_a"]
    X_train, X_test, y_train, y_test, method = split_data(loaded, 0.5, 42)
    assert method == "grouped_by_session"
    assert set(y_train) == VALID_LABELS
    assert set(y_test) == VALID_LABELS
    assert set(loaded.loc[X_train.index, "session_id"]).isdisjoint(
        set(loaded.loc[X_test.index, "session_id"])
    )
