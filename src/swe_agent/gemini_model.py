from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, cast

from google import genai

from swe_agent.models import AgentState, Finish, JsonObject, ToolCall

SYSTEM_PROMPT = """You are an autonomous software engineering agent operating on a local repository.
Use one tool at a time. Inspect before editing. Discover repository instructions and validation
commands instead of assuming a language. Treat tool errors and test failures as evidence, fix the
cause, and rerun tests after every edit. Inspect the final Git diff. Call finish only when the task
is complete, tests pass, and the diff contains only intended changes. Keep the finish summary
concise and mention validation."""


def load_local_api_key(path: Path = Path(".env")) -> str | None:
    """Read GEMINI_API_KEY from a local ignored env file without mutating process state."""
    if not path.is_file():
        return None
    for raw_line in path.read_text().splitlines():
        key, separator, value = raw_line.partition("=")
        if separator and key.strip() == "GEMINI_API_KEY":
            candidate = value.strip().strip('"').strip("'")
            return candidate or None
    return None


class GeminiModel:
    def __init__(
        self,
        model: str = "gemini-3.1-flash-lite",
        *,
        api_key: str | None = None,
        client: Any | None = None,
        max_rate_limit_retries: int = 3,
    ) -> None:
        self.client = client or genai.Client(
            api_key=api_key or load_local_api_key(),
            http_options={"retry_options": {"attempts": 1}},
        )
        self.model = model
        self.max_rate_limit_retries = max_rate_limit_retries

    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> ToolCall | Finish:
        finish_schema: JsonObject = {
            "type": "function",
            "name": "finish",
            "description": "Finish after successful tests and final diff inspection.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
                "additionalProperties": False,
            },
        }
        tools = [self._gemini_schema(schema) for schema in [*tool_schemas, finish_schema]]
        interaction = self._create_interaction(
            model=self.model,
            input=self._context(state),
            tools=tools,
            generation_config={
                "tool_choice": {
                    "allowed_tools": {"mode": "any", "tools": [tool["name"] for tool in tools]}
                }
            },
        )
        for raw_step in interaction.steps or []:
            step = cast(Any, raw_step)
            if step.type != "function_call":
                continue
            name = str(step.name)
            arguments = cast(JsonObject, step.arguments)
            if name == "finish":
                return Finish(str(arguments["summary"]))
            return ToolCall(name, arguments)
        raise RuntimeError("Gemini response did not contain a function call")

    def _create_interaction(self, **request: Any) -> Any:
        for attempt in range(self.max_rate_limit_retries + 1):
            try:
                return cast(Any, self.client.interactions.create(**request))
            except Exception as exc:
                rate_limited = getattr(exc, "status_code", None) == 429
                connection_failed = type(exc).__name__ in {"APIConnectionError", "APITimeoutError"}
                if not (rate_limited or connection_failed) or attempt == self.max_rate_limit_retries:
                    raise
                match = re.search(r"retry in ([0-9.]+)s", str(exc), re.IGNORECASE) if rate_limited else None
                delay = float(match.group(1)) if match else min(2 ** attempt, 30)
                time.sleep(delay + 0.25)
        raise RuntimeError("unreachable")

    @staticmethod
    def _gemini_schema(schema: JsonObject) -> JsonObject:
        return {key: value for key, value in schema.items() if key != "strict"}

    @staticmethod
    def _context(state: AgentState) -> str:
        history = []
        for event in state.events:
            if isinstance(event.action, ToolCall):
                action: JsonObject = {"tool": event.action.name, "arguments": event.action.arguments}
            else:
                action = {"finish": event.action.summary}
            history.append(
                {
                    "action": action,
                    "observation": {
                        "success": event.observation.success,
                        "output": event.observation.output,
                        "metadata": event.observation.metadata,
                        "truncated": event.observation.truncated,
                    },
                }
            )
        return json.dumps(
            {
                "instructions": SYSTEM_PROMPT,
                "repository": str(state.repository),
                "task": state.task,
                "step": state.step,
                "history": history,
            },
            ensure_ascii=False,
        )
