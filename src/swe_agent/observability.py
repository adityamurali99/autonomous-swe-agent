from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any, Protocol, cast

from langfuse import Langfuse

from swe_agent.models import JsonObject


class TraceObservation(Protocol):
    def update(self, **kwargs: Any) -> Any: ...


class Tracer(Protocol):
    enabled: bool

    def agent(self, *, input: JsonObject, metadata: JsonObject) -> AbstractContextManager[Any]: ...

    def generation(
        self, *, name: str, model: str, input: JsonObject
    ) -> AbstractContextManager[Any]: ...

    def flush(self) -> None: ...


class NullTracer:
    enabled = False

    def agent(self, *, input: JsonObject, metadata: JsonObject) -> AbstractContextManager[Any]:
        return nullcontext(_NullObservation())

    def generation(
        self, *, name: str, model: str, input: JsonObject
    ) -> AbstractContextManager[Any]:
        return nullcontext(_NullObservation())

    def flush(self) -> None:
        return None


class _NullObservation:
    def update(self, **kwargs: Any) -> None:
        return None


class LangfuseTracer:
    enabled = True

    def __init__(self, client: Any) -> None:
        self._client = client

    def agent(self, *, input: JsonObject, metadata: JsonObject) -> AbstractContextManager[Any]:
        return cast(
            AbstractContextManager[Any],
            self._client.start_as_current_observation(
                name="autonomous-swe-agent",
                as_type="agent",
                input=input,
                metadata=metadata,
            ),
        )

    def generation(
        self, *, name: str, model: str, input: JsonObject
    ) -> AbstractContextManager[Any]:
        return cast(
            AbstractContextManager[Any],
            self._client.start_as_current_observation(
                name=name,
                as_type="generation",
                model=model,
                input=input,
            ),
        )

    def flush(self) -> None:
        self._client.flush()


def load_local_env(path: Path = Path(".env")) -> dict[str, str]:
    """Read simple KEY=VALUE entries without mutating the process environment."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = raw_line.partition("=")
        if separator and key.strip():
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def create_tracer(
    env_file: Path = Path(".env"), *, client_factory: Any = Langfuse
) -> Tracer:
    values = load_local_env(env_file)
    public_key = values.get("LANGFUSE_PUBLIC_KEY")
    secret_key = values.get("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return NullTracer()
    return LangfuseTracer(
        client_factory(
            public_key=public_key,
            secret_key=secret_key,
            base_url=values.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
        )
    )
