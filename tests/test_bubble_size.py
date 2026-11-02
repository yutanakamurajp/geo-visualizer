from __future__ import annotations

import math

import pandas as pd
import pytest

from src.bubble_size import BubbleSizeError, calculate_radii, compute_bubble_sizes


def test_minimum_and_maximum_values_map_to_bounds() -> None:
    radii = calculate_radii(pd.Series([0, 100]), 4, 28)

    assert radii.tolist() == [4.0, 28.0]


def test_sqrt_scaling_uses_square_root_normalization() -> None:
    radii = calculate_radii(pd.Series([0, 25, 100]), 4, 28, scaling="sqrt")

    assert radii.tolist() == pytest.approx([4.0, 16.0, 28.0])


def test_linear_scaling_uses_linear_normalization() -> None:
    radii = calculate_radii(pd.Series([0, 50, 100]), 4, 28, scaling="linear")

    assert radii.tolist() == pytest.approx([4.0, 16.0, 28.0])


def test_log_scaling_uses_log1p_normalization() -> None:
    radii = calculate_radii(pd.Series([0, 10, 100]), 4, 28, scaling="log")

    expected_middle = 4 + 24 * math.log1p(10) / math.log1p(100)
    assert radii.tolist() == pytest.approx([4.0, expected_middle, 28.0])


def test_equal_values_do_not_divide_by_zero() -> None:
    radii = calculate_radii(pd.Series([5, 5]), 4, 28)

    assert radii.notna().all()
    assert radii.tolist() == [28.0, 28.0]


def test_negative_value_reports_source_row_and_value() -> None:
    with pytest.raises(BubbleSizeError, match="CSV row 7.*-3"):
        calculate_radii(pd.Series([0, -3]), 4, 28, source_rows=pd.Series([2, 7]))


def test_global_and_per_dataset_normalization_differ() -> None:
    points = pd.DataFrame(
        {
            "dataset": ["A", "A", "B"],
            "value": [0, 100, 10],
            "source_row": [2, 3, 4],
        }
    )
    base = {
        "minimum_radius": 4,
        "maximum_radius": 28,
        "scaling": "linear",
        "zero_value": "minimum",
    }

    global_result = compute_bubble_sizes(points, {**base, "normalize": {"mode": "global"}})
    per_dataset_result = compute_bubble_sizes(
        points, {**base, "normalize": {"mode": "per_dataset"}}
    )

    assert global_result.loc[2, "bubble_radius"] == pytest.approx(6.4)
    assert per_dataset_result.loc[2, "bubble_radius"] == pytest.approx(28.0)


def test_zero_can_be_hidden() -> None:
    radii = calculate_radii(pd.Series([0, 100]), 4, 28, zero_value="hide")

    assert radii.tolist() == [0.0, 28.0]


def test_fixed_maximum_keeps_sizes_comparable_across_maps() -> None:
    """normalize.maximum を固定すると、別の地図でも同じ値は同じ半径になる。"""

    config = {"minimum_radius": 0, "maximum_radius": 10, "scaling": "linear", "normalize": {"mode": "global", "maximum": 100}}
    a = compute_bubble_sizes(pd.DataFrame({"dataset": ["x", "x"], "value": [50.0, 100.0]}), config)
    b = compute_bubble_sizes(pd.DataFrame({"dataset": ["x", "x"], "value": [50.0, 20.0]}), config)
    assert a.bubble_radius.tolist() == [5.0, 10.0] and b.bubble_radius.tolist() == [5.0, 2.0]
    c = compute_bubble_sizes(pd.DataFrame({"dataset": ["x"], "value": [150.0]}), config)
    assert c.bubble_radius.tolist() == [10.0]  # 超える値は最大半径
