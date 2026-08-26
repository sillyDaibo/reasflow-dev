---
name: reascholar-two-stage-retrieval
description: Build evidence-grounded survey retrieval artifacts with ReaScholar's Topic-to-Domain-to-Paper workflow and Semantic Scholar as a controlled supplement. Use for survey or related-work research, outline construction from domain timelines, literature coverage of gaps and future work, or controlled ReaScholar+S2 versus S2-only retrieval comparisons.
---

# ReaScholar Two-Stage Retrieval

Treat a ReaScholar Domain page as a high-value map, never as ground truth. Use it to propose scope, chronology, limitations, and future-work questions. Confirm every material claim against specific papers or independent searches before drafting it as fact.

## Run the workflow

Semantic Scholar credentials are resolved automatically. An explicit
`SEMANTIC_SCHOLAR_API_KEY` or `S2_API_KEY` in the process environment takes
precedence; otherwise the runtime searches from the current workspace upward
for the nearest `.env.local` and loads only those two allowlisted variables.
Set `REASFLOW_ENV_FILE` to use a different credential file. Credentials are
never written to retrieval artifacts, cache keys, or logs.

Resolve the private skill root and create the survey library:

```bash
REASFLOW_PRIVATE_SKILLS_ROOT="${REASFLOW_PRIVATE_SKILLS_ROOT:-$(pwd)/.codex/reasflow-skills}"
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/reascholar-two-stage-retrieval"
mkdir -p survey/library
```

Run the default ReaScholar+S2 profile:

```bash
python3 "$SKILL_ROOT/scripts/two_stage_retrieval.py" \
  --topic "<exact survey topic>" \
  --profile reascholar-s2 \
  --task-path frozen_task.yaml \
  --out-dir survey/library/reascholar-s2
```

For a controlled baseline, change only the profile and output directory:

```bash
python3 "$SKILL_ROOT/scripts/two_stage_retrieval.py" \
  --topic "<same exact survey topic>" \
  --profile s2-only \
  --task-path frozen_task.yaml \
  --out-dir survey/library/s2-only
```

Both profiles run the same four-query Semantic Scholar evidence core and, when `--task-path` supplies key references, the same bounded exact-title S2 anchor audit. The `reascholar-s2` profile adds three Domain-filtered ReaScholar queries and Domain structure; it never replaces or suppresses shared S2. Inspect `required_anchor_audit.json` before any extra targeted search. The `s2-only` profile makes no ReaScholar request. Set `SEMANTIC_SCHOLAR_API_KEY` when available; never put it in commands, prompts, or artifacts.

Each shared S2 query returns at most 60 candidates by default. This provides
enough unique candidates for the 100-paper survey publication gate while
keeping the query count identical in both profiles. Lower limits are suitable
only for retrieval smoke tests, not full survey generation.

The assisted profile also walks one bounded citation hop from at most 12
ReaScholar detail seeds: at most three references and two cited-by papers per
seed, with at most 30 new papers globally. Empty citation records do not consume
the seed budget, and candidates must pass the generation-visible task relevance,
cutoff, and canonical-dedup gates. If the local within-corpus graph yields fewer
than 12 additions, the workflow uses a bounded, cached Semantic Scholar one-hop
fallback from those same ReaScholar-selected seeds. This fallback is additive
treatment behavior, not part of the shared four-query S2 core. Inspect
`citation_expansion.json` for every request, provider, seed, direction, hop, and
retained paper; inspect `additive_s2_citation_query_count` in the retrieval
manifest when reporting cost. Use the structure-only A/B below when the paper
pool must remain identical.

## Select domains deliberately

For important or cross-domain surveys, first run discovery without retrieving papers:

```bash
python3 "$SKILL_ROOT/scripts/two_stage_retrieval.py" \
  --topic "<topic>" \
  --profile reascholar-s2 \
  --out-dir survey/library/reascholar-s2 \
  --discover-only
```

Read `domain_discovery.json`. Inspect topic relevance, anchor papers, L1 diversity, year range, and paper count. Then rerun with two to five justified L2 IDs:

```bash
python3 "$SKILL_ROOT/scripts/two_stage_retrieval.py" \
  --topic "<same topic>" \
  --profile reascholar-s2 \
  --domain-id <id> --domain-id <id> \
  --out-dir survey/library/reascholar-s2
```

Never reuse Domain IDs from an older run: IDs belong to the current database snapshot and can change.

## Consume the artifacts

Read these files in order:

