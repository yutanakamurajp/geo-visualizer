"""バブル半径を一貫して計算するための共通ロジック。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import numpy as np
import pandas as pd


ScalingMode = Literal["sqrt", "linear", "log"]
NormalizeMode = Literal["global", "per_dataset"]
ZeroValueMode = Literal["minimum", "hide"]


class BubbleSizeError(ValueError):
    """バブルサイズの計算に必要な値または設定が不正な場合の例外。"""


def _validate_settings(
    minimum_radius: float, maximum_radius: float, scaling: str, zero_value: str
) -> None:
    """半径計算の設定値を検証する。"""

    if minimum_radius < 0 or maximum_radius <= 0 or minimum_radius > maximum_radius:
        raise BubbleSizeError(
            "Radii must satisfy 0 <= minimum_radius <= maximum_radius."
        )
    if scaling not in {"sqrt", "linear", "log"}:
        raise BubbleSizeError("Scaling must be sqrt, linear, or log.")
    if zero_value not in {"minimum", "hide"}:
        raise BubbleSizeError("zero_value must be minimum or hide.")


def _check_negative_values(values: pd.Series, source_rows: pd.Series | None) -> None:
    """負値を検出し、元CSVの行番号を含むエラーを送出する。"""

    negative_indices = values.index[values < 0]
    if len(negative_indices) == 0:
        return
    index = negative_indices[0]
    row = int(source_rows.loc[index]) if source_rows is not None else int(index) + 1
    value = values.loc[index]
    raise BubbleSizeError(
        f"Negative value at CSV row {row}, column 'value', value {value}: "
        "negative values are not supported."
    )


def calculate_radii(
    values: pd.Series,
    minimum_radius: float,
    maximum_radius: float,
    scaling: ScalingMode = "sqrt",
    zero_value: ZeroValueMode = "minimum",
    source_rows: pd.Series | None = None,
) -> pd.Series:
    """値列を半径に変換する。

    最大値を1に正規化する。sqrt は面積が値に比例して見える既定の方式で、
    log は log1p を使うためゼロも安全に扱える。値がすべてゼロの場合は
    最小半径（または zero_value=hide のとき0）を返す。
    """

    _validate_settings(minimum_radius, maximum_radius, scaling, zero_value)
    numeric_values = pd.to_numeric(values, errors="raise").astype(float)
    if not np.isfinite(numeric_values.to_numpy()).all():
        raise BubbleSizeError("All values supplied for bubble sizing must be finite.")
    _check_negative_values(numeric_values, source_rows)

    maximum_value = float(numeric_values.max()) if not numeric_values.empty else 0.0
    if maximum_value == 0:
        radii = pd.Series(minimum_radius, index=values.index, dtype=float)
    else:
        normalized = numeric_values / maximum_value
        if scaling == "sqrt":
            scaled = np.sqrt(normalized)
        elif scaling == "linear":
            scaled = normalized
        else:
            scaled = np.log1p(numeric_values) / np.log1p(maximum_value)
        radii = minimum_radius + (maximum_radius - minimum_radius) * scaled
        radii = pd.Series(radii, index=values.index, dtype=float)

    if zero_value == "hide":
        radii.loc[numeric_values == 0] = 0.0
    return radii


def compute_bubble_sizes(points: pd.DataFrame, bubble_config: Mapping[str, object]) -> pd.DataFrame:
    """DataFrameへ bubble_radius 列を加える。

    global は全系列共通の最大値、per_dataset は系列ごとの最大値で
    正規化する。絶対値を系列間で比較する用途では global を使う。
    """

    required = {"value", "dataset"}
    missing = required.difference(points.columns)
    if missing:
        raise BubbleSizeError(f"Points data is missing required column(s): {sorted(missing)}")

    minimum_radius = float(bubble_config["minimum_radius"])
    maximum_radius = float(bubble_config["maximum_radius"])
    scaling = str(bubble_config.get("scaling", "sqrt"))
    zero_value = str(bubble_config.get("zero_value", "minimum"))
    normalize = bubble_config.get("normalize", {})
    if not isinstance(normalize, Mapping):
        raise BubbleSizeError("bubble.normalize must be a mapping.")
    mode = str(normalize.get("mode", "global"))
    if mode not in {"global", "per_dataset"}:
        raise BubbleSizeError("Normalization mode must be global or per_dataset.")

    result = points.copy()
    source_rows = result["source_row"] if "source_row" in result.columns else None
    if mode == "global":
        result["bubble_radius"] = calculate_radii(
            result["value"],
            minimum_radius,
            maximum_radius,
            scaling,  # type: ignore[arg-type]
            zero_value,  # type: ignore[arg-type]
            source_rows,
        )
        return result

    radii = pd.Series(index=result.index, dtype=float)
    for _, group in result.groupby("dataset", sort=False):
        group_source_rows = group["source_row"] if "source_row" in group.columns else None
        radii.loc[group.index] = calculate_radii(
            group["value"],
            minimum_radius,
            maximum_radius,
            scaling,  # type: ignore[arg-type]
            zero_value,  # type: ignore[arg-type]
            group_source_rows,
        )
    result["bubble_radius"] = radii
    return result
