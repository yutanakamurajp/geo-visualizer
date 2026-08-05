from __future__ import annotations

from pathlib import Path

import pytest

from src.data_loader import DataValidationError, load_points
from src.flow_loader import DuplicateFlowWarning, load_flows, node_coordinate_lookup


POINT_HEADER = "name,latitude,longitude,dataset,value\n"
POINT_ROWS = "札幌,43.0618,141.3545,A,1\n東京,35.6762,139.6503,A,1\n仙台,38.2682,140.8694,A,1\n"
FLOW_HEADER = "from_name,to_name,dataset,value,unit,description\n"


def write_csv(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def valid_points(tmp_path: Path):
    return load_points(write_csv(tmp_path, "points.csv", POINT_HEADER + POINT_ROWS))


def test_loads_valid_flows_and_resolves_coordinates_and_direction(tmp_path: Path) -> None:
    points = valid_points(tmp_path)
    path = write_csv(
        tmp_path,
        "flows.csv",
        FLOW_HEADER
        + "札幌,東京,移動量,120,MW,positive\n"
        + "東京,仙台,移動量,-50,MW,negative\n",
    )

    result = load_flows(path, points)

    assert result.loc[0, "draw_from_name"] == "札幌"
    assert result.loc[0, "draw_to_name"] == "東京"
    assert result.loc[1, "draw_from_name"] == "仙台"
    assert result.loc[1, "draw_to_name"] == "東京"
    assert result.loc[1, "draw_direction"] == "仙台 → 東京"
    assert result.loc[0, "draw_from_latitude"] == pytest.approx(43.0618)


def test_missing_required_flow_column_is_reported(tmp_path: Path) -> None:
    points = valid_points(tmp_path)
    path = write_csv(tmp_path, "flows.csv", "from_name,to_name,dataset\n札幌,東京,A\n")

    with pytest.raises(DataValidationError, match="Missing required flow column.*value"):
        load_flows(path, points)


def test_unknown_node_reference_is_reported_with_flow_row(tmp_path: Path) -> None:
    points = valid_points(tmp_path)
    path = write_csv(tmp_path, "flows.csv", FLOW_HEADER + "札幌,大阪,A,1,,\n")

    with pytest.raises(
        DataValidationError,
        match="CSV row 2, column 'to_name', value '大阪'.*does not exist",
    ):
        load_flows(path, points)


def test_non_numeric_flow_value_is_reported_with_flow_row(tmp_path: Path) -> None:
    points = valid_points(tmp_path)
    path = write_csv(tmp_path, "flows.csv", FLOW_HEADER + "札幌,東京,A,not-a-number,,\n")

    with pytest.raises(
        DataValidationError,
        match="CSV row 2, column 'value', value 'not-a-number'.*numeric",
    ):
        load_flows(path, points)


def test_ambiguous_node_coordinates_are_rejected(tmp_path: Path) -> None:
    points = load_points(
        write_csv(
            tmp_path,
            "points.csv",
            POINT_HEADER + "東京,35,139,A,1\n東京,36,140,B,2\n札幌,43,141,A,1\n",
        )
    )

    with pytest.raises(DataValidationError, match="Node CSV rows .*column 'name'.*東京.*ambiguous"):
        node_coordinate_lookup(points)


def test_complete_duplicate_flows_follow_duplicate_policy(tmp_path: Path) -> None:
    points = valid_points(tmp_path)
    row = "札幌,東京,A,4,MW,same\n"
    path = write_csv(tmp_path, "flows.csv", FLOW_HEADER + row + row)

    with pytest.warns(DuplicateFlowWarning):
        with pytest.raises(DataValidationError, match="Duplicate complete rows"):
            load_flows(path, points, duplicate_mode="error")

    with pytest.warns(DuplicateFlowWarning):
        summed = load_flows(path, points, duplicate_mode="sum")
    assert len(summed) == 1
    assert summed.loc[0, "value"] == pytest.approx(8.0)
