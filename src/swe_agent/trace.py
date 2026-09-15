from __future__ import annotations

import json
from pathlib import Path

from swe_agent.models import AgentState, JsonObject, ToolCall

TRACE_SCHEMA_VERSION = 3


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
        "final_patch": state.final_patch,
        "runtime_seconds": state.runtime_seconds,
        "usage": state.usage.__dict__,
        "final_validation": None if state.final_validation is None else {
            "success": state.final_validation.success,
            "output": state.final_validation.output,
            "metadata": state.final_validation.metadata,
            "truncated": state.final_validation.truncated,
        },
        "events": events,
    }


def write_trace(state: AgentState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state_to_trace(state), indent=2, ensure_ascii=False) + "\n")
