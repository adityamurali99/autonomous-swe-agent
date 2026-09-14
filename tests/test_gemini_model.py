from pathlib import Path
from types import SimpleNamespace
from typing import Any

from swe_agent.gemini_model import GeminiModel, load_local_api_key
from swe_agent.models import AgentState, ToolCall


class FakeInteractions:
    def __init__(self, failures: int = 0) -> None:
        self.request: dict[str, Any] = {}
        self.failures = failures

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        if self.failures:
            self.failures -= 1
            error = RuntimeError("Please retry in 0.01s")
            error.status_code = 429  # type: ignore[attr-defined]
            raise error
        step = SimpleNamespace(type="function_call", name="read_file", arguments={"path": "README.md"})
        return SimpleNamespace(steps=[step])


def test_gemini_adapter_translates_function_call_and_schema(tmp_path: Path):
    interactions = FakeInteractions()
    client = SimpleNamespace(interactions=interactions)
    model = GeminiModel(client=client)
    state = AgentState(tmp_path, "Inspect the readme")
    schema = {
        "type": "function",
        "name": "read_file",
        "description": "Read a file",
        "parameters": {"type": "object"},
        "strict": False,
    }

    action = model.next_action(state, [schema])

    assert action == ToolCall("read_file", {"path": "README.md"})
    assert all("strict" not in tool for tool in interactions.request["tools"])
    assert interactions.request["model"] == "gemini-3.1-flash-lite"


def test_load_local_api_key(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("IGNORED=value\nGEMINI_API_KEY='secret-value'\n")
    assert load_local_api_key(env_file) == "secret-value"


def test_gemini_adapter_retries_rate_limit(tmp_path: Path):
    interactions = FakeInteractions(failures=1)
    client = SimpleNamespace(interactions=interactions)
    model = GeminiModel(client=client)

    action = model.next_action(AgentState(tmp_path, "Inspect the readme"), [])

    assert action == ToolCall("read_file", {"path": "README.md"})
    assert interactions.failures == 0


def test_gemini_adapter_retries_connection_error(tmp_path: Path):
    class APIConnectionError(RuntimeError):
        pass

    class RecoveringInteractions(FakeInteractions):
        def create(self, **kwargs: Any) -> SimpleNamespace:
            if self.failures:
                self.failures -= 1
                raise APIConnectionError("temporary DNS failure")
            return super().create(**kwargs)

    interactions = RecoveringInteractions(failures=1)
    model = GeminiModel(client=SimpleNamespace(interactions=interactions))

    action = model.next_action(AgentState(tmp_path, "Inspect the readme"), [])

    assert action == ToolCall("read_file", {"path": "README.md"})
