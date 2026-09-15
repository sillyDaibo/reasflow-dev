# Independent adapter fidelity review

Approved as a faithful blocked invocation: native one-row image support fails before iteration; no state is fabricated.

Inspected src/pirl1_am.py _prepare_system: dy_kernel has shape (1,3), and dy_kernel[:2,0]=(1.0,-1.0) writes two elements into a length-one view. Both public cases therefore raise ValueError before x initialization, as confirmed by readonly smoke; zero observations are retained.

Public shape (1,3), f, centered impulse response kernel, mu/beta/p/epsilon and iteration cap enter native _solve. Native FFT normalization, thresholding and stopping are unmodified. The public independent z0 has no source state or argument: dx/dy=Gx directly form the weights. No z0-based reweighting is synthesized.

The initial x hook would set u0 before native y/difference creation but is never reached due to the shape failure. Direct _solve access exposes epsilon without editing the wrapper or algorithm.

Substitutions inspected:
- kernel from public K: Centered impulse-response representation follows original psf2otf roll convention; no source adjoint/denominator replacement.
- initial x buffer: Declared u0 injection before y/difference initialization; unreachable for these public one-row cases.
- sys.settrace/exception record: Preserves the original invocation failure and all missing observations; no synthetic algorithm outputs.

Reviewed actual source functions and public inputs, not just author notes. Public-only readonly smoke exited 0 for both cases; stdout/stderr are in adapter-review-b-smoke/. No numeric private answer comparison or entire Judge invocation occurred. Approval concerns adaptation fidelity only; every reported block remains a coverage limitation. Digests were generated from current actual bytes and validate_adapter_review succeeded.
