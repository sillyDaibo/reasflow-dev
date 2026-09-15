import sys, os, json, importlib.util
sys.dont_write_bytecode = True
import numpy as np
from pathlib import Path
W = Path(os.environ['OPTIREPRO_WORKSPACE'])
spec = importlib.util.spec_from_file_location('original_algorithm', W / 'src/disprox_rr/algorithms.py')
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
    old_grad, old_local, old_prox = m.logistic_gradient, m._local_stochastic_epoch, m._prox_consensus
    def gradient(X, y, x):
        g = old_grad(X, y, x)
        if sys._getframe(1).f_code is old_local.__code__:
            before.append(x.copy())
            gradients.append(g.copy())
        return g
    def local(*args):
        result = old_local(*args)
        endpoints.append(result[0].copy())
        return result
    old_l1 = m._prox_l1
    def l1(v, *args):
        consensus.append(v.copy())
        return old_l1(v, *args)
    def prox(*args):
        z = old_prox(*args)
        after.append(z.copy().ravel())
        return z
    m.logistic_gradient, m._local_stochastic_epoch, m._prox_consensus, m._prox_l1 = gradient, local, prox, l1
    def trace(frame, event, arg):
        if frame.f_code is m.run_method.__code__ and event == 'line' and frame.f_lineno == 157:
            frame.f_locals['x'][:] = initial[:, None]
        return trace
    X = np.array(inp['signed_features'], dtype=float)[:, :, None]
    A = np.array(inp['mixing_matrices'][0])
    try:
        sys.settrace(trace)
        m.run_method('DPG-RR', X, np.ones(X.shape[:2]), A, A[None, :, :], epochs=par['epochs'],
                     gamma=par['gamma'], l1=par['regularizer_strength'], batch_size=1)
    finally:
        sys.settrace(None)
        m.np.random.default_rng = old_rng
        m.logistic_gradient, m._local_stochastic_epoch, m._prox_consensus, m._prox_l1 = old_grad, old_local, old_prox, old_l1
    consensus = np.array(consensus).reshape(par['epochs'], agents)
    rows=[]
    pre=np.array(before).reshape(par['epochs'],agents,n).transpose(0,2,1)
    grads=np.array(gradients).reshape(par['epochs'],agents,n).transpose(0,2,1)
    for t in range(par['epochs']):
        vals={'inner_x':np.vstack([pre[t], np.array(endpoints[t]).ravel()]),
              'inner_gradient':grads[t], 'consensus_v':consensus[t], 'x_next':after[t]}
        rows.extend({'step':t+1,'name':key,'value':np.asarray(val).tolist()} for key,val in vals.items())
    return {'id':case['id'],'observations':rows}
print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':[solve(c) for c in json.load(open(os.environ['OPTIREPRO_CASES']))['cases']]}))
