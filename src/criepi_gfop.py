"""CRIEPI GFOP の入力データから地図をまとめて生成するコマンド。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .bubble_size import compute_bubble_sizes
from .config import load_config
from .data_loader import load_points
from .flow_loader import load_flows
from .flow_plot import prepare_flow_geometry
from .flow_size import compute_flow_widths
from .interactive_map import save_interactive_map
from .static_map import save_static_map


ENCODING = "cp932"
DEFAULT_DATA_DIRECTORY = Path("data/criepi_GFOP_Inputdata")
DEFAULT_NODELIST_PATH = Path("../modules/node_dispatch/nodelist.csv")


def _normalise_node_id(value: object) -> str | None:
    """CSV が数値として読まれたノード ID を文字列へ正規化する。"""

    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        return text
    return str(int(numeric)) if numeric.is_integer() else text


def _config(config_path: Path, title: str) -> dict[str, Any]:
    """既定設定を読み、GFOP の入力向けに調整する。"""

    config = deepcopy(load_config(config_path))
    config["input"]["encoding"] = ENCODING
    config["bubble"]["zero_value"] = "hide"
    config["static_map"]["title"] = title
    return config


def _save_map(
    points: pd.DataFrame,
    output_directory: Path,
    config: dict[str, Any],
    base_directory: Path,
    flows: pd.DataFrame | None = None,
) -> list[Path]:
    """HTML と静的な PNG/PDF/SVG を保存する。"""

    output_directory.mkdir(parents=True, exist_ok=True)
    created = [
        save_interactive_map(
            points, config, output_directory / str(config["output"]["html_filename"]), flows
        )
    ]
    created.extend(save_static_map(points, config, output_directory, base_directory, flows).values())
    return created


def _build_node_edge_points(
    node_csv: Path, branch_csv: Path, nodelist_csv: Path, output_directory: Path
) -> tuple[Path, Path]:
    """フロー端点を含む地点 CSV と、空行を除いたフロー CSV を作成する。"""

    nodes = pd.read_csv(node_csv, encoding=ENCODING, dtype={"name": str})
    branches = pd.read_csv(branch_csv, encoding=ENCODING)
    branches["from_name"] = branches["from_name"].map(_normalise_node_id)
    branches["to_name"] = branches["to_name"].map(_normalise_node_id)
    branches = branches.dropna(subset=["from_name", "to_name"]).copy()

    known_ids = set(nodes["name"].map(_normalise_node_id).dropna())
    endpoint_ids = set(branches["from_name"]) | set(branches["to_name"])
    missing_ids = endpoint_ids - known_ids
    locations = pd.read_csv(nodelist_csv, encoding=ENCODING, dtype={"ID": str})
    locations["ID"] = locations["ID"].map(_normalise_node_id)
    missing_locations = locations.loc[locations["ID"].isin(missing_ids), ["ID", "lat", "lon"]]
    absent_ids = missing_ids - set(missing_locations["ID"])
    if absent_ids:
        raise ValueError(f"No coordinates found for branch endpoint IDs: {sorted(absent_ids)}")

    supplements = pd.DataFrame(
        {
            "name": missing_locations["ID"],
            "latitude": missing_locations["lat"],
            "longitude": missing_locations["lon"],
            "dataset": "送電線端点（値なし）",
            "value": 0.0,
            "unit": "MW",
            "description": "送電線を描画するため nodelist.csv から補完したノード",
        }
    )
    derived_nodes = pd.concat([nodes, supplements], ignore_index=True)
    output_directory.mkdir(parents=True, exist_ok=True)
    points_path = output_directory / "node_edge_points.csv"
    flows_path = output_directory / "branch_data_normalized.csv"
    derived_nodes.to_csv(points_path, index=False, encoding="utf-8-sig")
    branches.to_csv(flows_path, index=False, encoding="utf-8-sig")
    return points_path, flows_path


def generate(data_directory: Path, nodelist_path: Path, output_directory: Path) -> list[Path]:
    """4 種類の GFOP 地図を生成して、そのパスを返す。"""

    project_directory = Path(__file__).resolve().parents[1]
    config_path = project_directory / "config.yaml"
    created: list[Path] = []

    node_edge_directory = output_directory / "node_edge"
    points_path, flows_path = _build_node_edge_points(
        data_directory / "ele_eachnode.csv",
        data_directory / "branch_data.csv",
        nodelist_path,
        node_edge_directory,
    )
    node_edge_config = _config(config_path, "GFOP ノード・エッジ図（各ノードの電力）")
    points = compute_bubble_sizes(load_points(points_path), node_edge_config["bubble"])
    flows = load_flows(flows_path, points)
    flows = prepare_flow_geometry(
        compute_flow_widths(flows, node_edge_config["flow"]),
        float(node_edge_config["flow"]["curvature"]),
    )
    created.extend(_save_map(points, node_edge_directory, node_edge_config, project_directory, flows))

    for filename, title, directory_name in (
        ("RE_eachnode.csv", "GFOP ノード別再生可能エネルギー", "re_eachnode"),
        ("ele_eachplant.csv", "GFOP 発電所別電力", "ele_eachplant"),
        ("ele_eachnode.csv", "GFOP ノード別電力", "ele_eachnode"),
    ):
        config = _config(config_path, title)
        points = compute_bubble_sizes(
            load_points(data_directory / filename, encoding=ENCODING), config["bubble"]
        )
        created.extend(
            _save_map(points, output_directory / directory_name, config, project_directory)
        )
    return created


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate maps for CRIEPI GFOP input data.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_DIRECTORY)
    parser.add_argument("--nodelist", type=Path, default=DEFAULT_NODELIST_PATH)
    parser.add_argument("--output", type=Path, default=Path("output/criepi_GFOP"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for output_path in generate(args.data.resolve(), args.nodelist.resolve(), args.output.resolve()):
        print(f"Created: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
