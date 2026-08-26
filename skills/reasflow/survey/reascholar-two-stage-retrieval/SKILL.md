---
name: reascholar-two-stage-retrieval
description: Query ReaScholar Domains, structured paper evidence, citation expansion, limitations, and open-problem candidates for a survey, or run a controlled ReaScholar+S2 versus S2-only retrieval ablation.
---

# ReaScholar Survey Evidence

ReaScholar is an optional evidence and relationship layer. It proposes relevant
Domains, categories, timelines, limitations, and future-work questions; it does
not write the outline or determine which claims are true.

Resolve the skill root and profile:

```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/reascholar-two-stage-retrieval"
PROFILE="${REASFLOW_SURVEY_RETRIEVAL_PROFILE:-reascholar-s2}"
```

Both profiles use the same native web and shared S2 core. `reascholar-s2` adds
ReaScholar evidence and bounded citation expansion; `s2-only` must make no
ReaScholar request.

For an unfamiliar or ambiguous topic, inspect Domain discovery before full
retrieval:

```bash
python3 "$SKILL_ROOT/scripts/two_stage_retrieval.py" \
  --topic "<exact topic>" --profile "$PROFILE" --discover-only \
  --out-dir "survey/library/$PROFILE"
```

Select Domains only after checking their title, anchor papers, scope, year
range, and distinction from neighboring meanings. If discovery is weak, use
seed-paper and S2 citation retrieval instead of forcing a Domain.

Run evidence retrieval with the same exact topic and task cutoff:

```bash
python3 "$SKILL_ROOT/scripts/two_stage_retrieval.py" \
  --topic "<exact topic>" --profile "$PROFILE" \
  --task-path frozen_task.yaml --out-dir "survey/library/$PROFILE"
```

Inspect `retrieval_manifest.json`, `required_anchor_audit.json`,
`dedup_report.json`, and `citation_expansion.json` first. Then use the
Codex-first `shortlist`, `inspect`, and `structure` commands rather than loading
the complete pool or Domain prose into the manuscript context.

Evidence rules:

- A selected Domain is a retrieval hypothesis. Reject it when its anchors or
  mechanisms do not match the topic boundary.
- `support_papers` are candidate mappings. Ignore unresolved support IDs and
  verify the source paper before using the claim.
- Timeline prose with no direct citation edge may suggest a question, but it is
  not a verified method transition.
- A Domain timeline is a sparse evidence lead, not a complete history. Recover
  missing foundations and bridge works through backward citations,
  field-defining surveys, and targeted S2/Web searches. Preserve both the
  chronological chain and the mechanism transitions; do not replace one with
  the other.
- Classify every retained lineage relation as direct citation/explicit
  influence, chronological succession, parallel work, or survey inference.
  Use canonical publication metadata for dates; citation-key names are opaque
  identifiers and must not be interpreted as years.
- A paper limitation is not automatically a field-wide open problem.
- Before retaining a gap, search citations and newer papers through the cutoff
  for partial resolution or counterevidence.
- Preserve uncertainty when full text, metadata, or later-work coverage is
  incomplete.
- DOI, arXiv ID, and normalized title must pass the final canonical registry
  gate even if ReaScholar used a different paper key.

Read [references/reascholar-api.md](references/reascholar-api.md) only when
changing API calls or interpreting response fields. Read
[references/profile-contract.md](references/profile-contract.md) before
reporting a controlled retrieval comparison.
