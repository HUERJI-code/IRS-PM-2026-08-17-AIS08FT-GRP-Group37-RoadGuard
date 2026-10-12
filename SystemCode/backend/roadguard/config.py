"""Repository-relative configuration, with no import-time file access."""

from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = Path("SystemCode/config/project.example.json")
DEFAULT_DB_PATH = Path("SystemCode/backend/data/roadguard.sqlite3")
DEFAULT_DEMO_RULES_PATH = Path("SystemCode/config/demo_rules.example.json")


class ConfigurationError(ValueError):
    """An invalid local setting; messages deliberately omit paths and input."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ConfigurationError("Project configuration keys must be strings.")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ConfigurationError("Project configuration must contain finite JSON values.")


def _resolve_path(value: str | Path) -> Path:
    if not str(value).strip():
        raise ConfigurationError("Configuration paths must be non-empty.")
    path = Path(value)
    return (path if path.is_absolute() else REPOSITORY_ROOT / path).resolve()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError("Project configuration contains duplicate keys.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ConfigurationError("Project configuration must use valid JSON values.")


@dataclass(frozen=True)
class Settings:
    config_path: Path
    database_path: Path
    project: Mapping[str, Any]
    database_busy_timeout_ms: int = 5000
    demo_rules_path: Path = DEFAULT_DEMO_RULES_PATH

    def __post_init__(self) -> None:
        if not isinstance(self.project, Mapping):
            raise ConfigurationError("Project configuration must be an object.")
        name = self.project.get("project_name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError("Project configuration requires project_name.")
        if any(not isinstance(self.project.get(key), Mapping) for key in ("scenario", "planning")):
            raise ConfigurationError("Project configuration requires scenario and planning objects.")
        if type(self.database_busy_timeout_ms) is not int or self.database_busy_timeout_ms <= 0:
            raise ConfigurationError("Database busy timeout must be a positive integer.")
        object.__setattr__(self, "config_path", _resolve_path(self.config_path))
        object.__setattr__(self, "database_path", _resolve_path(self.database_path))
        object.__setattr__(self, "demo_rules_path", _resolve_path(self.demo_rules_path))
        object.__setattr__(self, "project", _freeze(self.project))


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Relative overrides resolve against the repository, never the process cwd."""
    environment = os.environ if environ is None else environ
    config_path = _resolve_path(environment.get("ROADGUARD_CONFIG_PATH", DEFAULT_CONFIG_PATH))
    database_path = _resolve_path(environment.get("ROADGUARD_DB_PATH", DEFAULT_DB_PATH))
    demo_rules_path = _resolve_path(environment.get("ROADGUARD_DEMO_RULES_PATH", DEFAULT_DEMO_RULES_PATH))
    try:
        project = json.loads(
            config_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError("Project configuration could not be read as UTF-8 JSON.") from exc
    return Settings(
        config_path=config_path, database_path=database_path, project=project,
        demo_rules_path=demo_rules_path,
    )
