"""CSV地点データの読み込み、検証、重複処理。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
import warnings

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ("name", "latitude", "longitude", "dataset", "value")
OPTIONAL_COLUMNS = ("unit", "description")
DuplicateMode = Literal["error", "first", "sum"]


class DataValidationError(ValueError):
    """CSVデータが入力仕様を満たさない場合に送出する例外。"""


class DuplicatePointWarning(UserWarning):
    """完全に重複した地点データを検出した場合の警告。"""


def _csv_row_number(index: int) -> int:
    """DataFrameのゼロ始まりの行番号をCSV上の行番号に変換する。"""

    return index + 2


def _format_value(value: object) -> str:
    """エラー内で空値も識別しやすい文字列に整形する。"""

    if isinstance(value, np.generic):
        value = value.item()
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "<missing>"
    return repr(value)


def _raise_row_error(index: int, column: str, value: object, reason: str) -> None:
    """行・列・値を含む一貫した検証エラーを送出する。"""

    raise DataValidationError(
        f"CSV row {_csv_row_number(index)}, column '{column}', value "
        f"{_format_value(value)}: {reason}"
    )


def _validate_text_columns(
    frame: pd.DataFrame, columns: tuple[str, ...] = ("name", "dataset")
) -> None:
    """指定した必須文字列列が欠損または空文字でないことを確認する。"""

    for column in columns:
        for index, value in frame[column].items():
            if pd.isna(value) or not str(value).strip():
                _raise_row_error(index, column, value, "must not be empty")
        frame[column] = frame[column].astype(str).str.strip()


def _validate_numeric_column(
    frame: pd.DataFrame, column: str, minimum: float | None, maximum: float | None
) -> None:
    """数値列の変換可能性、有限性、指定範囲を検証する。"""

    raw_values = frame[column].copy()
    converted = pd.to_numeric(raw_values, errors="coerce")
    for index, converted_value in converted.items():
        raw_value = raw_values.at[index]
        if pd.isna(converted_value):
            if str(raw_value).strip().lower() in {"nan", "+nan", "-nan"}:
                _raise_row_error(index, column, raw_value, "must be finite")
            _raise_row_error(index, column, raw_value, "must be a numeric value")
        if not np.isfinite(float(converted_value)):
            _raise_row_error(index, column, raw_value, "must be finite")
        if minimum is not None and float(converted_value) < minimum:
            _raise_row_error(index, column, raw_value, f"must be at least {minimum}")
        if maximum is not None and float(converted_value) > maximum:
            _raise_row_error(index, column, raw_value, f"must be at most {maximum}")
    frame[column] = converted.astype(float)


def _handle_duplicates(
    frame: pd.DataFrame,
    mode: DuplicateMode,
    warning_category: type[Warning] = DuplicatePointWarning,
) -> pd.DataFrame:
    """完全重複行を検出し、設定された方針に従って処理する。"""

    comparison_columns = [column for column in frame.columns if column != "source_row"]
    duplicate_mask = frame.duplicated(subset=comparison_columns, keep=False)
    if not duplicate_mask.any():
        return frame

    duplicate_rows = [_csv_row_number(int(index)) for index in frame.index[duplicate_mask]]
    first_duplicate_index = frame.index[duplicate_mask][0]
    example_column = comparison_columns[0]
    example_value = frame.at[first_duplicate_index, example_column]
    message = (
        f"Duplicate complete rows detected at CSV rows: {duplicate_rows}; "
        f"column '{example_column}', value {_format_value(example_value)}."
    )
    warnings.warn(message, warning_category, stacklevel=2)
    if mode == "error":
        raise DataValidationError(f"{message} Set data_validation.duplicates to first or sum.")
    if mode == "first":
        return frame.drop_duplicates(subset=comparison_columns, keep="first").copy()

    grouping_columns = [column for column in comparison_columns if column != "value"]
    aggregated = (
        frame.groupby(grouping_columns, sort=False, dropna=False, as_index=False)
        .agg(value=("value", "sum"), source_row=("source_row", "first"))
    )
    return aggregated[frame.columns]


def load_points(
    csv_path: Path,
    encoding: str = "utf-8-sig",
    duplicate_mode: DuplicateMode = "error",
) -> pd.DataFrame:
    """地点CSVを読み込み、検証済みのDataFrameを返す。

    任意列の unit と description はCSVに存在しない場合、空文字列の列として
    補完する。全ての行に source_row（CSVの実行上の行番号）も保持する。
    """

    if duplicate_mode not in {"error", "first", "sum"}:
        raise ValueError("duplicate_mode must be one of: error, first, sum")
    if not csv_path.is_file():
        raise FileNotFoundError(f"Input CSV does not exist: {csv_path}")

    try:
        frame = pd.read_csv(csv_path, encoding=encoding, keep_default_na=False)
    except UnicodeDecodeError as exc:
        raise DataValidationError(
            f"Could not decode CSV {csv_path} using encoding {encoding}: {exc}"
        ) from exc
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError(f"Input CSV is empty: {csv_path}") from exc

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise DataValidationError(
            f"Missing required column(s): {', '.join(missing_columns)}. "
            f"Required columns are: {', '.join(REQUIRED_COLUMNS)}."
        )
    if frame.empty:
        raise DataValidationError("Input CSV contains no data rows.")

    frame = frame.copy()
    for column in OPTIONAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
        else:
            frame[column] = frame[column].fillna("").astype(str)

    _validate_text_columns(frame)
    _validate_numeric_column(frame, "latitude", -90, 90)
    _validate_numeric_column(frame, "longitude", -180, 180)
    _validate_numeric_column(frame, "value", None, None)
    frame["source_row"] = [index + 2 for index in range(len(frame))]
    return _handle_duplicates(frame, duplicate_mode).reset_index(drop=True)
