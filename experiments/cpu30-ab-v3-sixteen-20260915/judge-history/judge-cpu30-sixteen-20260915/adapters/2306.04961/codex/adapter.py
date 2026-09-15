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
from simirls import algorithms as alg
from simirls.data import MeasurementOperator
for case in public['cases']:
    inp, par, obs = case['inputs'], case['parameters'], {}
    n1, n2 = inp['matrix_shape']
    A = np.asarray(inp['measurement_matrix'], dtype=float)
    permutation = np.arange(n1*n2).reshape(n1,n2).reshape(-1,order='F')
    op = MeasurementOperator(A[:,permutation], n1, n2, 'public')
    mark = line_of(alg.irls_lrrs, 'spectral_grad =')
    def trace(frame,event,arg):
        if frame.f_code is alg.irls_lrrs.__code__ and event == 'line' and frame.f_lineno == mark:
            loc = frame.f_locals; k = loc['iteration']
            for name, key in [('X','x'),('singular_values','singular'),('row_norms','rows'),('epsilon','eps'),('delta','delta'),('row_weight_diagonal','row_w')]:
                emit(obs,k,name,loc[key])
        return trace
    previous_trace = sys.gettrace()
    try:
        sys.settrace(trace)
        alg.irls_lrrs(op, np.asarray(inp['measurements'],dtype=float), par['rank_estimate'], par['row_sparsity_estimate'], max_iter=par['iterations'])
    finally:
        sys.settrace(previous_trace)
    finish(case,obs,'Source forms one-sided spectral_grad and row_w, with rank/row thresholds and projected refinements; no two-sided low-rank factors or fixed weight_operator matrix are formed. Original weights and solver unchanged.')

print('OPTIREPRO_OBSERVATIONS=' + json.dumps({'cases': results}, allow_nan=False))
