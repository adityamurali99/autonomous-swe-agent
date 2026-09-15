from __future__ import annotations

import argparse
from pathlib import Path

from swe_agent.benchmarks.swebench_lite import fetch_official_tasks, write_mirror


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror official SWE-bench Lite task data")
    parser.add_argument("--output", type=Path, default=Path("evals/swebench_lite"))
    args = parser.parse_args()

    tasks = fetch_official_tasks()
    write_mirror(tasks, args.output)
    print(f"Mirrored {len(tasks)} tasks to {args.output}")


if __name__ == "__main__":
    main()
