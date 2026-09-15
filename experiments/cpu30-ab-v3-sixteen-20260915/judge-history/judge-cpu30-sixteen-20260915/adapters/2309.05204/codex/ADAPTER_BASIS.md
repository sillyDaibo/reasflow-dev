# 2309.05204 / codex
Uses only permitted public inputs and original source. Calls `src/pirl1_am/algorithms.py:_solve` (via pirl1_am), unaccelerated, with original default tolerance and public iteration cap. Float64, FFT normalization, source stopping, weighting, shrinkage, and linear-system solve are retained.

The public circulant K is encoded as its impulse response K[:,0], rolled into the original PSF center convention. No data adjoint or spectral denominator is replaced. The single initial-state hook changes only the original x buffer before y and differences are initialized, thereby supplying public u0 separately from data f. The source does not have a separate previous-z state: dx/dy are G u and directly feed both weights and shrinkage. z0 is therefore explicitly unsupported; it is never used to repair the weights. This is a blocked public contract, not an assertion that the source is uncallable.

Observations are read-only locals: dx before shrink, weights_x/wx, vx after shrink, and x after the original FFT solve. Objective is a read-only evaluation of the public problem on those actual u/z values; it does not feed back into the solver. No independent recurrence, prox or update is implemented.

The source circular_filter is used unchanged even though _solve labels its output adjoint_observed, and _prepare_system uses its literal vertical Fourier symbol on the one-row image. These are not silently repaired.


Independent-review scope correction: only initial observations independent of the unsupported public parameter survive in observations: [(1, 'gradient_before')]. All later genuinely observed native-source states are retained under diagnostics.native_observations, and their required public fields are marked missing. Native trajectory is neither deleted nor presented as a realization of unsupported z0/B0/delta/exact-inner settings. This is an interface/coverage block, not a numeric correctness verdict.
