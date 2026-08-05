from __future__ import annotations

from pathlib import Path

import pytest

from src.config import ConfigurationError, load_config


def test_invalid_flow_configuration_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("flow:\n  zero_value: invalid\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="flow.zero_value"):
        load_config(path)


def test_non_finite_flow_width_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("flow:\n  maximum_width: .nan\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="flow width settings must be numeric"):
        load_config(path)
