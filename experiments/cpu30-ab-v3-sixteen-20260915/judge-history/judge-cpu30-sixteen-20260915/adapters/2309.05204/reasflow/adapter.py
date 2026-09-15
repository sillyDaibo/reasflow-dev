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
import pirl1_am as alg
for case in public['cases']:
    inp,par,obs = case['inputs'],case['parameters'],{}
    shape=tuple(inp['image_shape'])
    K=np.asarray(inp['K'],dtype=float)
    kernel=np.roll(K[:,0].reshape(shape),shape[1]//2,axis=1)
    initial=np.asarray(inp['u0'],dtype=float).reshape(shape)
    initialize=line_of(alg._solve,'y = x.copy()')
    before=line_of(alg._solve,'vx =')
    after=line_of(alg._solve,'denominator =' if hasattr(alg,'forward_difference') else 'denom =')
    def trace(frame,event,arg):
        if frame.f_code is alg._solve.__code__ and event=='line':
            loc=frame.f_locals
            if frame.f_lineno==initialize:
                # Exactly one injection into the original freshly allocated initial image.
                loc['x'][...] = initial
            elif frame.f_lineno==before:
                k=loc['iteration']
                emit(obs,k,'gradient_before',loc['dx'].reshape(-1))
                emit(obs,k,'thresholds',loc['weights_x' if 'weights_x' in loc else 'wx'].reshape(-1))
            elif frame.f_lineno==after:
                k=loc['iteration'];u=loc['x'].reshape(-1);z=loc['vx'].reshape(-1)
                emit(obs,k,'u',u);emit(obs,k,'z',z)
                # Read-only evaluation of the declared public objective at actual solver iterates.
                residual=K@u-np.asarray(inp['f']);coupling=z-np.asarray(inp['gradient_matrix'])@u
                value=.5*np.dot(residual,residual)+par['mu']*np.sum(np.abs(z)**par['p'])+.5*par['beta']*np.dot(coupling,coupling)
                emit(obs,k,'objective',value)
        return trace
    previous_trace=sys.gettrace()
    reason='Original state has only dx/dy=G u, with weights recomputed from that gradient; independent public z0 cannot be supplied without replacing the core weighting rule. Native threshold and blur-solve mechanisms remain unchanged.'
    try:
        sys.settrace(trace)
        alg._solve(np.asarray(inp['f']).reshape(shape),kernel,mu=par['mu'],beta=par['beta'],p=par['p'],epsilon=par['epsilon'],max_iter=par['iterations'],tol=1e-8,accelerated=False)
    except Exception as exc:
        reason += ' Original invocation raised '+type(exc).__name__+': '+str(exc)
    finally:
        sys.settrace(previous_trace)
    finish(case,obs,reason)

print('OPTIREPRO_OBSERVATIONS=' + json.dumps({'cases': results}, allow_nan=False))
