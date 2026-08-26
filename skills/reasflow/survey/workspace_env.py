"""Load allowlisted survey settings from a workspace-local env file."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


S2_CREDENTIAL_NAMES = ("SEMANTIC_SCHOLAR_API_KEY", "S2_API_KEY")
SURVEY_ENV_NAMES = (*S2_CREDENTIAL_NAMES, "REASCHOLAR_BASE_URL")


def _parse_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_workspace_survey_env(
    *,
    start: Path | None = None,
    names: Iterable[str] = SURVEY_ENV_NAMES,
) -> Path | None:
    """Load missing allowlisted survey settings from the nearest `.env.local`.

    Explicit process environment always wins. Unrelated workspace secrets are
    ignored, and values are never logged or written to generated artifacts.
    """

    allowed = tuple(names)
    missing = {name for name in allowed if not os.getenv(name, "").strip()}
    if not missing:
        return None

    explicit_file = os.getenv("REASFLOW_ENV_FILE", "").strip()
    if explicit_file:
        candidates = [Path(explicit_file).expanduser()]
    else:
        current = (start or Path.cwd()).resolve()
        candidates = [current / ".env.local", *(parent / ".env.local" for parent in current.parents)]

    for candidate in candidates:
        if not candidate.is_file():
            continue
        loaded_from_candidate = False
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].lstrip()
            if "=" not in line:
                continue
            name, raw_value = line.split("=", 1)
            name = name.strip()
            if name not in missing or os.getenv(name, "").strip():
                continue
            value = _parse_env_value(raw_value)
            if value:
                os.environ[name] = value
                loaded_from_candidate = True
        if loaded_from_candidate:
            return candidate
    return None


def load_workspace_s2_credentials(*, start: Path | None = None) -> Path | None:
    """Backward-compatible loader restricted to S2 credentials."""

    return load_workspace_survey_env(start=start, names=S2_CREDENTIAL_NAMES)
