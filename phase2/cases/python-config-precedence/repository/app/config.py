import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.defaults import DEFAULTS
from app.environment import environment_values
from app.files import file_values


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    timeout: int


def load_settings(path: str | Path, environ: Mapping[str, str] | None = None) -> Settings:
    environ = os.environ if environ is None else environ
    values = {**DEFAULTS, **environment_values(environ)}
    values.update(file_values(path))
    return Settings(host=str(values["host"]), port=int(values["port"]), timeout=int(values["timeout"]))
