# Manual failure taxonomy

Assign one primary code to every officially unresolved task. Add secondary codes only when they
materially contributed. Evidence must reference concrete steps in the task's `trace.json`.

| Code | Failure mode | Evidence threshold |
| --- | --- | --- |
| `INFRA_SETUP` | Checkout, dependency, or environment failure | The agent could not reach a usable repository for reasons outside its decisions. |
| `BUILD_DISCOVERY` | Wrong build or test command | Repository evidence supported another command that the agent failed to discover or use. |
| `REPRODUCTION` | Did not establish the reported failure | Existing tests were green or insufficient, and the agent did not create a focused reproduction. |
| `LOCALIZATION` | Failed to find the relevant implementation | The trace never reads or searches the code needed for the gold behavior. |
| `CONTEXT_MISSING` | Found the area but omitted a required dependency or invariant | A needed caller, helper, test, or documentation file was available but absent from reasoning. |
| `CONTEXT_NOISE` | Excessive exploration displaced useful progress | Repeated broad reads/searches consume the run without improving localization. |
| `IMPLEMENTATION` | Correct area, incorrect code change | Patch does not implement the issue behavior or introduces a regression. |
| `TEST_INTERPRETATION` | Misread test output or validated the wrong property | Available command output contradicted the agent's conclusion. |
| `RECOVERY` | Failed to adapt after actionable failure evidence | Subsequent actions repeat or ignore the demonstrated cause. |
| `PREMATURE_FINISH` | Declared completion without adequate task evidence | Harness gate passed, but reproduction or meaningful validation was absent. |
| `PATCH_SCOPE` | Unrelated, generated, test, or dependency changes | Patch includes changes unnecessary for the requested production fix. |
| `RESOURCE_LIMIT` | Step, time, token, or cost limit ended useful work | Trace shows reasonable progress but the configured budget terminated it. |
| `MODEL_PROVIDER` | Provider error or quota exhaustion | No agent behavior conclusion is possible from the failed request. |
| `BENCHMARK_AMBIGUITY` | Official task or tests appear inconsistent | Use only with concrete evidence and separate human review; never as a default explanation. |

## Review record

For each failure, record:

- primary code;
- optional secondary codes;
- one- or two-sentence evidence with trace step numbers;
- whether the problem is likely addressable in the agent, model, tool layer, or infrastructure;
- the smallest plausible improvement;
- confidence: high, medium, or low.

Do not classify a failure from the final patch alone. The purpose is to identify where the harness
failed so the next intervention is based on repeated causal evidence rather than anecdotes.
