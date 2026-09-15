# Independent public/source-only adapter review

Original APDG uses supplied native params; public quadratic gradient and rank-deficient constraint embedding retain original core methods and exact source states.

- Inspected apdg and model objective/gradient/A operators directly. Public-only readonly smoke completed both cases; no numeric comparison.
- Initial x/fast-x and y/fast-y/previous-y are injected once before the loop; later states are only observed. Native float dtype, update order and stopping branches retained.
- The regenerated problem objective differs only by residual expansion constant; measured public objective at true x has that irrelevant constant removed. Cached constructor optimum is diagnostic-only and is not a stopping criterion.
- B is embedded with a zero redundant row per node; dual indices [0,2,4,5,6,7] preserve A, A^T, ATA and AAT. All public parameters pass through the native params interface.

Substitution audit:
- QuadraticProblem data fields (problem_input): Public quadratic coefficients and constraints replace generated objective/linear-map data; original gradient executes.
- sys.settrace initialization (problem_input): Writes only the initial states required by public inputs.
- sys.settrace snapshots and public objective (observation): Copies source local arrays after updates; evaluates declared objective at actual x without manufacturing a trajectory.
- dual coordinate embedding/projection (problem_input): Redundant zero constraint rows preserve original square-B operator protocol.

Reviewed bytes: 782b9eddf550ca1c2a7aae1ac64cc641357a517490fb820cdf1f8aec4c858ebf
Workspace digest: c8f546b44d94678ba6d16553c80b73e8ac7a5e263fb91b20e81dc0e88035c2c9
No papers, private answers, derivations, historical reviews, or numerical Judge results were read. Approval concerns adaptation fidelity, not algorithm correctness.
