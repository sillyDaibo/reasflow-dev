# ReaScholar API contract used by this skill

Source of truth: `Database_For_Agents/docs/search-api.md` in the ReaScholar repository. Production base URL defaults to `https://scholar.reaslab.io` and can be overridden with `REASCHOLAR_BASE_URL`.

## Stage 1: domain discovery

`POST /api/search/domains`

```json
{
  "query": "research topic",
  "top_k": 8,
  "search_depth": 160,
  "anchor_paper_count": 3
}
```

Ranked L2 candidates contain Domain/L1 IDs, title, description, counts, year range, score breakdown, matched terms, reason, anchor papers, and detail links. Ranking produces candidates rather than a single authoritative classification.

`GET /api/search/domains/{l2_domain_id}` returns `display.overview`, `timeline`, `limitations`, `future_works`, `top_papers`, and `provenance`. Timeline/limitation/future entries can contain exact `support_papers` mappings and `unresolved_support_paper_ids`. Unresolved IDs are not usable citations.

## Stage 2: paper search and detail

`POST /api/search` with `response_format: structured` and `filters.l2_domain_ids` searches within selected domains. Keep `include_details` and `include_raw` false during recall. Supported focused modes include `agent`, `fast`, `model`, `algorithm`, `theorem`, and `code`.

`POST /api/search/papers/batch` accepts at most 50 `paper_keys`. Use normalized detail fields:

- `display.overview`: publication metadata, profile, classification, mapped references/cited-by;
- `display.algorithm.problem` and `.method`: task, assumptions, objectives, constraints, mechanisms, and updates;
- `display.experiment`: datasets, baselines, evaluations, and limitations;
- `display.proof.statement_cards`: theorem-like statements;
- source Markdown only for final or disputed claims.

Check HTTP status, `result_count`, and `diagnostics`. Agent mode may return HTTP 200 with an unavailable diagnostic. Scores are comparable only within one request and mode.

## Safety invariants

- URL-encode paper keys or use batch JSON bodies.
- Never hardcode Domain IDs across snapshots.
- Preserve `display.provenance` in artifacts.
- Label Domain narrative as candidate scaffolding.
- Prefer paper evidence when Domain and paper disagree.
