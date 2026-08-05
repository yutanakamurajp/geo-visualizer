"""全成果物をまとめて生成するコマンドラインエントリポイント。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .bubble_size import compute_bubble_sizes
from .config import load_config, resolve_path
from .data_loader import load_points
from .interactive_map import save_interactive_map
from .static_map import save_static_map


def build_parser() -> argparse.ArgumentParser:
    """CLI引数パーサーを生成する。"""

    parser = argparse.ArgumentParser(
        description="Generate an interactive and static Japan multi-series bubble map."
    )
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="YAML config path")
    parser.add_argument("--input", type=Path, help="Override input CSV path")
    parser.add_argument("--output", type=Path, help="Override output directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--html-only", action="store_true", help="Generate only the Folium HTML")
    mode.add_argument("--static-only", action="store_true", help="Generate only PNG, PDF, and SVG")
    return parser


def generate(args: argparse.Namespace) -> list[Path]:
    """引数に従ってデータを検証し、選択された成果物を生成する。"""

    config_path = args.config.expanduser().resolve()
    config = load_config(config_path)
    base_directory = config_path.parent
    input_path = args.input.expanduser().resolve() if args.input else resolve_path(
        config["input"]["csv_path"], base_directory
    )
    output_directory = args.output.expanduser().resolve() if args.output else resolve_path(
        config["output"]["directory"], base_directory
    )
    output_directory.mkdir(parents=True, exist_ok=True)

    points = load_points(
        input_path,
        encoding=str(config["input"]["encoding"]),
        duplicate_mode=str(config["data_validation"]["duplicates"]),  # type: ignore[arg-type]
    )
    points = compute_bubble_sizes(points, config["bubble"])

    created: list[Path] = []
    if not args.static_only:
        html_path = output_directory / str(config["output"]["html_filename"])
        created.append(save_interactive_map(points, config, html_path))
    if not args.html_only:
        created.extend(save_static_map(points, config, output_directory, base_directory).values())
    return created


def main(argv: Sequence[str] | None = None) -> int:
    """CLIを実行し、生成済みファイルの絶対パスを表示する。"""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        created = generate(args)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    for output_path in created:
        print(f"Created: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
