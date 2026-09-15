import json
from pathlib import Path


def file_values(path: str | Path) -> dict[str, object]:
    return json.loads(Path(path).read_text())
