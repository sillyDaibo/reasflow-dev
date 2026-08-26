from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = (
    ROOT
    / "skills/reasflow/survey/survey-tex-bib-packaging/scripts/build_publication.py"
)
SPEC = importlib.util.spec_from_file_location("build_publication", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_read_tex_tree_expands_nested_inputs_and_stays_inside_root(tmp_path) -> None:
    survey = tmp_path / "survey"
    sections = survey / "sections"
    sections.mkdir(parents=True)
    (survey / "survey.tex").write_text(
        r"\documentclass{article}\input{body}\begin{document}\end{document}",
        encoding="utf-8",
    )
    (survey / "body.tex").write_text(
        r"Body \cite{one}\input{sections/more}\input{../outside}",
        encoding="utf-8",
    )
    (sections / "more.tex").write_text(r"More \cite{two,three}", encoding="utf-8")
    (tmp_path / "outside.tex").write_text(r"Outside \cite{leak}", encoding="utf-8")

    source = MODULE.read_tex_tree(survey / "survey.tex", survey)

    assert MODULE.citation_keys(source) == {"one", "two", "three"}
    assert "Outside" not in source
