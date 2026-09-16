# Independent public/source-only adapter review

Original APDG hardcodes spectral tuning, including sigma_y=1; no parameter interface can express the public tuple. Revised adapter properly reports all standard observations missing/blocked and separates the real source-tuned trajectory into diagnostics.

- Inspected apdg and model objective/gradient/A operators directly. Public-only readonly smoke completed both cases; no numeric comparison.
- Initial x/fast-x and y/fast-y/previous-y are injected once before the loop; later states are only observed. Native float dtype, update order and stopping branches retained.
- The regenerated problem objective differs only by residual expansion constant; measured public objective at true x has that irrelevant constant removed. Cached constructor optimum is diagnostic-only and is not a stopping criterion.
- Challenged unsupported claim: apdg signature only accepts problem,max_iter,tolerance, directly calls spectral_constants, and fixes sigma_y=1. Altering spectral constants cannot realize public sigma_y=.9. Standard observations empty with every public schema item in missing_observations. Actual differing-parameter states are diagnostics only, not judged observations.

Substitution audit:
- SyntheticProblem data fields (problem_input): Public quadratic coefficients and constraints replace generated objective/linear-map data; original gradient executes.
- sys.settrace initialization (problem_input): Writes only the initial states required by public inputs.
- sys.settrace snapshots and public objective (observation): Copies source local arrays after updates; evaluates declared objective at actual x without manufacturing a trajectory.
- diagnostics (observation): Actual native source-tuned observations are excluded from standard observations because requested parameters cannot be supplied.

Reviewed bytes: e0c5564cf805511473cc5ac6051fa19cdbf90cbf80a31d6f2afe8ba9b0d4b3ec
Workspace digest: 2fab8b5886eaef44557c4feda677246a3f7caa4d50ba9c53ceac59128498c16e
No papers, private answers, derivations, historical reviews, or numerical Judge results were read. Approval concerns adaptation fidelity, not algorithm correctness.
