# 2309.05204 / reasflow
Uses only permitted public inputs and original source. Calls `src/pirl1_am.py:_solve` (directly because the public wrapper does not expose epsilon), unaccelerated, with original default tolerance and public iteration cap. Float64, FFT normalization, source stopping, weighting, shrinkage, and linear-system solve are retained.

The public circulant K is encoded as its impulse response K[:,0], rolled into the original PSF center convention. No data adjoint or spectral denominator is replaced. The single initial-state hook changes only the original x buffer before y and differences are initialized, thereby supplying public u0 separately from data f. The source does not have a separate previous-z state: dx/dy are G u and directly feed both weights and shrinkage. z0 is therefore explicitly unsupported; it is never used to repair the weights. This is a blocked public contract, not an assertion that the source is uncallable.

Observations are read-only locals: dx before shrink, weights_x/wx, vx after shrink, and x after the original FFT solve. Objective is a read-only evaluation of the public problem on those actual u/z values; it does not feed back into the solver. No independent recurrence, prox or update is implemented.

On the exact public (1,3) image, _prepare_system assigns (1.0,-1.0) to dy_kernel[:2,0], a length-one target, and raises ValueError before the optimizer initializes x. The adapter retains that failure and all missing observations; it does not enlarge the public image or repair the denominator. The original _solve call still occurs and is declared as binding.

