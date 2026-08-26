# Controlled retrieval profile contract

Use these profiles for paired generation/evaluation. Hold the exact topic, cutoff, shared S2 query family, S2 paper-search count, per-query result limit, writer prompt, model, and evaluation task constant. ReaScholar is an additive information treatment, so report its extra Domain/search calls separately instead of pretending the total provider-call count is equal.

## `reascholar-s2`

- Discover eight candidate L2 domains.
- Select two to five domains automatically or by recorded manual IDs.
- Read their normalized Domain pages.
- Run the same four Semantic Scholar paper-search queries as the `s2-only` arm. This is the invariant evidence core.
- Add three Domain-filtered ReaScholar searches; never substitute them for or suppress the S2 core.
- Add mapped Domain support/anchor papers, then batch-fetch normalized paper details.
- Expose Domain narrative only as provisional outline scaffolding.

## `s2-only`

- Make no ReaScholar requests.
- Spend all four paper-search queries in Semantic Scholar.
- Produce an empty Domain scaffold with an explicit `not_available_in_profile` reason.
- Use the same normalization and output filenames.

## Reporting

Report, at minimum:

- retrieval profile and database snapshot/time;
- selected Domain IDs/titles for the assisted arm;
- successful/failed query counts and unique papers;
- shared S2 query count, additive ReaScholar query count, and every later targeted/direct lookup;
- legacy 100-point total plus per-metric deltas;
- semantic shadow total plus lineage, important-work, gap, and future-work deltas when calibrated semantic judgments exist;
- whether the comparison is paired and controlled;
- limitations such as API drift, missing S2 credentials, different model runs, or uncalibrated semantic specs.

Do not call historical outputs from different models or dates a controlled A/B result. Label them observational.
