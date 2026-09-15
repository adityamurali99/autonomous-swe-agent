# Ten-case Gemini baseline

These artifacts are real `gemini-3.1-flash-lite` runs produced by the frozen agent and case set on
September 14, 2026. They are not hand-authored transcripts. Every case directory contains the raw
agent trace, resulting patch, and independent assessment.

## Results

| Case | Raw result | Adjudicated | Steps | Finding |
| --- | --- | --- | ---: | --- |
| `python-clamp-boundary` | Pass | Pass | 7 | Minimal one-file fix. |
| `python-csv-whitespace` | Fail | Pass | 8 | Evaluator rejected `tag.strip()` because it expected `part.strip()`. |
| `python-makefile-discovery` | Pass | Pass | 9 | Discovered and used `make test`. |
| `python-missing-slugify` | Fail | Pass | 10 | Evaluator rejected equivalent single-quoted syntax. |
| `python-off-by-one` | Pass | Pass | 10 | Correct fix; completion gate required a second validation through `run_tests`. |
| `typescript-api-rename` | Pass | Pass | 14 | Correct coordinated two-file rename. |
| `typescript-async-return` | Fail | Fail | 17 | Fixed behavior but unnecessarily changed dependency manifests. |
| `typescript-falsy-default` | Fail | Fail | 8 | Repeated repository listing without editing; no-progress stop. |
| `typescript-prefix-check` | Pass | Pass | 8 | Minimal one-file fix with runtime tests. |
| `typescript-signature-update` | Fail | Fail | 9 | Existing tests passed, then repeated listing without editing. |

- Raw machine score: **5/10**.
- Manually adjudicated task score: **7/10**.
- Independent validation passed after **all 10 runs**, but this is misleading for the two no-edit
  cases because their fixture tests did not encode the requested new behavior.

## Repeatable failure patterns

### 1. Passing tests can distract the model from an unfinished task

Both `typescript-falsy-default` and `typescript-signature-update` had tests that passed before the
requested change. In both runs, the model inspected the relevant implementation, later observed a
successful type-check or repository state, and then repeated `list_files` three times. The
no-progress guard correctly stopped both runs, but the agent never made the requested edit.

This is the strongest agent-level pattern: **2/10 runs had the same terminal state, repeated tool,
and absence of a patch**. The next behavior improvement should make task satisfaction explicit and
prevent a passing validation command from being treated as evidence that an unimplemented request
is complete.

### 2. Exact source-string checks produce false negatives

Two correct Python patches were marked failed solely because the evaluator required implementation
spelling rather than behavior. The CSV solution used `tag` instead of `part`; the slug solution used
single quotes and intermediate variables. Both changed only the intended file and passed independent
tests. This affected **2/10 runs** and means evaluator repair should precede agent optimization.

### 3. Ad hoc validation can pollute the patch

For `typescript-async-return`, the model correctly diagnosed and fixed the missing `await`, but used
`npm i --save-dev @types/node` to support a temporary test. It removed the temporary test but left
changes in both package manifests. This occurred once, so it is a real failure but not yet a
repeatable pattern. A future safety policy should discourage dependency installation unless the task
requires it and should re-check unexpected changed files before finishing.

### 4. Models often validate through the generic command tool

Several runs invoked tests with `run_command` before eventually using `run_tests`. Because the
completion gate recognizes only `run_tests`, otherwise successful runs required extra steps. The gate
protected correctness, but the distinction between the tools is not clear enough to the model. This
is an efficiency issue, not a demonstrated correctness failure.

## Recommended next changes

1. Replace exact implementation-string scoring with behavioral assertions plus explicit forbidden
   content or API checks where necessary.
2. Add a compact task-progress signal to model context: whether any edit has occurred and whether
   the current diff is empty.
3. Strengthen the prompt: passing existing tests does not prove a requested behavioral or API change
   has been implemented.
4. Surface the changed-file list after edits and warn before dependency-manifest changes unrelated
   to the task.
5. Repeat the same ten cases at least three times before claiming a stable success-rate change.

Do not optimize based on the async dependency pollution yet; it appeared only once. The repeated
no-edit loop and evaluator false negatives have enough evidence to address first.
