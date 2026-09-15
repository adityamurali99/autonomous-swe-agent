from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: JsonObject


@dataclass(frozen=True)
class Finish:
    summary: str


Action = ToolCall | Finish


@dataclass(frozen=True)
class Observation:
    success: bool
    output: str
    metadata: JsonObject = field(default_factory=dict)
    truncated: bool = False


@dataclass(frozen=True)
class Event:
    action: Action
    observation: Observation


@dataclass
class AgentState:
    repository: Path
    task: str
    max_steps: int = 40
    step: int = 0
    events: list[Event] = field(default_factory=list)
    validation_succeeded: bool = False
    diff_inspected: bool = False
    status: str = "running"
    summary: str | None = None
    error: str | None = None
    final_patch: str | None = None
    final_validation: Observation | None = None


class Model(Protocol):
    def next_action(self, state: AgentState, tool_schemas: list[JsonObject]) -> Action: ...
