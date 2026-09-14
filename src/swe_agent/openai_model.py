from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from swe_agent.models import AgentState, Finish, JsonObject, ToolCall

SYSTEM_PROMPT = """You are an autonomous software engineering agent operating on a local repository.
Use one tool at a time. Inspect before editing. Discover repository instructions and validation
commands instead of assuming a language. Treat tool errors and test failures as evidence, fix the
cause, and rerun tests after every edit. Inspect the final Git diff. Call finish only when the task
is complete, tests pass, and the diff contains only intended changes. Keep the finish summary
concise and mention validation."""


class OpenAIModel:
    def __init__(self, model: str = "gpt-5.4-mini", client: OpenAI | None = None) -> None:
        self.client = client or OpenAI()
        self.model = model

    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> ToolCall | Finish:
        finish_schema: JsonObject = {
            "type": "function",
            "name": "finish",
            "description": "Finish after successful tests and final diff inspection.",
            "parameters": {"type": "object", "properties": {"summary": {"type": "string"}},
                           "required": ["summary"], "additionalProperties": False},
        }
        response = self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=self._context(state),
            tools=[*tool_schemas, finish_schema],
            tool_choice="required",
        )
        for item in response.output:
            if getattr(item, "type", None) != "function_call":
                continue
            name = str(item.name)
            arguments: dict[str, Any] = json.loads(item.arguments)
            if name == "finish":
                return Finish(str(arguments["summary"]))
            return ToolCall(name, arguments)
        raise RuntimeError("Model response did not contain a function call")

    @staticmethod
    def _context(state: AgentState) -> str:
        history = []
        for event in state.events:
            if isinstance(event.action, ToolCall):
                action: JsonObject = {"tool": event.action.name, "arguments": event.action.arguments}
            else:
                action = {"finish": event.action.summary}
            history.append({"action": action, "observation": {
                "success": event.observation.success,
                "output": event.observation.output,
                "metadata": event.observation.metadata,
                "truncated": event.observation.truncated,
            }})
        return json.dumps({"repository": str(state.repository), "task": state.task,
                           "step": state.step, "history": history}, ensure_ascii=False)
