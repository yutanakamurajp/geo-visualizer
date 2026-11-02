"""フロー線幅をバブルと同じ正規化規則で計算する。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from .bubble_size import BubbleSizeError, calculate_radii


class FlowSizeError(BubbleSizeError):
    """フロー線幅の設定または入力値が不正な場合の例外。"""


def compute_flow_widths(flows: pd.DataFrame, flow_config: Mapping[str, Any]) -> pd.DataFrame:
    """フローの絶対値から ``flow_width`` を追加して返す。

    バブルの ``sqrt`` / ``linear`` / ``log`` スケーリング実装をそのまま再利用する。
    したがって負値は描画方向だけを反転し、線幅は常に ``abs(value)`` で決まる。
    """

    required = {"value", "dataset"}
    missing = required.difference(flows.columns)
    if missing:
        raise FlowSizeError(f"Flow data is missing required column(s): {sorted(missing)}")

    minimum_width = float(flow_config["minimum_width"])
    maximum_width = float(flow_config["maximum_width"])
    scaling = str(flow_config.get("scaling", "sqrt"))
    zero_value = str(flow_config.get("zero_value", "hide"))
    normalize = flow_config.get("normalize", {})
    if not isinstance(normalize, Mapping):
        raise FlowSizeError("flow.normalize must be a mapping.")
    mode = str(normalize.get("mode", "global"))
    if mode not in {"global", "per_dataset"}:
        raise FlowSizeError("Normalization mode must be global or per_dataset.")

    result = flows.copy()
    magnitudes = result["value"].abs()
    source_rows = result["source_row"] if "source_row" in result.columns else None
    try:
        if mode == "global":
            result["flow_width"] = calculate_radii(
                magnitudes,
                minimum_width,
                maximum_width,
                scaling,  # type: ignore[arg-type]
                zero_value,  # type: ignore[arg-type]
                source_rows,
                normalize.get("maximum"),
            )
        else:
            widths = pd.Series(index=result.index, dtype=float)
            for _, group in result.groupby("dataset", sort=False):
                group_source_rows = (
                    group["source_row"] if "source_row" in group.columns else None
                )
                widths.loc[group.index] = calculate_radii(
                    group["value"].abs(),
                    minimum_width,
                    maximum_width,
                    scaling,  # type: ignore[arg-type]
                    zero_value,  # type: ignore[arg-type]
                    group_source_rows,
                )
            result["flow_width"] = widths
    except BubbleSizeError as exc:
        raise FlowSizeError(str(exc)) from exc
    result["flow_magnitude"] = magnitudes.astype(float)
    return result
