"""GeoPandasとMatplotlibによる資料向け静止バブルマップ。"""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import tempfile
from typing import Any
import warnings

import geopandas as gpd

# 読み取り専用プロファイルでもMatplotlibのフォントキャッシュで失敗しないようにする。
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "japan-bubble-map-matplotlib")
)

import matplotlib
import matplotlib.font_manager as font_manager

# 静止画生成は画面表示を必要としないため、サーバーやCIでも動くバックエンドを使う。
matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import FancyArrowPatch
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from .interactive_map import dataset_styles, ordered_datasets
from .flow_plot import prepare_flow_geometry


JAPANESE_FONT_CANDIDATES = (
    "Noto Sans CJK JP",
    "Noto Sans JP",
    "IPAexGothic",
    "Yu Gothic",
    "Meiryo",
)


def configure_japanese_font() -> FontProperties | None:
    """利用可能な日本語フォントを選び、存在しなければ警告して既定へ戻す。"""

    installed = {font.name: font.fname for font in font_manager.fontManager.ttflist}
    for candidate in JAPANESE_FONT_CANDIDATES:
        if candidate in installed:
            return FontProperties(fname=installed[candidate])
    warnings.warn(
        "No preferred Japanese font was found. Falling back to Matplotlib's default font; "
        "Japanese glyphs may not render correctly.",
        UserWarning,
        stacklevel=2,
    )
    return None


def load_japan_basemap(geojson_path: Path) -> gpd.GeoDataFrame:
    """ローカルGeoJSONを優先し、同梱Natural Earthの日本形状へフォールバックする。"""

    if geojson_path.is_file():
        basemap = gpd.read_file(geojson_path)
        if basemap.empty:
            raise RuntimeError(f"Local basemap GeoJSON is empty: {geojson_path}")
        return basemap.to_crs("EPSG:4326") if basemap.crs else basemap.set_crs("EPSG:4326")

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="The geopandas.dataset module is deprecated",
                category=FutureWarning,
            )
            natural_earth_path = gpd.datasets.get_path("naturalearth_lowres")
        world = gpd.read_file(natural_earth_path)
    except (AttributeError, OSError) as exc:
        raise RuntimeError(
            "No local Japan GeoJSON was found and GeoPandas' bundled Natural Earth "
            "dataset is unavailable. Install geopandas<1.0 or place a Japan GeoJSON at "
            f"{geojson_path}."
        ) from exc

    name_column = "name" if "name" in world.columns else None
    iso_column = "iso_a3" if "iso_a3" in world.columns else None
    mask = pd.Series(False, index=world.index)
    if name_column:
        mask |= world[name_column].astype(str).eq("Japan")
    if iso_column:
        mask |= world[iso_column].astype(str).eq("JPN")
    japan = world.loc[mask]
    if japan.empty:
        raise RuntimeError("Could not locate Japan in GeoPandas' Natural Earth dataset.")
    return japan.to_crs("EPSG:4326")


def _marker_areas(radii: pd.Series) -> np.ndarray:
    """Foliumのピクセル半径をMatplotlibのポイント平方へ換算する。"""

    return np.pi * np.square(radii.to_numpy(dtype=float) * 0.85)


def _value_labels(points: pd.DataFrame) -> list[float]:
    """サイズ凡例に使う最大値の0%、50%、100%目安を返す。"""

    maximum = float(points["value"].max())
    return [0.0, maximum / 2, maximum]


def _legend_radius(value: float, maximum: float, minimum: float, maximum_radius: float) -> float:
    """既定のsqrtスケールでサイズ凡例の半径を算出する。"""

    if maximum <= 0:
        return minimum
    return minimum + (maximum_radius - minimum) * np.sqrt(value / maximum)


