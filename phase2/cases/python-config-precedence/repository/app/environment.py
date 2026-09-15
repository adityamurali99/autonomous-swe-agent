from collections.abc import Mapping


def environment_values(environ: Mapping[str, str]) -> dict[str, object]:
    values: dict[str, object] = {}
    if host := environ.get("SERVICE_HOST"):
        values["host"] = host
    if port := environ.get("SERVICE_PORT"):
        values["port"] = int(port)
    if timeout := environ.get("SERVICE_TIMEOUT"):
        values["timeout"] = int(timeout)
    return values
