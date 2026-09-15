# CPU30 adapter preparation boundary

Read only PUBLIC_TARGETS.json, public/<paper_id>/public_cases.json and assigned original workspace. Do not read TARGETS.json, papers/, paper_reviews/, derivation scripts, prior verdicts or private expected values. The task is faithful input adaptation and observation, not deciding correctness.

Write adapters/<paper_id>/<codex|reasflow>/adapter.py, bindings.json (array of {path,symbol}), environment_actions.json (array), ADAPTER_BASIS.md. Independent review.json will be supplied by another agent.

Adapter reads OPTIREPRO_CASES (public JSON file path) and OPTIREPRO_WORKSPACE. Emits exactly one line:
OPTIREPRO_OBSERVATIONS={"cases":[{"id":"case-id","observations":[{"step":1,"name":"x","value":[1,2]}]}]}
Each case must correspond to a public case. Actual numeric values only, shape and timing as declared. status may be absent/ok/pass/blocked. For unsupported states report blocked with reason and missing_observations, while retaining any actual observations. Missing results cannot be fabricated from a recurrence, interpolation or expected answer. Unknown statuses are invalid.

Call original core algorithms; no copying or repairing updates. Public objective/gradient inputs, initial states, deterministic random realizations and observation wrappers are permitted; record each substitution and the bypassed scope. Prefer the original problem/objective class whenever it can represent the declared public problem; do not replace an existing matching loss/gradient/prox/compressor merely for convenience. If a synthetic objective callback is necessary, explicitly state which original problem-specific functions are bypassed. Original prox, aggregation, compression and quasi-Newton update functions are algorithm mechanisms, not unrestricted problem inputs. Preserve source normalization, dtype, update order, sampler semantics and stopping behavior. Do not quietly override algorithm mechanisms to meet the public experiment. A traced call is not sufficient if its output is ignored and computed separately.

Use sys.settrace if needed to read true locals after statements. Do not override sys.setprofile (outer harness uses it for original-call provenance). Set sys.dont_write_bytecode = True. Workspace is immutable; all setup/logs/temp outputs go outside it. Smoke with public inputs only using the available /tmp/optirepro-paper-judge-20260915/bin/python, and use execution._readonly_tree to protect originals. Do not invoke full Judge or read numeric comparison results during preparation.

Environment actions examples: {"kind":"install_package","package":"numpy","reason":"original source imports numpy","source":"relative/file.py:line"}. Explicit [] is valid if stdlib-only. Add necessary packages based on imports. Do not edit production pipeline.

If the paper-selected original algorithm genuinely does not exist or cannot be invoked without algorithm replacement, record concrete inspected source/function evidence. Prefer partial genuine execution with blocked cases when feasible. Only when no faithful call is possible write status.json {"status":"blocked","reason":"specific source evidence"} and ADAPTER_BASIS.md, instead of making up an adapter. Such cases remain uncovered and cannot pass.

If the source cannot accept the declared initial state, algorithm parameters or solver settings, later source-tuned trajectories are not comparable to that experiment. Put them in diagnostics, retain only genuinely comparable original observations, and report all remaining coordinates missing/blocked. Do not turn different-input executions into algorithm numerical mismatches.

Dependency actions must cover package __init__ imports as well as the direct algorithm file. Public smoke in a pre-populated interpreter does not establish that the fresh execution environment has all required dependencies.
