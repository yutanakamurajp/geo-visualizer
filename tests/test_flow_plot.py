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


def test_flows_above_bubbles_option(tmp_path) -> None:
    """flow.above_bubbles=true で、静止画の矢印をバブルより上(zorder 4)に描く。"""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    from matplotlib.patches import FancyArrowPatch

    from src.config import DEFAULT_CONFIG
    from src.static_map import _draw_flows

    flows = pd.DataFrame({"dataset": ["f"], "value": [1.0], "flow_width": [2.0], "curve_offset": [0.0],
                          "draw_from_latitude": [35.0], "draw_from_longitude": [136.0], "draw_to_latitude": [35.5], "draw_to_longitude": [136.5]})
    for flag, z in ((False, 2), (True, 4)):
        cfg = {**DEFAULT_CONFIG, "flow": {**DEFAULT_CONFIG["flow"], "above_bubbles": flag}, "datasets": {}}
        fig, ax = plt.subplots()
        _draw_flows(ax, flows, cfg)
        assert [p.get_zorder() for p in ax.patches if isinstance(p, FancyArrowPatch)] == [z]
        plt.close(fig)


def test_tile_url_with_attribution() -> None:
    """map.attribution を書けば、URL のタイル(地理院タイルなど)で地図を作れる。"""

    import json

    import pandas as pd

    from src.config import DEFAULT_CONFIG
    from src.interactive_map import build_interactive_map

    url = "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png"
    cfg = {**DEFAULT_CONFIG, "map": {**DEFAULT_CONFIG["map"], "tiles": url, "attribution": "地理院タイル"}, "datasets": {}}
    pts = pd.DataFrame({"name": ["a"], "latitude": [35.0], "longitude": [137.0], "dataset": ["d"], "value": [1.0],
                        "unit": ["MW"], "description": [""], "bubble_radius": [5.0]})
    html = build_interactive_map(pts, cfg).get_root().render()
    assert "cyberjapandata.gsi.go.jp" in html
    assert "地理院タイル" in html or json.dumps("地理院タイル")[1:-1] in html  # folium は JSON で \\uXXXX にする
