---
name: codex-first-survey
description: Research and write a full academic survey or related-work section with Codex as the single owner, using compact evidence tools and deterministic publication checks instead of staged drafting agents.
---

# Codex-first Survey

Own the research map, outline, manuscript, and revisions yourself. Use tools to
improve evidence reliability; do not turn their output into a mandatory outline
or paste a whole paper pool into the writing context.

## Research state

Resolve the installed private skill root, then set:

```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/codex-first-survey"
```

Initialize an auditable run after defining the topic boundary:

```bash
python3 "$SKILL_ROOT/scripts/codex_first_tools.py" init \
  --topic "<topic>" --profile "${REASFLOW_SURVEY_RETRIEVAL_PROFILE:-reascholar-s2}" \
  --include-term "<central concept>" --exclude-term "<known ambiguity>" \
  --state survey/research_state.json
```

Use native web search for discovery. Use `autosurvey-paper-retrieval` for
reproducible S2 search, paper metadata, citations, references, and BibTeX. For
the ReaScholar profile, use `reascholar-two-stage-retrieval` to obtain Domain
and paper evidence, but query and inspect it in small batches.

Merge retrieved JSON/JSONL files into one canonical registry:

```bash
python3 "$SKILL_ROOT/scripts/codex_first_tools.py" merge \
  --input survey/library/search_*.json \
  --input survey/library/reascholar-s2/paper_pool.jsonl \
  --registry survey/library/registry.jsonl \
  --report survey/library/registry_report.json
```

Use `shortlist` before reading a large pool, and `inspect` for chosen IDs. Both
commands return compact JSON and accept `--limit` or explicit IDs. Re-run them
with a new query when the article reveals a missing branch.

Use `structure` only when evaluating a ReaScholar timeline, limitation, gap, or
future-work candidate. It excludes unresolved support and reports the supporting
paper IDs; verify the actual paper evidence before writing the claim.

Use `record` to log consequential choices such as rejected Domains, topic-drift
papers, citation expansion, unresolved metadata, and later-work checks.

## Evidence decisions

- Resolve duplicate identity by DOI, arXiv ID, then normalized title.
- Reject keyword matches whose title, abstract, and mechanism do not support the
  topic boundary.
- Treat categories as comparison hypotheses, not section headings.
- Treat a citation edge as relationship evidence, not proof of a specific claim.
- A gap is unresolved only after checking later work through the task cutoff.
- Never infer missing bibliographic fields from memory.

Validate DOI records against Crossref before generating the bibliography:

```bash
python3 "$SKILL_ROOT/scripts/codex_first_tools.py" validate-doi \
  --registry survey/library/registry.jsonl \
  --output-registry survey/library/registry.validated.jsonl \
  --report survey/library/doi_validation.json
python3 "$SKILL_ROOT/scripts/codex_first_tools.py" bibtex \
  --registry survey/library/registry.validated.jsonl \
  --output survey/references.bib
```

Read the DOI-validation report and do not silently restore rejected or
conflicting identifiers. A network-unavailable record remains explicitly
unverified; a Crossref title mismatch loses the candidate DOI.

## Publication

Write `survey/survey.tex` and `related_works/related_works.tex` directly. Use one
bibliography, registry-assigned keys, and natbib numeric citations. Run:

```bash
python3 "$REASFLOW_PRIVATE_SKILLS_ROOT/survey/survey-tex-bib-packaging/scripts/build_publication.py" --workspace .
python3 "$SKILL_ROOT/scripts/codex_first_tools.py" audit \
  --state survey/research_state.json --registry survey/library/registry.jsonl \
  --survey survey/survey.tex --related related_works/related_works.tex \
  --bib survey/references.bib --output build/research_audit.json
```

Repair only observed publication or evidence failures, then rerun both checks.
