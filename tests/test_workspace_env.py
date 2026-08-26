from __future__ import annotations

import os
import sys
from pathlib import Path


SURVEY_SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "reasflow" / "survey"
if str(SURVEY_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SURVEY_SKILL_ROOT))

from workspace_env import load_workspace_s2_credentials, load_workspace_survey_env


def clear_s2_env(monkeypatch) -> None:
    for name in (
        "SEMANTIC_SCHOLAR_API_KEY",
        "S2_API_KEY",
        "REASCHOLAR_BASE_URL",
        "REASFLOW_ENV_FILE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_loads_key_from_nearest_workspace_ancestor(tmp_path, monkeypatch) -> None:
    clear_s2_env(monkeypatch)
    workspace = tmp_path / "workspaces"
    nested = workspace / "runs" / "one" / "arm"
    nested.mkdir(parents=True)
    (workspace / ".env.local").write_text(
        "UNRELATED_SECRET=do-not-load\nSEMANTIC_SCHOLAR_API_KEY='workspace-key'\n",
        encoding="utf-8",
    )

    loaded = load_workspace_s2_credentials(start=nested)

    assert loaded == workspace / ".env.local"
    assert os.environ["SEMANTIC_SCHOLAR_API_KEY"] == "workspace-key"
    assert "UNRELATED_SECRET" not in os.environ


def test_explicit_environment_is_never_overwritten(tmp_path, monkeypatch) -> None:
    clear_s2_env(monkeypatch)
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "explicit-key")
    (tmp_path / ".env.local").write_text(
        "SEMANTIC_SCHOLAR_API_KEY=workspace-key\n", encoding="utf-8"
    )

    loaded = load_workspace_s2_credentials(start=tmp_path)

    assert loaded is None
    assert os.environ["SEMANTIC_SCHOLAR_API_KEY"] == "explicit-key"


def test_explicit_env_file_supports_s2_alias(tmp_path, monkeypatch) -> None:
    clear_s2_env(monkeypatch)
    env_file = tmp_path / "credentials.env"
    env_file.write_text("export S2_API_KEY=alias-key\n", encoding="utf-8")
    monkeypatch.setenv("REASFLOW_ENV_FILE", str(env_file))

    loaded = load_workspace_s2_credentials(start=tmp_path / "unrelated")

    assert loaded == env_file
    assert os.environ["S2_API_KEY"] == "alias-key"


def test_survey_loader_reads_local_reascholar_url_with_s2_key(
    tmp_path, monkeypatch
) -> None:
    clear_s2_env(monkeypatch)
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "explicit-key")
    (tmp_path / ".env.local").write_text(
        "SEMANTIC_SCHOLAR_API_KEY=workspace-key\n"
        "REASCHOLAR_BASE_URL=http://127.0.0.1:8010\n",
        encoding="utf-8",
    )

    loaded = load_workspace_survey_env(start=tmp_path)

    assert loaded == tmp_path / ".env.local"
    assert os.environ["SEMANTIC_SCHOLAR_API_KEY"] == "explicit-key"
    assert os.environ["REASCHOLAR_BASE_URL"] == "http://127.0.0.1:8010"
