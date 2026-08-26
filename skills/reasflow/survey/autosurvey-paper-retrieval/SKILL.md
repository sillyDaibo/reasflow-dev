---
name: autosurvey-paper-retrieval
description: Retrieve reproducible scholarly metadata and citation/reference neighbors for a survey when native web discovery needs canonical paper records.
---

# Paper Retrieval

Use native Codex web search for broad discovery and current primary sources.
Use this helper for reproducible Semantic Scholar or ReaScholar metadata and
graph operations. Keep every response under `survey/library/`; merge it into the
Codex-first canonical registry before citing it.

Resolve the private skill root:

```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/autosurvey-paper-retrieval"
```

Semantic Scholar credentials are loaded from the process environment, or from
the nearest `.env.local` when absent. Only `SEMANTIC_SCHOLAR_API_KEY` and
`S2_API_KEY` are loaded. Never put a key in a command or artifact.

```bash
python3 "$SKILL_ROOT/scripts/autosurvey_literature.py" search \
  --source semantic_scholar --query "<focused query>" --limit 20 \
  --out survey/library/search_<name>.json

python3 "$SKILL_ROOT/scripts/autosurvey_literature.py" paper \
  --source semantic_scholar --paper-id "<DOI, arXiv, or S2 ID>" \
  --out survey/library/paper_<name>.json

python3 "$SKILL_ROOT/scripts/autosurvey_literature.py" references \
  --paper-id "<ID>" --limit 20 --out survey/library/refs_<name>.json

python3 "$SKILL_ROOT/scripts/autosurvey_literature.py" citations \
  --paper-id "<ID>" --limit 20 --out survey/library/cites_<name>.json
```

Search in focused batches. Inspect title, abstract, identifiers, year, venue,
and retrieval source before adding a record. Citation count is not relevance.
Use references to recover foundations and citations to check successors or
later resolutions. A graph edge does not by itself support a lineage claim.

Do not generate the final bibliography directly from heterogeneous search
files. Merge and audit them with the `codex-first-survey` registry tools first.
