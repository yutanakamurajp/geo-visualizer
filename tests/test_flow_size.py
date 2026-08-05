from __future__ import annotations

import math

import pandas as pd
import pytest

from src.flow_size import compute_flow_widths
from src.interactive_map import AUTO_COLORS, dataset_styles


def flow_config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "minimum_width": 1.0,
        "maximum_width": 10.0,
        "scaling": "sqrt",
        "zero_value": "hide",
        "normalize": {"mode": "global"},
    }
    config.update(overrides)
    return config


def test_sqrt_linear_and_log_flow_width_scaling() -> None:
    flows = pd.DataFrame({"dataset": ["A", "A", "A"], "value": [0, 25, 100]})

    sqrt_result = compute_flow_widths(flows, flow_config(zero_value="minimum"))
    linear_result = compute_flow_widths(
        flows, flow_config(scaling="linear", zero_value="minimum")
    )
    log_result = compute_flow_widths(
        flows, flow_config(scaling="log", zero_value="minimum")
    )

    assert sqrt_result["flow_width"].tolist() == pytest.approx([1, 5.5, 10])
    assert linear_result["flow_width"].tolist() == pytest.approx([1, 3.25, 10])
    expected_log = 1 + 9 * math.log1p(25) / math.log1p(100)
    assert log_result["flow_width"].tolist() == pytest.approx([1, expected_log, 10])


def test_global_and_per_dataset_flow_normalization_differ() -> None:
    flows = pd.DataFrame({"dataset": ["A", "A", "B"], "value": [0, 100, -10]})

    global_result = compute_flow_widths(flows, flow_config(scaling="linear"))
    per_dataset_result = compute_flow_widths(
        flows, flow_config(scaling="linear", normalize={"mode": "per_dataset"})
    )

    assert global_result.loc[2, "flow_width"] == pytest.approx(1.9)
    assert per_dataset_result.loc[2, "flow_width"] == pytest.approx(10)


def test_zero_value_hide_hides_zero_flow() -> None:
    flows = pd.DataFrame({"dataset": ["A", "A"], "value": [0, 10]})

    result = compute_flow_widths(flows, flow_config(zero_value="hide"))

    assert result["flow_width"].tolist() == pytest.approx([0, 10])


def test_unconfigured_flow_dataset_uses_auto_color() -> None:
    flows = pd.DataFrame({"dataset": ["未設定フロー"], "value": [1]})
    config = {"map": {"dataset_order": []}, "datasets": {}}

    styles = dataset_styles(flows, config)

    assert styles["未設定フロー"]["color"] == AUTO_COLORS[0]
