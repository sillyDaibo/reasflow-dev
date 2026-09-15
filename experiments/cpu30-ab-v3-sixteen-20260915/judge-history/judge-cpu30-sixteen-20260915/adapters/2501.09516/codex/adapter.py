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
sys.path.insert(0,str(workspace / 'src'))
from manpqn import algorithms as alg
from manpqn.problems import CompressedModes
from manpqn.geometry import project_tangent
class AffineCM(CompressedModes):
    def smooth_value(self,x): return super().smooth_value(x)+float(np.sum(self.c*x))
    def smooth_grad(self,x): return super().smooth_grad(x)+self.c
for case in public['cases']:
    inp,par,obs=case['inputs'],case['parameters'],{}
    Q=np.asarray(inp['Q'],dtype=float);c=np.asarray(inp['linear_c'],dtype=float).reshape(-1,1)
    if np.any(c):
        problem=AffineCM(Q/2,mu=inp['mu']);problem.c=c
    else:
        problem=CompressedModes(Q/2,mu=inp['mu'])
    fn=alg.run_method
    before=line_of(fn,'inner_tol =')
    after=line_of(fn,'history.append(float(value))')
    line_count=[0]
    def trace(frame,event,arg):
        if frame.f_code is fn.__code__ and event=='line':
            loc=frame.f_locals;k=loc.get('iteration')
            if frame.f_lineno==before:
                emit(obs,k,'X_before',loc['x'])
                emit(obs,k,'riemannian_gradient',project_tangent(loc['x'],loc['grad']))
                emit(obs,k,'metric_diagonal',loc['metric'])
                line_count[0]=loc['line_search_steps']
            elif frame.f_lineno==after:
                for name,key in [('V','v'),('line_search_reference','reference'),('alpha','alpha'),('X','x'),('objective','value')]:emit(obs,k,name,loc[key])
                emit(obs,k,'backtracks',loc['line_search_steps']-line_count[0])
        return trace
    previous_trace=sys.gettrace()
    try:
        sys.settrace(trace)
        alg.manpqn(problem,np.asarray(inp['X0'],dtype=float),maxiter=par['iterations'],nonmonotone_window=par['nonmonotone_m'],retraction='svd')
    finally:
        sys.settrace(previous_trace)
    comparable_keys = [(1, 'X_before'), (1, 'riemannian_gradient')]
    native_diagnostics = [value for key, value in obs.items() if key not in comparable_keys]
    obs = {key: value for key, value in obs.items() if key in comparable_keys}
    finish(case,obs,'The native ManPQN stores an inverse-like diagonal secant-ratio scaling, not a full damped BFGS B_matrix or damping_beta, and does not evaluate tangent_metric_norm_squared. The native approximate tangent solve and stopping were preserved; no exact solver substituted.')
    results[-1]['diagnostics'] = {'native_observations': native_diagnostics, 'scope': 'Actual unmodified-source trajectory under native unsupported parameter rules; not comparable observations for the declared public experiment.'}

print('OPTIREPRO_OBSERVATIONS=' + json.dumps({'cases': results}, allow_nan=False))
