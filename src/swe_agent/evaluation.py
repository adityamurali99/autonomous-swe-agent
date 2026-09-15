import json
from pathlib import Path


def artifacts_complete(output: Path) -> bool:
    """Return whether a case directory has all durable result artifacts."""
    patch = output / "actual.patch"
    if not patch.is_file():
        return False
    try:
        for filename in ("assessment.json", "trace.json"):
            json.loads((output / filename).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return True
