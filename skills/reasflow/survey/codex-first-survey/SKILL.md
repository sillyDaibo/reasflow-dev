---
name: codex-first-survey
description: Research and write a full academic survey or related-work section with Codex as the single owner, using compact evidence tools and deterministic publication checks instead of staged drafting agents.
---

# Minimal ReasFlow augmentation

Keep Codex in charge of the research plan, outline, prose, and revisions. Do
not impose a staged workflow or convert tool output into section headings.
Native web search is the default discovery path. Do not construct a candidate
pool or bibliography first. Research and draft in Codex's native order, then
apply identity and metadata checks only to works that the manuscript actually
selects or cites.

Use ReasFlow only for three measured weaknesses of an unaided long-form run:

1. canonical paper identity and bibliography metadata;
2. selective paper or citation-neighbor evidence when a claim cannot be
   resolved confidently from the web;
3. deterministic TeX, citation-key, duplicate, and PDF validation.

Resolve the helper root only when one of those needs occurs:

```bash
SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/codex-first-survey"
```

The optional `merge`, `shortlist`, `inspect`, `enrich-metadata`, `validate-doi`,
and `bibtex` commands live in
`$SKILL_ROOT/scripts/codex_first_tools.py`. Read their `--help` instead of
loading an entire candidate pool. The Semantic Scholar helper is under
`survey/autosurvey-paper-retrieval`; use it for a focused metadata, reference,
or citation query, not as a substitute for native research.

Before delivery, check every sentence that names an originator, first method,
or historical foundation. Its attached citation must contain the named author
and represent the original work. If the original cannot be verified, rewrite
the sentence as a qualified secondary account. This check is deliberately
narrow: it must not prescribe the taxonomy, historical narrative, gap list, or
future-work agenda.

Write the manuscripts directly in LaTeX, share one bibliography, then run:

```bash
python3 "$REASFLOW_PRIVATE_SKILLS_ROOT/survey/survey-tex-bib-packaging/scripts/build_publication.py" --workspace .
```

Inspect both PDFs. Repair only observed evidence, metadata, compilation,
duplicate, citation-key, formula, or layout failures. Keep internal retrieval
records and audit language out of the article.
