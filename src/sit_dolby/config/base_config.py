from __future__ import annotations

from typing import TypeVar

import json
import tomllib
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


BaseConfigT = TypeVar("BaseConfigT", bound="BaseConfig")


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @classmethod
    def read_from_file(
        cls: type[BaseConfigT],
        config_file: str | Path,
    ) -> BaseConfigT:
        config_file = Path(config_file)
        content = config_file.read_text(encoding="utf-8")

        match file_format := config_file.suffix:
            case ".json":
                obj = json.loads(content)
            case ".yaml" | ".yml":
                obj = yaml.safe_load(content)
            case ".toml":
                obj = tomllib.loads(content)
            case _:
                msg = (
                    f"`{file_format}` is not supported. "
                    "Supported formats: .json, .yaml, .yml, .toml"
                )
                raise AssertionError(msg)

        return cls.model_validate(obj)
