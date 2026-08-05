"""HTML・静止画で共用するフローの曲線ジオメトリ。"""

from __future__ import annotations

from collections.abc import Iterable
import math

import numpy as np
import pandas as pd


FLOW_COORDINATE_COLUMNS = {
    "from_name",
    "to_name",
    "draw_from_name",
    "draw_to_name",
    "draw_from_latitude",
    "draw_from_longitude",
    "draw_to_latitude",
    "draw_to_longitude",
}


def _pair_key(row: pd.Series) -> tuple[str, str]:
    """入力上のノード対を向きによらない比較キーへ変換する。"""

    return tuple(sorted((str(row["from_name"]), str(row["to_name"]))))


def _curve_offsets(flows: pd.DataFrame, curvature: float) -> pd.Series:
    """同一ノード対の各フローに、中央基準の曲率オフセットを割り当てる。"""

    offsets = pd.Series(0.0, index=flows.index, dtype=float)
    if curvature == 0:
        return offsets
    pair_keys = flows.apply(_pair_key, axis=1)
    for _, group in flows.groupby(pair_keys, sort=False):
        count = len(group)
        if count <= 1:
            continue
        positions = np.arange(count, dtype=float) - (count - 1) / 2
        offsets.loc[group.index] = positions * curvature
    return offsets


def curved_locations(row: pd.Series, curvature: float, steps: int = 16) -> list[tuple[float, float]]:
    """フローの実描画方向に沿う、緯度・経度の二次ベジェ曲線を返す。

    ``curvature`` は接続線の長さに対する垂直オフセットの比率で、複数フローは
    ``prepare_flow_geometry`` が付与する ``curve_offset`` を使う。
    """

    del curvature  # 曲率は行ごとの curve_offset に正規化済み。
    start_latitude = float(row["draw_from_latitude"])
    start_longitude = float(row["draw_from_longitude"])
    end_latitude = float(row["draw_to_latitude"])
    end_longitude = float(row["draw_to_longitude"])
    offset = float(row.get("curve_offset", 0.0))

    delta_latitude = end_latitude - start_latitude
    delta_longitude = end_longitude - start_longitude
    midpoint_latitude = (start_latitude + end_latitude) / 2
    midpoint_longitude = (start_longitude + end_longitude) / 2
    mean_latitude_radians = math.radians(midpoint_latitude)
    longitude_scale = max(math.cos(mean_latitude_radians), 0.1)
    metric_longitude = delta_longitude * longitude_scale
    distance = math.hypot(delta_latitude, metric_longitude)

    if distance == 0:
        # 自己参照も非表示にはせず、小さなループとして描画する。
        loop_radius = 0.28 + abs(offset)
        angles = np.linspace(math.pi, math.pi * 3, steps)
        return [
            (
                start_latitude + loop_radius * math.sin(angle),
                start_longitude + loop_radius * math.cos(angle) / longitude_scale,
            )
            for angle in angles
        ]

    normal_latitude = metric_longitude / distance
    normal_metric_longitude = -delta_latitude / distance
    control_latitude = midpoint_latitude + normal_latitude * distance * offset
    control_longitude = midpoint_longitude + (
        normal_metric_longitude * distance * offset / longitude_scale
    )
    positions = np.linspace(0.0, 1.0, steps)
    return [
        (
            (1 - position) ** 2 * start_latitude
            + 2 * (1 - position) * position * control_latitude
            + position**2 * end_latitude,
            (1 - position) ** 2 * start_longitude
            + 2 * (1 - position) * position * control_longitude
            + position**2 * end_longitude,
        )
        for position in positions
    ]


def prepare_flow_geometry(flows: pd.DataFrame, curvature: float) -> pd.DataFrame:
    """曲線オフセットとFolium向けの ``flow_locations`` を追加して返す。"""

    missing = FLOW_COORDINATE_COLUMNS.difference(flows.columns)
    if missing:
        raise ValueError(f"Flow data is missing required column(s): {sorted(missing)}")
    if curvature < 0:
        raise ValueError("flow curvature must be non-negative.")

    result = flows.copy()
    result["curve_offset"] = _curve_offsets(result, curvature)
    result["flow_locations"] = [
        curved_locations(row, curvature) for _, row in result.iterrows()
    ]
    return result


def curve_location_pairs(locations: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    """静止画用に ``(latitude, longitude)`` 座標列を確実なリストへ変換する。"""

    return [(float(latitude), float(longitude)) for latitude, longitude in locations]
