# Recorded Phase 1 results

These are real Gemini runs produced by `scripts/run_phase1_case.py`, not hand-authored transcripts.
See each case's `trace.json` for every model-selected action and tool observation, `actual.patch`
for the resulting patch, and `assessment.json` for the independent outcome checks.

| Case | Model | Result | Steps | Notable behavior |
| --- | --- | --- | ---: | --- |
| `python-off-by-one` | `gemini-3.1-flash-lite` | Pass | 7 | Ran the failing test, edited one file, reran tests, and inspected the diff. |
| `typescript-api-rename` | `gemini-3.1-flash-lite` | Pass | 15 | Recovered from one rejected exact edit and an early finish rejected by the validation gate. |

Both cases passed an independent post-run validation command, changed exactly the allowed files,
and contained the expected result. Exact model action sequences may vary on future runs.

## Provider reliability observation

Initial `gemini-3.8-flash` trials encountered one transient DNS failure and then exhausted that
model's 20-request free allowance. Those failures led to explicit terminal `model_error` states,
bounded connection/rate-limit recovery, and selection of `gemini-3.1-flash-lite` as the free-tier
baseline. The passing artifacts below use the model recorded in each assessment.
