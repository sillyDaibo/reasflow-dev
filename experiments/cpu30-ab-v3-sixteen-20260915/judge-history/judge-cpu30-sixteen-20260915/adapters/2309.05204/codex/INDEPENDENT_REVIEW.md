# Independent adapter fidelity review

Approved after revision: only the comparable initial gradient is a standard observation; unsupported independent-z0 trajectory remains blocked diagnostics.

Inspected src/pirl1_am/algorithms.py _solve and forward_difference, _shrink, divergence and _prepare_system, plus data.psf2otf/circular_filter. The source has dx/dy=Gx and computes weights from dx/dy each iteration; no independent previous-z state or z0 argument exists. Injecting z0 into weights would replace the original core, which this adapter does not do.

Public u0 is assigned once to freshly initialized x before y and differences. Step 1 gradient_before is copied from native dx and is independent of missing z0. The other 14 native values per case are explicitly in diagnostics, not comparable observations; all corresponding standard observations are missing/blocked.

Centered public K impulse response follows original PSF convention. Source float64, FFT normalization, literal vertical symbol on a one-row image, circular_filter used as source adjoint, native shrink and stopping remain untouched. The diagnostic objective is only a public-loss evaluation on actual native u/z; it feeds no algorithm state.

Readonly public smoke on revised bytes exited 0 with exactly one standard observation per case and blocked status.

Substitutions inspected:
- kernel and initial x: Public circulant matrix encoded via original PSF centering; x buffer alone receives declared u0.
- sys.settrace: Native pre-shrink dx supplies the sole comparable observation; native weights/vx/updated x are diagnostics because z0 is unsupported.
- diagnostic objective: Public loss evaluated on genuine native u/z for diagnostics only; no prox, gradient or iterate update is replaced.

Reviewed actual source functions and public inputs, not just author notes. Public-only readonly smoke exited 0 for both cases; stdout/stderr are in adapter-review-b-smoke/. No numeric private answer comparison or entire Judge invocation occurred. Approval concerns adaptation fidelity only; every reported block remains a coverage limitation. Digests were generated from current actual bytes and validate_adapter_review succeeded.
