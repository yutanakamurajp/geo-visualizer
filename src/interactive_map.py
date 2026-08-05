"""Foliumによる操作可能な複数系列バブルマップ。"""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from pathlib import Path
from typing import Any

import folium
from branca.element import Element
from folium.plugins import PolyLineTextPath
import pandas as pd

from .flow_plot import prepare_flow_geometry


AUTO_COLORS = (
    "#2ca02c",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#17becf",
    "#bcbd22",
    "#ff7f0e",
)


def ordered_datasets(points: pd.DataFrame, map_config: Mapping[str, Any]) -> list[str]:
    """設定順を優先しながら、CSVに現れるすべての系列を並べる。"""

    present = list(dict.fromkeys(points["dataset"].astype(str)))
    configured = [str(name) for name in map_config.get("dataset_order", [])]
    return [name for name in configured if name in present] + [
        name for name in present if name not in configured
    ]


def dataset_styles(
    points: pd.DataFrame, config: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    """設定済み・未設定を問わず、各系列の表示スタイルを返す。"""

    configured = config.get("datasets", {})
    if not isinstance(configured, Mapping):
        configured = {}
    styles: dict[str, dict[str, Any]] = {}
    for color_index, dataset in enumerate(ordered_datasets(points, config["map"])):
        raw = configured.get(dataset, {})
        details = raw if isinstance(raw, Mapping) else {}
        styles[dataset] = {
            "label": str(details.get("label", dataset)),
            "color": str(details.get("color", AUTO_COLORS[color_index % len(AUTO_COLORS)])),
            "visible": bool(details.get("visible", True)),
            "opacity": float(details.get("opacity", 0.55)),
        }
    return styles


def _display_number(value: object) -> str:
    """値を凡例・ツールチップ用の簡潔な文字列へ変換する。"""

    numeric = float(value)
    return f"{numeric:g}"


def _tooltip(row: pd.Series, label: str) -> str:
    """エスケープ済みのツールチップHTMLを組み立てる。"""

    unit = f" {escape(str(row['unit']))}" if str(row["unit"]) else ""
    return (
        f"<strong>{escape(str(row['name']))}</strong><br>"
        f"{escape(label)}: {escape(_display_number(row['value']))}{unit}"
    )


def _popup(row: pd.Series, label: str) -> str:
    """地点詳細を含むエスケープ済みHTMLテーブルを組み立てる。"""

    entries = (
        ("地点名", row["name"]),
        ("データ系列名", label),
        ("値", _display_number(row["value"])),
        ("単位", row["unit"]),
        ("緯度", _display_number(row["latitude"])),
        ("経度", _display_number(row["longitude"])),
        ("説明", row["description"]),
    )
    cells = "".join(
        f"<tr><th>{escape(title)}</th><td>{escape(str(value))}</td></tr>"
        for title, value in entries
    )
    return (
        "<table style='border-collapse:collapse;'>"
        "<tbody>"
        f"{cells}"
        "</tbody></table>"
    )


def _legend_html(
    styles: Mapping[str, Mapping[str, Any]],
    points: pd.DataFrame,
    config: Mapping[str, Any],
    flow_styles: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    """系列・サイズ・単位を表示するLeaflet上の凡例HTMLを作る。"""

    bubble = config["bubble"]
    minimum = float(bubble["minimum_radius"])
    maximum = float(bubble["maximum_radius"])
    midpoint = (minimum + maximum) / 2
    maximum_value = float(points["value"].max())
    units = sorted({str(unit) for unit in points["unit"] if str(unit)})
    unit_text = ", ".join(escape(unit) for unit in units) if units else "（単位なし）"
    rows = "".join(
        "<div><span style='display:inline-block;width:12px;height:12px;"
        f"margin-right:6px;background:{escape(str(style['color']))};opacity:"
        f"{float(style['opacity']):.2f};border:1px solid #333;'></span>"
        f"{escape(str(style['label']))}</div>"
        for style in styles.values()
    )
    circles = "".join(
        "<span style='display:inline-block;border-radius:50%;background:#777;"
        "opacity:.45;border:1px solid #333;vertical-align:middle;margin:2px 6px 2px 0;"
        f"width:{radius * 2:.0f}px;height:{radius * 2:.0f}px;'></span>"
        for radius in (minimum, midpoint, maximum)
    )
    flow_rows = ""
    if flow_styles:
        flow_rows = (
            "<div style='margin-top:7px;'><strong>フロー系列</strong>"
            + "".join(
                "<div><span style='display:inline-block;width:18px;height:3px;"
                f"margin:0 6px 2px 0;background:{escape(str(style['color']))};opacity:"
                f"{float(config['flow']['opacity']):.2f};'></span>"
                f"{escape(str(style['label']))}</div>"
                for style in flow_styles.values()
            )
            + "</div>"
        )
    return f"""
    <div style='position:fixed;bottom:24px;left:24px;z-index:9999;
                background:white;padding:10px 12px;border:1px solid #777;border-radius:4px;
                font-size:13px;line-height:1.45;max-width:230px;'>
      <strong>系列</strong>{rows}
      <div style='margin-top:7px;'><strong>バブルサイズ</strong><br>{circles}
      <span>最大値 {escape(_display_number(maximum_value))}</span></div>
      <div style='margin-top:5px;'><strong>単位:</strong> {unit_text}</div>
      {flow_rows}
    </div>
    """


def _flow_tooltip(row: pd.Series, label: str) -> str:
    """フローの入力値と実描画方向を含むエスケープ済みツールチップを返す。"""

    unit = f" {escape(str(row['unit']))}" if str(row["unit"]) else ""
    return (
        f"<strong>{escape(label)}</strong><br>"
        f"始点: {escape(str(row['from_name']))}<br>"
        f"終点: {escape(str(row['to_name']))}<br>"
        f"入力値: {escape(_display_number(row['value']))}{unit}<br>"
        f"描画方向: {escape(str(row['draw_direction']))}"
    )


def _flow_popup(row: pd.Series, label: str) -> str:
    """フロー詳細を含むエスケープ済みHTMLテーブルを返す。"""

    entries = (
        ("フロー系列名", label),
        ("始点", row["from_name"]),
        ("終点", row["to_name"]),
        ("入力値", _display_number(row["value"])),
        ("描画方向", row["draw_direction"]),
        ("描画量（絶対値）", _display_number(row["flow_magnitude"])),
        ("単位", row["unit"]),
        ("説明", row["description"]),
    )
    cells = "".join(
        f"<tr><th>{escape(title)}</th><td>{escape(str(value))}</td></tr>"
        for title, value in entries
    )
    return (
        "<table style='border-collapse:collapse;'>"
        "<tbody>"
        f"{cells}"
        "</tbody></table>"
    )


def _add_flow_layers(
    result: folium.Map, flows: pd.DataFrame, config: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    """フロー系列ごとのFoliumレイヤーと終端矢印を地図に追加する。"""

    required = {
        "dataset",
        "flow_width",
        "flow_magnitude",
        "flow_locations",
        "from_name",
        "to_name",
        "value",
        "unit",
        "description",
        "draw_direction",
    }
    missing = required.difference(flows.columns)
    if missing:
        raise ValueError(f"Flow data is missing required column(s): {sorted(missing)}")

    styles = dataset_styles(flows, config)
    flow_config = config["flow"]
    arrow_config = flow_config["arrow"]
    for dataset, style in styles.items():
        layer = folium.FeatureGroup(
            name=f"フロー: {str(style['label'])}", show=bool(style["visible"])
        )
        rows = flows.loc[flows["dataset"] == dataset]
        for _, row in rows.iterrows():
            if float(row["flow_width"]) <= 0:
                continue
            line = folium.PolyLine(
                locations=row["flow_locations"],
                color=str(style["color"]),
                weight=float(row["flow_width"]),
                opacity=float(flow_config["opacity"]),
                tooltip=folium.Tooltip(_flow_tooltip(row, str(style["label"])), sticky=True),
                popup=folium.Popup(_flow_popup(row, str(style["label"])), max_width=360),
            )
            line.add_to(layer)
            if bool(arrow_config["enabled"]):
                PolyLineTextPath(
                    line,
                    "▶",
                    repeat=False,
                    offset="88%",
                    attributes={
                        "fill": str(style["color"]),
                        "font-size": f"{float(arrow_config['size']):g}px",
                        "font-weight": "bold",
                    },
                ).add_to(layer)
        layer.add_to(result)
    return styles


def build_interactive_map(
    points: pd.DataFrame, config: Mapping[str, Any], flows: pd.DataFrame | None = None
) -> folium.Map:
    """検証済み・サイズ計算済みの地点データからFolium地図を作成する。"""

    required = {"name", "latitude", "longitude", "dataset", "value", "unit", "description", "bubble_radius"}
    missing = required.difference(points.columns)
    if missing:
        raise ValueError(f"Points data is missing required column(s): {sorted(missing)}")

    map_config = config["map"]
    center = map_config["center"]
    result = folium.Map(
        location=[float(center["latitude"]), float(center["longitude"])],
        zoom_start=int(map_config["zoom_start"]),
        tiles=str(map_config["tiles"]),
        control_scale=True,
    )
    styles = dataset_styles(points, config)
    for dataset, style in styles.items():
        layer = folium.FeatureGroup(name=str(style["label"]), show=bool(style["visible"]))
        rows = points.loc[points["dataset"] == dataset]
        for _, row in rows.iterrows():
            radius = float(row["bubble_radius"])
            if radius <= 0:
                continue
            folium.CircleMarker(
                location=[float(row["latitude"]), float(row["longitude"])],
                radius=radius,
                color=str(style["color"]),
                weight=1.2,
                fill=True,
                fill_color=str(style["color"]),
                fill_opacity=float(style["opacity"]),
                tooltip=folium.Tooltip(_tooltip(row, str(style["label"])), sticky=True),
                popup=folium.Popup(_popup(row, str(style["label"])), max_width=360),
            ).add_to(layer)
        layer.add_to(result)

    flow_styles: dict[str, dict[str, Any]] | None = None
    if flows is not None and not flows.empty and bool(config["flow"]["enabled"]):
        prepared_flows = (
            flows
            if "flow_locations" in flows.columns
            else prepare_flow_geometry(flows, float(config["flow"]["curvature"]))
        )
        flow_styles = _add_flow_layers(result, prepared_flows, config)

    folium.LayerControl(collapsed=False).add_to(result)
    result.get_root().html.add_child(Element(_legend_html(styles, points, config, flow_styles)))
    return result


def save_interactive_map(
    points: pd.DataFrame,
    config: Mapping[str, Any],
    output_path: Path,
    flows: pd.DataFrame | None = None,
) -> Path:
    """Folium地図をHTMLとして保存し、絶対パスを返す。"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_interactive_map(points, config, flows).save(str(output_path))
    return output_path.resolve()