1. `retrieval_manifest.json` and `required_anchor_audit.json`: confirm profile, shared query budget, exact-title anchor coverage, cutoff, diagnostics, and selected domains.
2. `dedup_report.json` and `citation_expansion.json`: require zero duplicate canonical identities and inspect every citation-neighbor addition.
3. `domain_scaffold.json` and `outline_context.md`: organize an initial outline around domain scope and timeline. Mark every domain-derived statement as provisional.
4. `evidence_ledger.json`: distinguish mapped support papers from unresolved IDs and independently retrieved evidence.
5. `structure_pack.json` and `structure_pack.md`: compact, provisional taxonomy, timeline, gap/future-work, and within-pool citation relations for the optional structure treatment.
6. `paper_details.json`: check problem setting, method, experiments, limitations, proofs, and citation links for final candidates.
7. `paper_pool.jsonl`: pass this path to AutoSurvey as the frozen external library.

Use the pool when preparing outline and survey data:

```bash
python3 "$REASFLOW_PRIVATE_SKILLS_ROOT/survey/autosurvey-execution/scripts/autosurvey_tools.py" \
  prepare-outline-data --topic "<topic>" \
  --library-dir survey/library/reascholar-s2 \
  --structure-mode auto \
  --output-path survey/stage1.json
```

The generated prompt JSON records the structure-pack path, SHA-256, item counts, and the frozen `paper_pool.jsonl` SHA-256. Do not inject unverified Domain prose into the final survey outside this controlled structure input.

## Run the lightweight structure-only A/B

Use this experiment first when testing whether ReaScholar organization helps. Retrieve once, freeze the library, then prepare two arms from the same directory. Do not run any additional search between the two arms.

```bash
LIBRARY="survey/library/reascholar-s2"
TOOLS="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/autosurvey-execution/scripts/autosurvey_tools.py"

python3 "$TOOLS" prepare-outline-data \
  --topic "<same exact topic>" --library-dir "$LIBRARY" \
  --structure-mode include --output-path survey/treatment_outline_prompt.json

python3 "$TOOLS" prepare-outline-data \
  --topic "<same exact topic>" --library-dir "$LIBRARY" \
  --structure-mode exclude --output-path survey/control_outline_prompt.json
```

After each arm produces its outline, use the same switch for writing:

```bash
python3 "$TOOLS" prepare-native-survey-data \
  --topic "<same exact topic>" --library-dir "$LIBRARY" \
  --outline-path survey/treatment_outline.md --structure-mode include \
  --output-path survey/treatment_survey_prompt.json

python3 "$TOOLS" prepare-native-survey-data \
  --topic "<same exact topic>" --library-dir "$LIBRARY" \
  --outline-path survey/control_outline.md --structure-mode exclude \
  --output-path survey/control_survey_prompt.json
```

Before interpreting the result, verify that both prompt JSON files have identical `paper_library.paper_pool_sha256`, paper counts, model, word targets, and other generation settings. The treatment changes only access to the structure pack. `--structure-mode include` fails if the pack is missing or empty; `exclude` guarantees no structure text enters the prompt.

## Evidence rules

- Use Domain `timeline`, `limitations`, and `future_works` to identify questions, branches, and candidate support papers.
- Write a limitation as an unresolved gap only after checking its source paper and
  later-work/counterevidence status at the evaluation cutoff. State the affected
  capability, scope, or assumption and cite the source that actually supports it.
- A Domain future-work item is usable as evidence only when it names source support,
  explains `why_now`, and supplies a concrete `first_step`. Prefer directions that
  also state a falsifiable prediction, evaluation protocol, or feasibility constraint.
  A result, contribution, theorem conclusion, or generic paper summary is never
  future-work evidence.
- When no verified Domain future-work synthesis is available, derive a direction only
  from checked paper limitations plus later-work/counterevidence search. Label the
  result as an inference and keep the supporting sources adjacent. Do not fill an
  empty future-work field with conclusions, profiles, or other evidence statements.
- Ignore `unresolved_support_paper_ids` as citations.
- Treat `support_papers` as precise candidate mappings, not automatic confirmation that the Domain synthesis is correct.
- Prefer primary-paper details or source Markdown for technical claims. Use theorem cards for formal statements and experiment fields for empirical claims.
- Search for counter-evidence before asserting that a gap remains open at the cutoff.
- If a Domain claim conflicts with a paper, revise or drop the claim. Never repair the paper evidence to match the Domain page.
- Use S2 to supplement metadata, find papers outside the ReaScholar snapshot, and chase citation/reference edges. Do not let citation count override topical relevance.
- Record uncertainty explicitly when coverage or freshness is incomplete.
- Treat DOI, arXiv ID, ReaScholar key, and normalized title as linked identity
  evidence. `dedup_report.json` and final package
  `canonical_reference_dedup.gate_passed` must both be true; duplicate canonical
  references are a failed run, even when their BibTeX keys differ.

Read [references/reascholar-api.md](references/reascholar-api.md) when changing API calls or interpreting response fields. Read [references/profile-contract.md](references/profile-contract.md) before running or reporting an A/B comparison.
