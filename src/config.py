"""設定ファイルの読み込みと既定値の管理。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "input": {
        "csv_path": "data/points.csv",
        "flow_csv_path": "data/flows.csv",
        "encoding": "utf-8-sig",
    },
    "output": {
        "directory": "output",
        "html_filename": "japan_bubble_map.html",
        "png_filename": "japan_bubble_map.png",
        "pdf_filename": "japan_bubble_map.pdf",
        "svg_filename": "japan_bubble_map.svg",
    },
    "data_validation": {"duplicates": "error"},
    "map": {
        "center": {"latitude": 36.2, "longitude": 138.2},
        "zoom_start": 5,
        "tiles": "CartoDB positron",
        "dataset_order": [],
    },
    "bubble": {
        "minimum_radius": 4,
        "maximum_radius": 28,
        "scaling": "sqrt",
        "zero_value": "minimum",
        "normalize": {"mode": "global"},
    },
    "flow": {
        "enabled": True,
        "minimum_width": 1.0,
        "maximum_width": 10.0,
        "scaling": "sqrt",
        "zero_value": "hide",
        "normalize": {"mode": "global"},
        "arrow": {"enabled": True, "size": 12},
        "opacity": 0.75,
        "curvature": 0.12,
    },
    "static_map": {
        "figsize": {"width": 10, "height": 12},
        "dpi": 300,
        "title": "Japan Bubble Map",
        "show_legend": True,
        "show_dataset_legend": True,
        "show_size_legend": True,
        "show_grid": True,
        "outline_color": "black",
        "longitude_range": {"minimum": 122, "maximum": 154},
        "latitude_range": {"minimum": 20, "maximum": 46},
        "geojson_path": "data/geo/japan.geojson",
    },
    "datasets": {},
}


class ConfigurationError(ValueError):
    """設定ファイルの形式または値が不正な場合に送出する例外。"""


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """入れ子の辞書を再帰的にマージし、override を優先して返す。"""

    merged = deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_config(config_path: Path) -> dict[str, Any]:
    """YAML設定を既定値とマージして読み込む。

    Parameters
    ----------
    config_path:
        読み込む YAML ファイルのパス。
    """

    if not config_path.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {config_path}")

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {config_path}: {exc}") from exc

    if loaded is None:
        loaded = {}
    if not isinstance(loaded, Mapping):
        raise ConfigurationError("Configuration root must be a YAML mapping.")

    config = _deep_merge(DEFAULT_CONFIG, loaded)
    _validate_config(config)
    return config


def resolve_path(value: str | Path, base_directory: Path) -> Path:
    """設定内のパスを設定ファイルの親ディレクトリから解決する。"""

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base_directory / candidate
    return candidate.resolve()


def _validate_config(config: Mapping[str, Any]) -> None:
    """早期に検出できる設定値を検証する。"""

    duplicate_mode = config["data_validation"].get("duplicates")
    if duplicate_mode not in {"error", "first", "sum"}:
        raise ConfigurationError(
            "data_validation.duplicates must be one of: error, first, sum."
        )

    bubble = config["bubble"]
    if bubble.get("scaling") not in {"sqrt", "linear", "log"}:
        raise ConfigurationError("bubble.scaling must be sqrt, linear, or log.")
    if bubble.get("zero_value") not in {"minimum", "hide"}:
        raise ConfigurationError("bubble.zero_value must be minimum or hide.")
    if bubble["normalize"].get("mode") not in {"global", "per_dataset"}:
        raise ConfigurationError(
            "bubble.normalize.mode must be global or per_dataset."
        )

    minimum = bubble.get("minimum_radius")
    maximum = bubble.get("maximum_radius")
    if (
        isinstance(minimum, bool)
        or isinstance(maximum, bool)
        or not isinstance(minimum, (int, float))
        or not isinstance(maximum, (int, float))
        or not math.isfinite(float(minimum))
        or not math.isfinite(float(maximum))
    ):
        raise ConfigurationError("bubble radius settings must be numeric.")
    if minimum < 0 or maximum <= 0 or minimum > maximum:
        raise ConfigurationError(
            "bubble radii must satisfy 0 <= minimum_radius <= maximum_radius."
        )

    flow = config.get("flow")
    if not isinstance(flow, Mapping):
        raise ConfigurationError("flow must be a mapping.")
    if not isinstance(flow.get("enabled"), bool):
        raise ConfigurationError("flow.enabled must be a boolean.")
    if flow.get("scaling") not in {"sqrt", "linear", "log"}:
        raise ConfigurationError("flow.scaling must be sqrt, linear, or log.")
    if flow.get("zero_value") not in {"minimum", "hide"}:
        raise ConfigurationError("flow.zero_value must be minimum or hide.")
    normalize = flow.get("normalize")
    if not isinstance(normalize, Mapping) or normalize.get("mode") not in {
        "global",
        "per_dataset",
    }:
        raise ConfigurationError(
            "flow.normalize.mode must be global or per_dataset."
        )
    flow_minimum = flow.get("minimum_width")
    flow_maximum = flow.get("maximum_width")
    if (
        isinstance(flow_minimum, bool)
        or isinstance(flow_maximum, bool)
        or not isinstance(flow_minimum, (int, float))
        or not isinstance(flow_maximum, (int, float))
        or not math.isfinite(float(flow_minimum))
        or not math.isfinite(float(flow_maximum))
    ):
        raise ConfigurationError("flow width settings must be numeric.")
    if flow_minimum < 0 or flow_maximum <= 0 or flow_minimum > flow_maximum:
        raise ConfigurationError(
            "flow widths must satisfy 0 <= minimum_width <= maximum_width."
        )
    arrow = flow.get("arrow")
    if not isinstance(arrow, Mapping) or not isinstance(arrow.get("enabled"), bool):
        raise ConfigurationError("flow.arrow.enabled must be a boolean.")
    arrow_size = arrow.get("size")
    if (
        isinstance(arrow_size, bool)
        or not isinstance(arrow_size, (int, float))
        or not math.isfinite(float(arrow_size))
        or arrow_size <= 0
    ):
        raise ConfigurationError("flow.arrow.size must be a positive number.")
    opacity = flow.get("opacity")
    if isinstance(opacity, bool) or not isinstance(opacity, (int, float)) or not 0 <= opacity <= 1:
        raise ConfigurationError("flow.opacity must be a number from 0 to 1.")
    curvature = flow.get("curvature")
    if (
        isinstance(curvature, bool)
        or not isinstance(curvature, (int, float))
        or not 0 <= curvature <= 1
    ):
        raise ConfigurationError("flow.curvature must be a number from 0 to 1.")
