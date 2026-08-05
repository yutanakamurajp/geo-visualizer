from __future__ import annotations

from pathlib import Path

import pytest

from src.data_loader import DataValidationError, load_points


HEADER = "name,latitude,longitude,dataset,value,unit,description\n"
VALID_ROW = "東京,35.6762,139.6503,データA,500,MW,正常データ\n"


def write_csv(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "points.csv"
    path.write_text(body, encoding="utf-8")
    return path


def test_loads_valid_csv_and_adds_optional_columns(tmp_path: Path) -> None:
    path = write_csv(tmp_path, HEADER + VALID_ROW)

    result = load_points(path)

    assert len(result) == 1
    assert result.loc[0, "name"] == "東京"
    assert result.loc[0, "value"] == 500.0
    assert result.loc[0, "source_row"] == 2


def test_optional_columns_may_be_absent(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "name,latitude,longitude,dataset,value\n" + "東京,35,139,A,1\n")

    result = load_points(path)

    assert result.loc[0, "unit"] == ""
    assert result.loc[0, "description"] == ""


def test_missing_required_column_raises_specific_error(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "name,latitude,longitude,dataset\n東京,35,139,A\n")

    with pytest.raises(DataValidationError, match="Missing required column.*value"):
        load_points(path)


def test_out_of_range_latitude_is_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path, HEADER + "東京,91,139,データA,1,MW,説明\n")

    with pytest.raises(DataValidationError, match="CSV row 2, column 'latitude', value 91.*90"):
        load_points(path)


def test_out_of_range_longitude_is_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path, HEADER + "東京,35,181,データA,1,MW,説明\n")

    with pytest.raises(DataValidationError, match="CSV row 2, column 'longitude', value 181.*180"):
        load_points(path)


def test_non_numeric_value_is_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path, HEADER + "東京,35,139,データA,not-a-number,MW,説明\n")

    with pytest.raises(DataValidationError, match="CSV row 2, column 'value', value 'not-a-number'.*numeric"):
        load_points(path)


def test_empty_name_is_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path, HEADER + ",35,139,データA,1,MW,説明\n")

    with pytest.raises(DataValidationError, match="CSV row 2, column 'name'.*must not be empty"):
        load_points(path)


def test_empty_dataset_is_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path, HEADER + "東京,35,139,,1,MW,説明\n")

    with pytest.raises(DataValidationError, match="CSV row 2, column 'dataset'.*must not be empty"):
        load_points(path)
