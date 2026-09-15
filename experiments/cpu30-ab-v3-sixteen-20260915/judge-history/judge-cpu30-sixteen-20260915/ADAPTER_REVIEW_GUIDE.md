# Independent adapter review

Audit adapters for a paper group you did not prepare. You may read ADAPTER_GUIDE.md, PUBLIC_TARGETS.json, public/<id>/public_cases.json, the assigned adapters and original workspaces. Do not read papers/, paper_reviews/, TARGETS.json, numerical Judge comparisons, old verdicts or private expected answers.

Inspect original source, not just the author's notes. Verify each public input maps faithfully, true observation timing, original core function calls and all substitutions. Original matching objective/prox/compressor/aggregation functions should be used. Synthetic problem callbacks require explicit scope; they must not repair algorithm updates or bypass the mechanism claimed under test. Preserve dtype, normalization, stopping, random call consumption and conditional branches. Check unsupported claims against actual source; don't rubber-stamp blocked when an original interface exists. Never rewrite a missing output from paper formulas or aggregate observed states to fabricate an algorithm output that source never produced.

For ready adapters save adapters/<id>/<variant>/review.json and INDEPENDENT_REVIEW.md. Record:
{
 "schema_version":"optirepro.adapter_review.v1",
 "reviewer_id":"your agent name",
 "basis":"public_inputs_and_source_only",
 "decision":"approved|needs_revision|unsupported",
 "summary":"concrete source-based finding",
 "scope_notes":["all coverage limitations"],
 "substitutions":[{"symbol":"...","role":"problem_input|observation|algorithm_replacement","reason":"..."}],
 "public_digest":"canonical json_digest(public)",
 "adapter_sha256":"sha256 actual adapter.py bytes",
 "workspace_digest":"execution._snapshot_digest(execution._workspace_snapshot(workspace))",
 "bindings_digest":"json_digest(bindings with normalized repository-relative paths)"
}
Use validate_adapter_review in repo_judge/src/judge/review_records.py. An approved review cannot contain algorithm_replacement. Approval is adaptation fidelity only, not algorithm correctness. If code changes after review, hashes must be rechecked with a new actual review.

For an author-declared wholly blocked status.json, independently inspect the evidence and save BLOCKED_REVIEW.md plus status_review.json {decision,reviewer_id,reason,workspace_digest,status_sha256,public_digest}. Do not invent adapter code or approve nonexistent execution. If the block is unsound, return needs_revision and tell the author/root exactly which source interface supports it.

Do not edit another author's adapter silently. Send concrete source/public-input fixes to author/root, then re-audit corrected bytes. No private numeric comparisons or external API calls. Public-input smoke runs are allowed under original-workspace read-only protection, with outputs only in your report directory.
