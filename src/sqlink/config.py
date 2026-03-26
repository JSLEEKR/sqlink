"""Configuration management for sqlink."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_FILENAME = ".sqlink.json"


@dataclass
class Config:
    """sqlink configuration."""

    disabled_rules: list[str] = field(default_factory=list)
    max_joins: int = 5
    large_row_threshold: int = 10000
    high_cost_threshold: float = 1000.0
    row_estimate_mismatch_ratio: float = 10.0
    output_format: str = "text"
    color: bool = True
    severity_threshold: str = "info"  # info, warning, error, critical

    def to_dict(self) -> dict[str, object]:
        return {
            "disabled_rules": self.disabled_rules,
            "max_joins": self.max_joins,
            "large_row_threshold": self.large_row_threshold,
            "high_cost_threshold": self.high_cost_threshold,
            "row_estimate_mismatch_ratio": self.row_estimate_mismatch_ratio,
            "output_format": self.output_format,
            "color": self.color,
            "severity_threshold": self.severity_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        return cls(
            disabled_rules=data.get("disabled_rules", []),
            max_joins=data.get("max_joins", 5),
            large_row_threshold=data.get("large_row_threshold", 10000),
            high_cost_threshold=data.get("high_cost_threshold", 1000.0),
            row_estimate_mismatch_ratio=data.get("row_estimate_mismatch_ratio", 10.0),
            output_format=data.get("output_format", "text"),
            color=data.get("color", True),
            severity_threshold=data.get("severity_threshold", "info"),
        )

    def save(self, path: str | Path | None = None) -> None:
        """Save config to file."""
        if path is None:
            path = Path.cwd() / CONFIG_FILENAME
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        """Load config from file."""
        if path is None:
            path = Path.cwd() / CONFIG_FILENAME
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text())
        return cls.from_dict(data)

    def merge(self, other: Config) -> Config:
        """Merge another config into this one (other takes precedence)."""
        merged = Config.from_dict(self.to_dict())
        other_dict = other.to_dict()
        for key, value in other_dict.items():
            if key == "disabled_rules":
                merged.disabled_rules = list(set(merged.disabled_rules + value))
            else:
                setattr(merged, key, value)
        return merged


def find_config(start_dir: str | Path | None = None) -> Config:
    """Find and load config, searching up from start_dir."""
    if start_dir is None:
        start_dir = Path.cwd()

    current = Path(start_dir).resolve()
    while True:
        config_path = current / CONFIG_FILENAME
        if config_path.exists():
            return Config.load(config_path)
        parent = current.parent
        if parent == current:
            break
        current = parent

    return Config()  # defaults
