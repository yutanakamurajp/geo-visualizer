"""ノード間フローCSVの読み込み、検証、座標解決。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from .data_loader import (
    DataValidationError,
    _format_value,
    _handle_duplicates,
    _raise_row_error,
    _validate_numeric_column,
    _validate_text_columns,
)


REQUIRED_FLOW_COLUMNS = ("from_name", "to_name", "dataset", "value")
OPTIONAL_FLOW_COLUMNS = ("unit", "description")
DuplicateMode = Literal["error", "first", "sum"]
FlowValidationError = DataValidationError


class DuplicateFlowWarning(UserWarning):
    """完全に重複したフロー行を検出した場合の警告。"""


def node_coordinate_lookup(points: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """地点データから、名前ごとに一意な ``(latitude, longitude)`` を作る。

    同じ名前が複数系列に登場しても座標が同一なら利用できる。座標が異なる場合は
    フローの接続先を一意に決められないため、元ノードCSVの行番号を含めて停止する。
    """

    required = {"name", "latitude", "longitude"}
    missing = required.difference(points.columns)
    if missing:
        raise DataValidationError(
            f"Node data is missing required column(s): {sorted(missing)}."
        )

    lookup: dict[str, tuple[float, float]] = {}
    for name, group in points.groupby("name", sort=False):
        coordinates = group[["latitude", "longitude"]].drop_duplicates()
        if len(coordinates) != 1:
            source_rows = (
                group["source_row"].astype(int).tolist()
                if "source_row" in group.columns
                else [int(index) + 2 for index in group.index]
            )
            coordinate_text = ", ".join(
                f"({float(row.latitude):g}, {float(row.longitude):g})"
                for row in coordinates.itertuples(index=False)
            )
            raise DataValidationError(
                f"Node CSV rows {source_rows}, column 'name', value {_format_value(name)}: "
                "coordinates are ambiguous for this name "
                f"({coordinate_text})."
            )
        coordinate = coordinates.iloc[0]
        lookup[str(name)] = (float(coordinate["latitude"]), float(coordinate["longitude"]))
    return lookup


def _validate_references(frame: pd.DataFrame, points: pd.DataFrame) -> None:
    """フローの始終点名がノードCSVに存在し、座標を取得できることを確認する。"""

    known_nodes = node_coordinate_lookup(points)
    for column in ("from_name", "to_name"):
        for index, value in frame[column].items():
            if str(value) not in known_nodes:
                _raise_row_error(
                    int(index),
                    column,
                    value,
                    "does not exist in the node CSV",
                )


def _add_direction_and_coordinates(
    frame: pd.DataFrame, points: pd.DataFrame
) -> pd.DataFrame:
    """正負の値に従う実描画方向と始終点の座標列を追加する。"""

    lookup = node_coordinate_lookup(points)
    result = frame.copy()
    negative = result["value"] < 0
    result["draw_from_name"] = result["from_name"].where(~negative, result["to_name"])
    result["draw_to_name"] = result["to_name"].where(~negative, result["from_name"])
    result["draw_from_latitude"] = result["draw_from_name"].map(
        lambda name: lookup[str(name)][0]
    )
    result["draw_from_longitude"] = result["draw_from_name"].map(
        lambda name: lookup[str(name)][1]
    )
    result["draw_to_latitude"] = result["draw_to_name"].map(
        lambda name: lookup[str(name)][0]
    )
    result["draw_to_longitude"] = result["draw_to_name"].map(
        lambda name: lookup[str(name)][1]
    )
    result["draw_direction"] = (
        result["draw_from_name"].astype(str) + " → " + result["draw_to_name"].astype(str)
    )
    return result


def load_flows(
    csv_path: Path,
    points: pd.DataFrame,
    encoding: str = "utf-8-sig",
    duplicate_mode: DuplicateMode = "error",
) -> pd.DataFrame:
    """フローCSVを検証し、方向とノード座標を解決したDataFrameを返す。

    負値はエラーではなく、値の絶対値を描画量として、始点・終点を反転した
    ``draw_*`` 列で保持する。完全重複行の処理は地点CSVと同じ設定に従う。
    """

    if duplicate_mode not in {"error", "first", "sum"}:
        raise ValueError("duplicate_mode must be one of: error, first, sum")
    if not csv_path.is_file():
        raise FileNotFoundError(f"Flow CSV does not exist: {csv_path}")

    try:
        frame = pd.read_csv(csv_path, encoding=encoding, keep_default_na=False)
    except UnicodeDecodeError as exc:
        raise DataValidationError(
            f"Could not decode flow CSV {csv_path} using encoding {encoding}: {exc}"
        ) from exc
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError(f"Flow CSV is empty: {csv_path}") from exc

    missing_columns = [column for column in REQUIRED_FLOW_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise DataValidationError(
            f"Missing required flow column(s): {', '.join(missing_columns)}. "
            f"Required columns are: {', '.join(REQUIRED_FLOW_COLUMNS)}."
        )
    if frame.empty:
        raise DataValidationError("Flow CSV contains no data rows.")

    frame = frame.copy()
    for column in OPTIONAL_FLOW_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
        else:
            frame[column] = frame[column].fillna("").astype(str)

    _validate_text_columns(frame, ("from_name", "to_name", "dataset"))
    _validate_numeric_column(frame, "value", None, None)
    _validate_references(frame, points)
    frame["source_row"] = [index + 2 for index in range(len(frame))]
    frame = _handle_duplicates(
        frame, duplicate_mode, warning_category=DuplicateFlowWarning
    ).reset_index(drop=True)
    return _add_direction_and_coordinates(frame, points)
