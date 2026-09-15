from __future__ import annotations

import json
import logging
from pathlib import Path

from swe_agent.models import AgentState, Event, Finish, Model, Observation, ToolCall
from swe_agent.observability import NullTracer, Tracer
from swe_agent.tools import RepositoryTools

logger = logging.getLogger("swe_agent.agent")


class Agent:
    def __init__(
        self,
        model: Model,
        repository: Path,
        *,
        max_steps: int = 40,
        max_repeated_actions: int = 3,
        allow_dirty: bool = False,
        tracer: Tracer | None = None,
    ) -> None:
        self.model = model
        self.tools = RepositoryTools(repository)
        self.max_steps = max_steps
        self.max_repeated_actions = max_repeated_actions
        self.tracer = tracer or NullTracer()
        if not allow_dirty:
            dirty = self.tools.execute("run_command", {"command": "git status --porcelain"})
            if not dirty.success:
                raise ValueError("Could not inspect Git working tree")
            if dirty.output.strip():
                raise ValueError("Repository has uncommitted changes; commit them or pass allow_dirty=True")

    def run(self, task: str) -> AgentState:
        with self.tracer.agent(
            input={"repository": str(self.tools.root), "task": task},
            metadata={"max_steps": self.max_steps},
        ) as trace:
            state = self._run(task)
            trace.update(
                output={
                    "status": state.status,
                    "steps": state.step,
                    "summary": state.summary,
                    "error": state.error,
                    "validation_succeeded": state.validation_succeeded,
                    "diff_inspected": state.diff_inspected,
                    "final_patch": state.final_patch,
                    "final_validation_succeeded": (
                        None if state.final_validation is None else state.final_validation.success
                    ),
                }
            )
            return state

    def _run(self, task: str) -> AgentState:
        state = AgentState(self.tools.root, task, self.max_steps)
        while state.step < state.max_steps and state.status == "running":
            try:
                action = self.model.next_action(state, self.tools.schemas)
            except Exception as exc:  # noqa: BLE001 - provider failures become inspectable state
                state.status = "model_error"
                state.error = f"{type(exc).__name__}: {exc}"
                logger.error(json.dumps({"event": "model_error", "error": state.error}))
                break
            state.step += 1
            if isinstance(action, ToolCall) and self._is_repeated(state, action):
                observation = Observation(False, "Stopped after repeated identical actions without progress")
                state.events.append(Event(action, observation))
                state.status = "no_progress"
                state.error = observation.output
                self._log(state, action, observation)
                break
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
                finalization_error = self._finalize(state)
                if finalization_error is not None:
                    state.events.append(Event(action, finalization_error))
                    self._log(state, action, finalization_error)
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

    def _finalize(self, state: AgentState) -> Observation | None:
        validation_event = next(
            (
                event
                for event in reversed(state.events)
                if isinstance(event.action, ToolCall)
                and event.action.name == "run_tests"
                and event.observation.success
            ),
            None,
        )
        if validation_event is None:
            return Observation(False, "Finalization requires a previous successful run_tests call")

        before_patch, _ = self.tools.working_tree_patch()
        validation_action = validation_event.action
        if not isinstance(validation_action, ToolCall):
            return Observation(False, "Finalization could not recover the validation command")
        validation_arguments = dict(validation_action.arguments)
        validation_arguments["command"] = validation_event.observation.metadata["command"]
        validation = self.tools.execute("run_tests", validation_arguments)
        state.final_validation = validation
        after_patch, _ = self.tools.working_tree_patch()
        if not validation.success:
            state.validation_succeeded = False
            state.diff_inspected = False
            return Observation(False, "System final validation failed:\n" + validation.output)
        if before_patch != after_patch:
            state.validation_succeeded = False
            state.diff_inspected = False
            return Observation(
                False,
                "System final validation modified the working tree; inspect the changes, clean up, "
                "and validate again.",
            )
        state.final_patch = after_patch
        return None

    def _is_repeated(self, state: AgentState, action: ToolCall) -> bool:
        repeated = 1
        for event in reversed(state.events):
            if not isinstance(event.action, ToolCall) or event.action != action:
                break
            repeated += 1
        return repeated >= self.max_repeated_actions

    @staticmethod
    def _log(state: AgentState, action: ToolCall | Finish, observation: Observation) -> None:
        logger.info(json.dumps({"event": "agent_step", "step": state.step,
                                "action": action.name if isinstance(action, ToolCall) else "finish",
                                "success": observation.success}))
