from __future__ import annotations

import json
import logging
from pathlib import Path

from swe_agent.models import AgentState, Event, Finish, Model, Observation, ToolCall
from swe_agent.tools import RepositoryTools

logger = logging.getLogger("swe_agent.agent")


class Agent:
    def __init__(self, model: Model, repository: Path, *, max_steps: int = 40) -> None:
        self.model = model
        self.tools = RepositoryTools(repository)
        self.max_steps = max_steps

    def run(self, task: str) -> AgentState:
        state = AgentState(self.tools.root, task, self.max_steps)
        while state.step < state.max_steps and state.status == "running":
            action = self.model.next_action(state, self.tools.schemas)
            state.step += 1
            if isinstance(action, Finish):
                missing = []
                if not state.validation_succeeded:
                    missing.append("a successful run_tests call")
                if not state.diff_inspected:
                    missing.append("inspect_diff")
                if missing:
                    observation = Observation(False, "Cannot finish yet; required: " + ", ".join(missing))
                    state.events.append(Event(action, observation))
                    self._log(state, action, observation)
                    continue
                state.status = "completed"
                state.summary = action.summary
                observation = Observation(True, "Completion accepted")
                state.events.append(Event(action, observation))
                self._log(state, action, observation)
                break

            observation = self.tools.execute(action.name, action.arguments)
            if action.name == "run_tests":
                state.validation_succeeded = observation.success
            elif action.name == "edit_file" and observation.success:
                state.validation_succeeded = False
                state.diff_inspected = False
            elif action.name == "inspect_diff" and observation.success:
                state.diff_inspected = True
            state.events.append(Event(action, observation))
            self._log(state, action, observation)

        if state.status == "running":
            state.status = "step_limit"
        return state

    @staticmethod
    def _log(state: AgentState, action: ToolCall | Finish, observation: Observation) -> None:
        logger.info(json.dumps({"event": "agent_step", "step": state.step,
                                "action": action.name if isinstance(action, ToolCall) else "finish",
                                "success": observation.success}))
