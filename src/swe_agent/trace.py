from __future__ import annotations

import json
from pathlib import Path

from swe_agent.models import AgentState, JsonObject, ToolCall

TRACE_SCHEMA_VERSION = 1


def state_to_trace(state: AgentState) -> JsonObject:
    events: list[JsonObject] = []
    for index, event in enumerate(state.events, start=1):
        if isinstance(event.action, ToolCall):
            action: JsonObject = {
                "type": "tool_call",
                "name": event.action.name,
                "arguments": event.action.arguments,
            }
        else:
            action = {"type": "finish", "summary": event.action.summary}
        events.append(
            {
                "step": index,
                "action": action,
                "observation": {
                    "success": event.observation.success,
                    "output": event.observation.output,
                    "metadata": event.observation.metadata,
                    "truncated": event.observation.truncated,
                },
            }
        )
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "repository": str(state.repository),
        "task": state.task,
        "status": state.status,
        "steps": state.step,
        "validation_succeeded": state.validation_succeeded,
        "diff_inspected": state.diff_inspected,
        "summary": state.summary,
        "error": state.error,
        "events": events,
    }


def write_trace(state: AgentState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state_to_trace(state), indent=2, ensure_ascii=False) + "\n")
