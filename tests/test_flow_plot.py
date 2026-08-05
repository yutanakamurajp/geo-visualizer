from __future__ import annotations

import pandas as pd
import pytest

from src.flow_plot import prepare_flow_geometry


def test_multiple_flows_between_same_nodes_get_separate_curves() -> None:
    flows = pd.DataFrame(
        {
            "from_name": ["A", "A"],
            "to_name": ["B", "B"],
            "draw_from_name": ["A", "A"],
            "draw_to_name": ["B", "B"],
            "draw_from_latitude": [35.0, 35.0],
            "draw_from_longitude": [139.0, 139.0],
            "draw_to_latitude": [36.0, 140.0],
            "draw_to_longitude": [140.0, 140.0],
        }
    )

    result = prepare_flow_geometry(flows, curvature=0.12)

    assert result["curve_offset"].tolist() == pytest.approx([-0.06, 0.06])
    assert result.loc[0, "flow_locations"] != result.loc[1, "flow_locations"]
