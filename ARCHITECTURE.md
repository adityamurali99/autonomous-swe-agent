# Minimal architecture

## Shape of the system

The smallest useful design has five boundaries:

1. **CLI/application** accepts a repository path, task, model, and limits.
2. **Agent loop** owns state, asks a model for exactly one next action, executes it, and records
   the observation. It knows nothing about repository languages.
3. **Model adapter** converts state plus tool schemas into a model request and converts the
   response into either a tool call or a finish request. The OpenAI adapter can be replaced in
   tests or future routing experiments.
4. **Tool registry** exposes typed, schema-described repository capabilities and dispatches calls.
   All filesystem operations are constrained to the repository root.
5. **Command discovery** examines conventional manifests and documentation and returns ranked
   validation candidates with evidence. It does not silently execute them.

This is intentionally a loop, not a planner/executor graph. Planning, context compression,
model routing, retries, and evaluation can later be introduced behind the model adapter or as
policies around the loop without changing tools.

## Folder structure

```text
src/swe_agent/
  agent.py       # state machine and completion invariants
  models.py      # actions, observations, state, and model protocol
  gemini_model.py# production model adapter
  tools.py       # generic repository tools and registry
  discovery.py   # build/test command inference
  cli.py         # composition root
tests/           # deterministic unit and vertical-slice tests
```

## Component responsibilities

- `models.py`: stable domain types. It prevents provider payloads and subprocess details from
  leaking through the system.
- `agent.py`: advances state one action at a time, enforces step limits, and requires successful
  test execution plus diff inspection before accepting completion.
- `tools.py`: validates arguments, performs bounded I/O/process work, truncates observations, and
  reports errors as data so the model can recover.
- `discovery.py`: recognizes `package.json`, `pyproject.toml`, `Makefile`, CMake, Maven, and Gradle,
  and supplies plausible commands with the file that justified each one.
- `gemini_model.py`: contains prompting, local API-key loading, rate-limit recovery, and provider translation only.
- `cli.py`: wires dependencies, emits structured JSON logs, and renders the final result.

## Agent state

`AgentState` contains the immutable task and repository path plus an ordered event history,
current step, maximum steps, validation state, whether a diff was inspected, the system-owned
final validation result and patch, and terminal status/summary. The history is the initial context
strategy: retain all bounded observations. A later context selector can project this state into a
smaller model view.

An event is an `Action` paired with its `Observation`. Actions are either a named tool call with
JSON arguments or a finish request. Observations contain success, textual output, structured
metadata, and truncation status. Failures are observations rather than exceptions at the loop
boundary, enabling recovery.

## Tool interface

Every tool provides `name`, `description`, JSON `parameters`, and `execute(arguments) ->
Observation`. The initial registry contains:

- `list_files(path, max_depth)`
- `read_file(path, start_line, end_line)`
- `search_code(query, path, glob)`
- `edit_file(path, old_text, new_text, expected_replacements)`
- `run_command(command, timeout_seconds, allow_dependency_changes, dependency_change_reason)`
- `run_tests(command?, timeout_seconds)`
- `inspect_diff()`

`edit_file` uses exact replacement to make edits reviewable and detect stale context. A future
patch-based editor can implement the same interface. `run_tests` accepts an explicit discovered
command or selects the highest-ranked candidate. `run_command` exists for builds and focused
checks; process output and runtime are bounded. Commands are transactional around common dependency
manifests and lockfiles. Unauthorized changes are restored and reported as a failed observation;
tasks that genuinely require dependency changes must opt in with a non-empty reason. Test commands
always use the protected path.

## Loop and completion

The model receives the task, current state, recent tool observations, and tool schemas. It returns
one tool call. The registry executes it and appends an event. Tool errors remain in history and the
model chooses how to recover. A finish request is considered only after a successful `run_tests`
and `inspect_diff`; otherwise the loop returns a corrective observation. The system then reruns the
exact successful validation command, rejects completion if validation fails or changes the
working-tree patch, and captures a fresh authoritative diff against `HEAD`. This final diff includes
staged, unstaged, and untracked files and does not depend on an earlier model observation. The loop
stops on accepted completion or a configured step limit.

This completion gate proves that review happened and that the returned patch is the same state that
passed final validation; it does not prove that the implementation satisfies the task. Richer
policies can require targeted and full suites, clean diagnostics, or evaluator approval later.

## Build and test discovery

Discovery is evidence-based and ordered. It checks conventional files without assuming the code
language: package-manager lockfiles and `package.json` scripts; pytest configuration or Python
project metadata; Make targets; CMake; Maven wrappers/POM; and Gradle wrappers/build files.
Repository-owned wrappers and explicit test scripts rank above generic commands. Candidate output
is visible to the model through `run_tests` metadata, so it can override a poor guess. Documentation
can be searched by the model when conventions are insufficient.

## Smallest end-to-end milestone

Given a local Git repository and bug report, a model can list/read/search, make an exact edit,
discover or explicitly invoke tests, react to a failed test with another edit, inspect `git diff`,
and return an explanation and validated patch. The vertical-slice test demonstrates this entire
loop with a deterministic fake model and a temporary Python repository; provider quality is kept
out of the correctness test.

Not in milestone one: sandboxing untrusted repositories, remote cloning, multi-agent planning,
semantic indexing, persistent memory, PR creation, benchmark orchestration, or UI. These are useful
only after the basic completion loop is measurable.
