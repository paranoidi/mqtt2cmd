from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class BrokerConfig(BaseModel):
    """MQTT broker configuration."""

    host: str
    port: int = 1883
    username: str | None = None
    password: str | None = None


class CommandConfig(BaseModel):
    """Command configuration for a topic."""

    topic: str
    cmd: str
    args: list[str] = Field(default_factory=list)
    stdout: str | None = None
    stderr: str | None = None


class AppConfig(BaseModel):
    """Application configuration."""

    broker: BrokerConfig
    commands: list[CommandConfig]


def load_config(config_path: Path | str) -> AppConfig:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        AppConfig instance with loaded configuration.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with path.open() as f:
        data = yaml.safe_load(f)

    return AppConfig.model_validate(data)
