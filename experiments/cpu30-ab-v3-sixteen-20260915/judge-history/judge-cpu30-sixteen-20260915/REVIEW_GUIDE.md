# Independent paper review

Review a paper group you did not prepare, with the original PDFs and private contracts only. Do not inspect any workspace, adapter, actual output, previous verdict, or other review. Prefer independently reconstructing the arithmetic from the paper before reading the author's derivation program. Preserve frozen inputs, answers and tolerances unless a paper-grounded issue is explicitly established; no implementation-based changes.

For each assigned paper, independently recompute its complete finite trajectories and check update order, sign, normalization, random realizations, constraints and tolerances. Save a runnable independent recomputation script and numeric error output under paper_reviews/<id>/, plus paper_reviews/<id>.md. Keep scope limitations explicit (paper variants omitted, deterministic conditional sampling, stated paper ambiguities). Do not reject an ambiguity that provably cannot affect the declared returned values; do not approve ambiguous numeric results by guessing.

Write paper_reviews/<id>.json with:
{
 "schema_version":"optirepro.paper_review.v1",
 "contract_digest":"canonical contract_digest(contract)",
 "reviewer_id":"your agent name",
 "basis":"original_paper_only",
 "decision":"approved|needs_revision|unsupported",
 "summary":"concrete reason",
 "cases":[{"case_id":"...","decision":"approved|needs_revision|unsupported","reason":"independent reasoning","citations":["PDF page/eq/algorithm"]}],
 "scope_notes":["finite limitations"]
}
All case IDs exactly once; approved only when all cases approved. Validate using repo_judge/src/judge/review_records.py validate_paper_review. Hashes bind versions, not reviewer honesty. If changes are needed, notify root/author with paper-only evidence; do not change author's contract silently. The author and reviewer must remain separate.
