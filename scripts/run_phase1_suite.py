from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="Run every documented Phase 1 case")
    parser.add_argument("--cases-root", type=Path, default=Path("phase1/cases"))
    parser.add_argument("--output-root", type=Path, default=Path("phase1/results"))
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--max-steps", type=int, default=30)
    args = parser.parse_args()

    cases = sorted(path for path in args.cases_root.iterdir() if (path / "case.json").is_file())
    results: list[dict[str, Any]] = []
    for index, case_directory in enumerate(cases, start=1):
        case = json.loads((case_directory / "case.json").read_text())
        print(f"[{index}/{len(cases)}] {case['id']}", flush=True)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_phase1_case.py",
                str(case_directory),
                "--model",
                args.model,
                "--max-steps",
                str(args.max_steps),
                "--output-root",
                str(args.output_root),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assessment_path = args.output_root / case["id"] / "assessment.json"
        if assessment_path.is_file():
            assessment = json.loads(assessment_path.read_text())
            results.append(
                {
                    "case_id": case["id"],
                    "language": case["language"],
                    "passed": assessment["passed"],
                    "checks": assessment["checks"],
                }
            )
        else:
            results.append(
                {
                    "case_id": case["id"],
                    "language": case["language"],
                    "passed": False,
                    "runner_error": (completed.stderr or completed.stdout)[-2000:],
                }
            )
        print("PASS" if results[-1]["passed"] else "FAIL", flush=True)

    summary = {
        "model": args.model,
        "total": len(results),
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "results": results,
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "suite-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
