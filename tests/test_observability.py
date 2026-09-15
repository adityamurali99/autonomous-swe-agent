from pathlib import Path
from typing import Any

from swe_agent.observability import LangfuseTracer, NullTracer, create_tracer, load_local_env


class FakeLangfuseClient:
    def __init__(self, **credentials: Any) -> None:
        self.credentials = credentials
        self.flushed = False

    def flush(self) -> None:
        self.flushed = True


def test_load_local_env_ignores_comments_and_unquotes_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# local secrets\nPLAIN=value\nQUOTED='other value'\n\n")

    assert load_local_env(env_file) == {"PLAIN": "value", "QUOTED": "other value"}


def test_create_tracer_is_disabled_without_credentials(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=secret\n")

    assert isinstance(create_tracer(env_file), NullTracer)


def test_create_tracer_configures_langfuse_from_local_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LANGFUSE_PUBLIC_KEY=pk-test\n"
        "LANGFUSE_SECRET_KEY=sk-test\n"
        "LANGFUSE_BASE_URL=https://us.cloud.langfuse.com\n"
    )
    clients: list[FakeLangfuseClient] = []

    def factory(**credentials: Any) -> FakeLangfuseClient:
        client = FakeLangfuseClient(**credentials)
        clients.append(client)
        return client

    tracer = create_tracer(env_file, client_factory=factory)

    assert isinstance(tracer, LangfuseTracer)
    assert clients[0].credentials == {
        "public_key": "pk-test",
        "secret_key": "sk-test",
        "base_url": "https://us.cloud.langfuse.com",
    }
    tracer.flush()
    assert clients[0].flushed
