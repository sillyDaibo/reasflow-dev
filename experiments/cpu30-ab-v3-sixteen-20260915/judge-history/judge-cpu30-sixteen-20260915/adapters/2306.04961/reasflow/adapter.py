import os, sys, json, inspect
from pathlib import Path
sys.dont_write_bytecode = True
import numpy as np
workspace = Path(os.environ['OPTIREPRO_WORKSPACE'])
public = json.loads(Path(os.environ['OPTIREPRO_CASES']).read_text())
results = []
def emit(obs, step, name, value):
    v = np.asarray(value)
    if np.all(np.isfinite(v)):
        obs[(int(step), name)] = {'step': int(step), 'name': name, 'value': v.tolist()}
def finish(case, obs, reason):
    missing = [{'step': s['step'], 'name': s['name']} for s in case['observation_schema'] if (s['step'], s['name']) not in obs]
    result = {'id': case['id'], 'observations': list(obs.values())}
    if missing or reason:
        result.update(status='blocked', reason=reason or 'Original solver stopped before all requested observations.', missing_observations=missing)
    results.append(result)
def line_of(fn, text):
    lines, start = inspect.getsourcelines(fn)
    return start + next(i for i, line in enumerate(lines) if text in line)
sys.path.insert(0, str(workspace))
from simirls import core as alg
from simirls.core import MeasurementOperator
for case in public['cases']:
    inp, par, obs = case['inputs'], case['parameters'], {}
    n1, n2 = inp['matrix_shape']
    A = np.asarray(inp['measurement_matrix'], dtype=float)
    op = MeasurementOperator(A, n1, n2, 'public')
    mark = line_of(alg.irls_lrrs, 'for _ in range(inner_steps):')
    weight_mark = line_of(alg._weight_apply, 'return low +')
    seen_weights = set()
    def trace(frame,event,arg):
        if event == 'line' and frame.f_code is alg.irls_lrrs.__code__ and frame.f_lineno == mark:
            loc = frame.f_locals; k = loc['iteration'] + 1
            # A loop header repeats; only the first visit still holds this iteration's pre-solve x.
            if (k,'X') not in obs:
                for name,key in [('X','x'),('singular_values','singular'),('row_norms','rows'),('epsilon','eps'),('delta','delta')]:
                    emit(obs,k,name,loc[key])
        if event == 'line' and frame.f_code is alg._weight_apply.__code__ and frame.f_lineno == weight_mark:
            parent = frame.f_back
            if parent.f_code is alg.irls_lrrs.__code__:
                k = parent.f_locals['iteration']+1
                if k not in seen_weights:
                    seen_weights.add(k);loc=frame.f_locals
                    for name,key in [('low_rank_left','left'),('low_rank_right','right'),('row_weight_diagonal','row_w')]:
                        if key in loc: emit(obs,k,name,loc[key])
        return trace
    previous_trace = sys.gettrace()
    try:
        sys.settrace(trace)
        alg.irls_lrrs(op, np.asarray(inp['measurements'],dtype=float), par['rank_estimate'], par['row_sparsity_estimate'], max_iter=par['iterations'])
    finally:
        sys.settrace(previous_trace)
    finish(case,obs,'Source _weight_apply recomputes row_w from its argument on every inner step, so it is nonlinear and has no fixed linear weight_operator matrix. No basis-probing/reimplementation was used to invent that matrix.')

print('OPTIREPRO_OBSERVATIONS=' + json.dumps({'cases': results}, allow_nan=False))
