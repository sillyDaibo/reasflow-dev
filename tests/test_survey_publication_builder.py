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


def test_canonical_duplicate_groups_detects_different_keys_for_same_paper() -> None:
    bibliography = r"""
@article{preprint,
  title={A Forward-Backward Splitting Method for Monotone Inclusions without Cocoercivity},
  author={Y. Malitsky and M. K. Tam},
  eprint={1808.04162}
}
@article{published,
  title={A forward-backward splitting method for monotone inclusions without cocoercivity},
  author={Y. Malitsky and M. K. Tam},
  journal={SIAM Journal on Optimization}
}
"""

    groups = MODULE.canonical_duplicate_groups(bibliography)

    assert len(groups) == 1
    assert groups[0]["keys"] == ["preprint", "published"]
    assert groups[0]["identities"][0].startswith("title:")


def test_canonical_duplicate_groups_combines_multiple_shared_identities() -> None:
    bibliography = r"""
@article{one, title={A Shared Paper Title}, doi={10.1000/shared}}
@article{two, title={A Shared Paper Title}, doi={10.1000/shared}}
"""

    groups = MODULE.canonical_duplicate_groups(bibliography)

    assert len(groups) == 1
    assert groups[0]["keys"] == ["one", "two"]
    assert len(groups[0]["identities"]) == 2
