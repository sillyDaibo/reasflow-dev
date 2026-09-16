import sys, os, json, importlib.util
sys.dont_write_bytecode = True
import numpy as np
from pathlib import Path
W = Path(os.environ['OPTIREPRO_WORKSPACE'])
spec = importlib.util.spec_from_file_location('original_algorithm', W / 'src/algorithms.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
def solve(case):
    inp, par = case['inputs'], case['parameters']
    n, agents = inp['samples_per_agent'], inp['agents']
    before, gradients, endpoints, consensus, after = [], [], [], [], []
    class RNG:
        calls = 0
        def permutation(self, size):
            k = self.calls // agents
            self.calls += 1
            return np.array(inp['permutations'][k], dtype=int)
    old_rng = m.np.random.default_rng
    m.np.random.default_rng = lambda *a, **k: RNG()
    initial = np.array(inp['x_initial'], dtype=float)
    old_grad, old_mix, old_prox = m._sample_gradient, m._mix, m._soft_threshold
    def gradient(x, y, w):
        before.append(w.copy())
        g = old_grad(x, y, w)
        gradients.append(g.copy())
        return g
    def mix(q, *a):
        endpoints.append(q.copy().T)
        v = old_mix(q, *a)
        consensus.append(v.copy().ravel())
        return v
    def prox(v, threshold):
        z = old_prox(v, threshold)
        after.append(z.copy().ravel())
        return z
    m._sample_gradient, m._mix, m._soft_threshold = gradient, mix, prox
    def trace(frame, event, arg):
        if frame.f_code is m.run_method.__code__ and event == 'line' and frame.f_lineno == 80:
            frame.f_locals['x_agents'][:] = initial[None, :]
        return trace
    X = np.array(inp['signed_features'], dtype=float).reshape(-1, 1)
    try:
        sys.settrace(trace)
        m.run_method('dpg_rr', 'public', X, np.ones(len(X)), X, np.ones(len(X)),
                     [np.array(inp['mixing_matrices'][0])], epochs=par['epochs'], agents=agents,
                     lam=par['regularizer_strength'], step_size=par['gamma'])
    finally:
        sys.settrace(None)
        m.np.random.default_rng = old_rng
        m._sample_gradient, m._mix, m._soft_threshold = old_grad, old_mix, old_prox
    rows=[]
    pre=np.array(before).reshape(par['epochs'],agents,n).transpose(0,2,1)
    grads=np.array(gradients).reshape(par['epochs'],agents,n).transpose(0,2,1)
    for t in range(par['epochs']):
        vals={'inner_x':np.vstack([pre[t], np.array(endpoints[t]).ravel()]),
              'inner_gradient':grads[t], 'consensus_v':consensus[t], 'x_next':after[t]}
        rows.extend({'step':t+1,'name':key,'value':np.asarray(val).tolist()} for key,val in vals.items())
    return {'id':case['id'],'observations':rows}
print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':[solve(c) for c in json.load(open(os.environ['OPTIREPRO_CASES']))['cases']]}))