def _draw_flows(
    axis: Any, flows: pd.DataFrame, config: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    """Matplotlibの矢印パッチでフローを静止画に重ね描きする。"""

    required = {
        "dataset",
        "flow_width",
        "draw_from_latitude",
        "draw_from_longitude",
        "draw_to_latitude",
        "draw_to_longitude",
    }
    missing = required.difference(flows.columns)
    if missing:
        raise ValueError(f"Flow data is missing required column(s): {sorted(missing)}")

    prepared = (
        flows
        if "curve_offset" in flows.columns
        else prepare_flow_geometry(flows, float(config["flow"]["curvature"]))
    )
    styles = dataset_styles(prepared, config)
    flow_config = config["flow"]
    arrow_config = flow_config["arrow"]
    # バブル中心まで矢印を伸ばすと終端記号が隠れるため、最大バブル半径相当を
    # points単位で空ける。静止画でも方向が読み取れるようにする。
    endpoint_padding = float(config["bubble"]["maximum_radius"]) * 0.75
    for _, row in prepared.iterrows():
        if float(row["flow_width"]) <= 0:
            continue
        style = styles[str(row["dataset"])]
        arrow = FancyArrowPatch(
            (float(row["draw_from_longitude"]), float(row["draw_from_latitude"])),
            (float(row["draw_to_longitude"]), float(row["draw_to_latitude"])),
            arrowstyle="-|>" if bool(arrow_config["enabled"]) else "-",
            connectionstyle=f"arc3,rad={float(row['curve_offset']):g}",
            linewidth=float(row["flow_width"]),
            color=str(style["color"]),
            alpha=float(flow_config["opacity"]),
            mutation_scale=float(arrow_config["size"]),
            shrinkA=endpoint_padding,
            shrinkB=endpoint_padding,
            zorder=2,
        )
        axis.add_patch(arrow)
    return styles


def save_static_map(
    points: pd.DataFrame,
    config: Mapping[str, Any],
    output_directory: Path,
    base_directory: Path,
    flows: pd.DataFrame | None = None,
) -> dict[str, Path]:
    """PNG、PDF、SVGの静止画を保存し、形式ごとの絶対パスを返す。"""

    required = {"latitude", "longitude", "dataset", "value", "bubble_radius"}
    missing = required.difference(points.columns)
    if missing:
        raise ValueError(f"Points data is missing required column(s): {sorted(missing)}")

    static_config = config["static_map"]
    figure_size = static_config["figsize"]
    geojson_value = static_config.get("geojson_path", "data/geo/japan.geojson")
    geojson_path = Path(geojson_value)
    if not geojson_path.is_absolute():
        geojson_path = base_directory / geojson_path
    basemap = load_japan_basemap(geojson_path.resolve())
    font_properties = configure_japanese_font()

    figure, axis = plt.subplots(
        figsize=(float(figure_size["width"]), float(figure_size["height"])),
        dpi=int(static_config["dpi"]),
    )
    basemap.plot(ax=axis, color="#f4f4f4", edgecolor="#777777", linewidth=0.7, zorder=1)

    flow_styles: dict[str, dict[str, Any]] | None = None
    if flows is not None and not flows.empty and bool(config["flow"]["enabled"]):
        flow_styles = _draw_flows(axis, flows, config)

    point_geometry = gpd.points_from_xy(points["longitude"], points["latitude"])
    geo_points = gpd.GeoDataFrame(points.copy(), geometry=point_geometry, crs="EPSG:4326")
    styles = dataset_styles(points, config)
    for dataset in ordered_datasets(points, config["map"]):
        group = geo_points.loc[
            (geo_points["dataset"] == dataset) & (geo_points["bubble_radius"] > 0)
        ]
        if group.empty:
            continue
        style = styles[dataset]
        group.plot(
            ax=axis,
            markersize=_marker_areas(group["bubble_radius"]),
            color=style["color"],
            alpha=style["opacity"],
            edgecolor=str(static_config["outline_color"]),
            linewidth=0.75,
            zorder=3,
        )

    longitude = static_config["longitude_range"]
    latitude = static_config["latitude_range"]
    axis.set_xlim(float(longitude["minimum"]), float(longitude["maximum"]))
    axis.set_ylim(float(latitude["minimum"]), float(latitude["maximum"]))
    axis.set_xlabel("Longitude", fontproperties=font_properties)
    axis.set_ylabel("Latitude", fontproperties=font_properties)
    axis.set_title(str(static_config["title"]), fontproperties=font_properties, pad=12)
    axis.set_aspect("equal", adjustable="box")
    if static_config["show_grid"]:  # grid(False, linestyle=...) は警告を出して線を引いてしまう
        axis.grid(True, linestyle=":", linewidth=0.5, color="#999999")

    if bool(static_config["show_legend"]):
        dataset_legend = None
        if bool(static_config["show_dataset_legend"]):
            handles = [
                Line2D(
                    [0], [0], marker="o", color="none", label=str(style["label"]),
                    markerfacecolor=str(style["color"]), markeredgecolor=str(static_config["outline_color"]),
                    alpha=float(style["opacity"]), markersize=8,
                )
                for style in styles.values()
            ]
            dataset_legend = axis.legend(
                handles=handles,
                title="Dataset",
                loc="upper left",
                prop=font_properties,
            )
            axis.add_artist(dataset_legend)
        if flow_styles:
            flow_handles = [
                Line2D(
                    [0],
                    [0],
                    color=str(style["color"]),
                    alpha=float(config["flow"]["opacity"]),
                    linewidth=3,
                    label=str(style["label"]),
                )
                for style in flow_styles.values()
            ]
            flow_legend = axis.legend(
                handles=flow_handles,
                title="Flow dataset",
                loc="upper right",
                prop=font_properties,
            )
            axis.add_artist(flow_legend)
        if bool(static_config["show_size_legend"]):
            bubble = config["bubble"]
            maximum_value = float(points["value"].max())
            labels = _value_labels(points)
            size_handles = [
                Line2D(
                    [0], [0], marker="o", color="none", label=f"{value:g}",
                    markerfacecolor="#777777",
                    markeredgecolor=str(static_config["outline_color"]),
                    alpha=0.45,
                    markersize=2
                    * _legend_radius(
                        value,
                        maximum_value,
                        float(bubble["minimum_radius"]),
                        float(bubble["maximum_radius"]),
                    )
                    * 0.42,
                )
                for value in labels
            ]
            axis.legend(
                handles=size_handles,
                title="Bubble size",
                loc="lower left",
                bbox_to_anchor=(0.03, 0.04),
                prop=font_properties,
            )

    output_directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "png": output_directory / str(config["output"]["png_filename"]),
        "pdf": output_directory / str(config["output"]["pdf_filename"]),
        "svg": output_directory / str(config["output"]["svg_filename"]),
    }
    try:
        figure.savefig(outputs["png"], dpi=int(static_config["dpi"]), bbox_inches="tight")
        figure.savefig(outputs["pdf"], format="pdf", bbox_inches="tight")
        figure.savefig(outputs["svg"], format="svg", bbox_inches="tight")
    finally:
        plt.close(figure)
    return {format_name: path.resolve() for format_name, path in outputs.items()}
