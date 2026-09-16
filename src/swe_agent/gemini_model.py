from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, cast

from google import genai

from swe_agent.models import AgentState, Finish, JsonObject, ModelUsage, ToolCall
from swe_agent.observability import NullTracer, Tracer, load_local_env

SYSTEM_PROMPT = """You are an autonomous software engineering agent operating on a local repository.
Use one tool at a time. Inspect before editing. Discover repository instructions and validation
commands instead of assuming a language. Treat tool errors and test failures as evidence, fix the
cause, and rerun tests after every edit.

Follow this engineering sequence:
1. Inspect repository instructions and structure with focused queries.
2. Reproduce the reported behavior once when practical.
3. Locate the responsible production-code path and form a causal hypothesis.
4. Make the smallest production-code change that addresses that cause.
5. Run the narrowest relevant validation, then broaden validation if appropriate.
6. Inspect the final Git diff and remove temporary or unrelated changes.

Use the progress object as current evidence. If it contains guidance, change strategy accordingly.
Do not create repeated variations of an already demonstrated reproduction. Do not make speculative
edits before locating the implementation. Call finish only when the task is complete, tests pass,
and the diff contains only intended changes. Keep the finish summary concise and mention validation.
Do not change dependency manifests or lockfiles unless the task requires it; when it does, explicitly
allow the command and explain why. If the existing suite passes before a fix, a green suite alone does
not prove the reported bug is fixed. Remove temporary reproduction files before final validation."""


def load_local_api_key(path: Path = Path(".env")) -> str | None:
    """Read GEMINI_API_KEY from a local ignored env file without mutating process state."""
    return load_local_env(path).get("GEMINI_API_KEY") or None


class GeminiModel:
    def __init__(
        self,
        model: str = "gemini-3.1-flash-lite",
        *,
        api_key: str | None = None,
        client: Any | None = None,
        max_rate_limit_retries: int = 3,
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
        tracer: Tracer | None = None,
    ) -> None:
        self.client = client or genai.Client(
            api_key=api_key or load_local_api_key(),
            http_options={"retry_options": {"attempts": 1}},
        )
        self.model = model
        self.max_rate_limit_retries = max_rate_limit_retries
        self.input_cost_per_million = input_cost_per_million
        self.output_cost_per_million = output_cost_per_million
        self.usage = ModelUsage()
        self.tracer = tracer or NullTracer()

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
        context = self._context(state)
        trace_input: JsonObject = {"context": json.loads(context), "tools": tools}
        with self.tracer.generation(
            name="gemini-next-action", model=self.model, input=trace_input
        ) as generation:
            usage_before = self.usage
            interaction = self._create_interaction(
                model=self.model,
                input=context,
                tools=tools,
                generation_config={
                    "tool_choice": {
                        "allowed_tools": {"mode": "any", "tools": [tool["name"] for tool in tools]}
                    }
                },
            )
            self._record_usage(getattr(interaction, "usage", None))
            for raw_step in interaction.steps or []:
                step = cast(Any, raw_step)
                if step.type != "function_call":
                    continue
                name = str(step.name)
                arguments = cast(JsonObject, step.arguments)
                generation.update(
                    output={"tool": name, "arguments": arguments},
                    usage_details={
                        "input": self.usage.input_tokens - usage_before.input_tokens,
                        "output": self.usage.output_tokens - usage_before.output_tokens,
                        "total": self.usage.total_tokens - usage_before.total_tokens,
                    },
                )
                if name == "finish":
                    return Finish(str(arguments["summary"]))
                return ToolCall(name, arguments)
            raise RuntimeError("Gemini response did not contain a function call")

    def _create_interaction(self, **request: Any) -> Any:
        for attempt in range(self.max_rate_limit_retries + 1):
            try:
                self.usage = ModelUsage(
                    requests=self.usage.requests + 1,
                    input_tokens=self.usage.input_tokens,
                    output_tokens=self.usage.output_tokens,
                    total_tokens=self.usage.total_tokens,
                    estimated_cost_usd=self.usage.estimated_cost_usd,
                )
                return cast(Any, self.client.interactions.create(**request))
            except Exception as exc:
                status_code = getattr(exc, "status_code", None)
                rate_limited = status_code == 429
                server_failed = isinstance(status_code, int) and status_code >= 500
                connection_failed = type(exc).__name__ in {"APIConnectionError", "APITimeoutError"}
                if not (rate_limited or server_failed or connection_failed) or attempt == self.max_rate_limit_retries:
                    raise
                match = re.search(r"retry in ([0-9.]+)s", str(exc), re.IGNORECASE) if rate_limited else None
                delay = float(match.group(1)) if match else min(2 ** attempt, 30)
                time.sleep(delay + 0.25)
        raise RuntimeError("unreachable")

    def _record_usage(self, provider_usage: Any) -> None:
        if provider_usage is None:
            return
        input_tokens = int(self._usage_value(provider_usage, "total_input_tokens") or 0)
        output_tokens = int(self._usage_value(provider_usage, "total_output_tokens") or 0)
        total_tokens = int(
            self._usage_value(provider_usage, "total_tokens") or input_tokens + output_tokens
        )
        incremental_cost = (
            input_tokens * self.input_cost_per_million
            + output_tokens * self.output_cost_per_million
        ) / 1_000_000
        self.usage = ModelUsage(
            requests=self.usage.requests,
            input_tokens=self.usage.input_tokens + input_tokens,
            output_tokens=self.usage.output_tokens + output_tokens,
            total_tokens=self.usage.total_tokens + total_tokens,
            estimated_cost_usd=self.usage.estimated_cost_usd + incremental_cost,
        )

    @staticmethod
    def _usage_value(provider_usage: Any, name: str) -> Any:
        if isinstance(provider_usage, dict):
            return provider_usage.get(name)
        return getattr(provider_usage, name, None)

    @staticmethod
    def _gemini_schema(schema: JsonObject) -> JsonObject:
        return {key: value for key, value in schema.items() if key != "strict"}

    @staticmethod
    def _context(state: AgentState) -> str:
        history = []
        for event in state.model_events if state.model_events is not None else state.events:
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
                "progress": state.progress,
                "history": history,
            },
            ensure_ascii=False,
        )
