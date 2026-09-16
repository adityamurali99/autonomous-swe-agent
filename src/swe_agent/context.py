from __future__ import annotations

from dataclasses import dataclass

from swe_agent.models import AgentState, Event, ToolCall


@dataclass(frozen=True)
class ContextConfig:
    """Controls how much of the full trajectory is shown to the model."""

    max_characters: int = 24_000
    max_observation_characters: int = 6_000
    recent_events: int = 8


class ContextSelector:
    """Select a compact model history without altering the auditable trajectory."""

    def __init__(self, config: ContextConfig | None = None) -> None:
        self.config = config or ContextConfig()

    def select(self, state: AgentState) -> list[Event]:
        if not state.events:
            return []

        priority = self._priority_indexes(state.events)
        selected: list[tuple[int, Event]] = []
        used = 0
        for index in sorted(priority, reverse=True):
            compact = self._compact(state.events[index])
            size = self._event_size(compact)
            if selected and used + size > self.config.max_characters:
                continue
            selected.append((index, compact))
            used += size

        selected.sort(key=lambda item: item[0])
        return [event for _, event in selected]

    def _priority_indexes(self, events: list[Event]) -> set[int]:
        indexes = set(range(max(0, len(events) - self.config.recent_events), len(events)))
        latest_by_file: dict[str, int] = {}
        for index, event in enumerate(events):
            if not isinstance(event.action, ToolCall):
                continue
            name = event.action.name
            if name in {"edit_file", "inspect_diff"}:
                indexes.add(index)
            if name == "run_tests" and not event.observation.success:
                indexes.add(index)
            if name == "read_file":
                path = str(event.action.arguments.get("path", ""))
                latest_by_file[path] = index
        indexes.update(latest_by_file.values())
        return indexes

    def _compact(self, event: Event) -> Event:
        output = event.observation.output
        limit = self.config.max_observation_characters
        if len(output) <= limit:
            return event
        half = max(1, (limit - 80) // 2)
        output = output[:half] + "\n... observation elided for model context ...\n" + output[-half:]
        observation = type(event.observation)(
            event.observation.success,
            output,
            event.observation.metadata,
            True,
        )
        return Event(event.action, observation)

    @staticmethod
    def _event_size(event: Event) -> int:
        return len(event.observation.output) + len(str(event.action)) + len(str(event.observation.metadata))
