#!/usr/bin/env python3
"""Public-input-only adapter. Executes original drivers and observes their states.
No paper expectations are read, and no optimization update is implemented here.
"""
import contextlib
import inspect
import json
import os
from pathlib import Path
import sys
import numpy as np

KIND = 'codex'
sys.dont_write_bytecode = True
WORKSPACE = Path(os.environ['OPTIREPRO_WORKSPACE']).resolve()
sys.path.insert(0, str(WORKSPACE))

if KIND == 'codex':
    from rr_prox_fed import algorithms as methods, objectives as losses
else:
    from rr_prox_fed import methods, losses
from rr_prox_fed import federated


class Permutations:
    """Only randomness is replaced: exactly the publicly specified realizations."""
    def __init__(self, orders):
        self.orders = iter(orders)
        self.used = 0
    def permutation(self, values):
        order = np.asarray(next(self.orders), dtype=int)
        original = np.arange(values) if np.isscalar(values) else np.asarray(values)
        if sorted(order.tolist()) != sorted(original.tolist()):
            raise ValueError('Public permutation cannot represent requested source input')
        self.used += 1
        return order.copy()


@contextlib.contextmanager
def patch(obj, name, replacement):
    old = getattr(obj, name)
    setattr(obj, name, replacement)
    try: yield
    finally: setattr(obj, name, old)


class QuadraticInput:
    """Synthetic objective input only; original driver owns every state update."""
    def __init__(self, diagonals, centers, l1, l2):
        self.diagonals = np.asarray(diagonals, float)
        self.centers = np.asarray(centers, float)
        self.n, self.dim = self.diagonals.shape
        self.l1, self.l2 = l1, l2
        if KIND == 'codex':
            self.regularizer = losses.ProximalOperator(l1, l2)
    def gradient(self, x, idx=None, normalization=None, sample_weights=None):
        idx = np.arange(self.n) if idx is None else np.asarray(idx, int)
        gradients = self.diagonals[idx] * (x-self.centers[idx])
        if sample_weights is not None:
            gradients = gradients * np.asarray(sample_weights)[:,None]
        return gradients.sum(axis=0)/(len(idx) if normalization is None else normalization)
    def gradient_batch(self, x, idx=None, normalize=True):
        idx = np.arange(self.n) if idx is None else np.asarray(idx, int)
        return self.gradient(x, idx, normalization=(len(idx) if normalize else 1))
    def value(self, x):
        # This is unobserved logging requested by the original driver's API.
        return float(.5*np.sum(self.diagonals*(x-self.centers)**2)/self.n + self.l1*np.sum(abs(x)) + .5*self.l2*np.dot(x,x))


def logistic_input(inp, par):
    cls = losses.ElasticNetLogistic if KIND == 'codex' else losses.LogisticElasticNet
    return cls(np.asarray(inp['features'],float), np.asarray(inp['labels'],float), l1=par['lambda1'], l2=par['lambda2'])


class Capture:
    """Record state immediately after selected original statements execute.
    settrace is independent of setprofile used by the surrounding provenance harness.
    """
    def __init__(self, func, mode, epoch=None):
        self.code = func.__code__
        source, start = inspect.getsourcelines(func)
        self.lines = {start+i: line.strip() for i,line in enumerate(source)}
        self.previous = None
        self.mode, self.epoch = mode, epoch
        self.inner = []
        self.first, self.endpoints = {}, {}
        self.observations = []
        self.client_sample_count = 0
    def emit(self, step, name, value):
        self.observations.append(dict(step=step,name=name,value=np.asarray(value,float).tolist()))
    def trace(self, frame, event, arg):
        if frame.f_code is not self.code:
            return self.trace
        if event in ('line','return'):
            statement = self.lines.get(self.previous,'')
            v = frame.f_locals
            if self.mode == 'prox':
                if statement.startswith('x -= '):
                    self.inner.append(v['x'].copy())
                if statement.startswith('x = self.objective.regularizer(') or statement.startswith('x = elastic_net_prox('):
                    self.emit(self.epoch, 'inner_iterates', self.inner)
                    self.emit(self.epoch, 'iterate', v['x'])
            else:
                step = v.get('epoch',-1)+1 if KIND == 'codex' else v.get('rnd')
                if statement.startswith('z -= '):
                    if self.client_sample_count == 0:
                        self.first.setdefault(step,[]).append(v['z'].copy())
                    self.client_sample_count += 1
                if statement == 'local_models.append(z)':
                    self.endpoints.setdefault(step,[]).append(v['z'].copy())
                    self.client_sample_count = 0
                if statement == 'x = np.mean(local_models, axis=0)':
                    self.emit(step, 'local_after_first_sample', self.first[step])
                    self.emit(step, 'local_endpoints', self.endpoints[step])
                    self.emit(step, 'aggregate', v['x'])
                if statement.startswith('x /= ') or statement.startswith('x = elastic_net_prox('):
                    self.emit(step, 'iterate', v['x'])
            self.previous = frame.f_lineno if event == 'line' else None
        return self.trace
    def __enter__(self):
        self.old = sys.gettrace()
        sys.settrace(self.trace)
        return self
    def __exit__(self, *args):
        sys.settrace(self.old)


def proximal(case, observations):
    inp, par = case['inputs'], case['parameters']
    objective = (QuadraticInput(inp['diagonals'], inp['centers'], par['lambda1'], par['lambda2'])
                 if 'diagonals' in inp else logistic_input(inp,par))
    x = np.asarray(inp['x0'],float)
    # The driver has a constant-rate epoch API. Supply each public epoch's gamma
    # through that API and carry only its returned iterate into the next x0.
    # This never reimplements inner updates, regularization or averaging.
    for epoch, (gamma,order) in enumerate(zip(par['epoch_stepsizes'],inp['epoch_sample_orders']),1):
        rng = Permutations([order])
        with patch(np.random,'default_rng',lambda *a,**kw:rng):
            if KIND == 'codex':
                driver = methods.ProxRR(objective, epochs=1, step_size=gamma, batch_size=1)
                capture = Capture(methods.ProxRR.run,'prox',epoch)
                with capture:
                    x,_ = driver.run(x0=x)
            else:
                capture = Capture(methods.prox_rr,'prox',epoch)
                with capture:
                    result = methods.prox_rr(objective,epochs=1,gamma=gamma,x0=x)
                x = result['x']
        observations.extend(capture.observations)
        if rng.used != 1:
            raise RuntimeError('Original epoch did not consume the prescribed permutation exactly once')


def federation(case, observations):
    inp, par = case['inputs'], case['parameters']
    diagonals = [np.asarray(x,float) for x in inp['client_diagonals']]
    centers = [np.asarray(x,float) for x in inp['client_centers']]
    # Public diagonals serve as API data containers with exactly the requested
    # node sample counts. The factory installs the prescribed synthetic loss.
    workers = [(d,np.zeros(len(d))) for d in diagonals]
    def local_factory(A,b,l1=0.,l2=0.,**kwargs):
        client = next(i for i,d in enumerate(diagonals) if A is d)
        return QuadraticInput(diagonals[client],centers[client],l1,l2)
    orders = [order for epoch in inp['epoch_client_sample_orders'] for order in epoch]
    rng = Permutations(orders)
    if KIND == 'codex':
        driver = federated.FedRR(workers,epochs=par['epochs'],step_size=par['stepsize'],l1=par['lambda1'],l2=par['lambda2'],local_batch_size=1)
        capture = Capture(federated.FedRR.run,'fed')
        with patch(federated,'_client_objective',local_factory), patch(np.random,'default_rng',lambda *a,**kw:rng), capture:
            driver.run(x0=inp['x0'])
    else:
        # The public global loss is only used for dimension/coefficient metadata
        # and unobserved value logging; original local construction is intercepted.
        global_loss = QuadraticInput(np.concatenate(diagonals),np.concatenate(centers),par['lambda1'],par['lambda2'])
        global_loss.A = np.concatenate(diagonals)
        global_loss.b = np.zeros(par['N'])
        capture = Capture(federated._run,'fed')
        with patch(federated,'_partition',lambda *a,**kw:workers), patch(federated,'LogisticElasticNet',local_factory), patch(np.random,'default_rng',lambda *a,**kw:rng), capture:
            federated.fed_rr(global_loss,workers_count=par['M'],rounds=par['epochs'],gamma=par['stepsize'],local_steps=par['n'],x0=inp['x0'])
    observations.extend(capture.observations)
    if rng.used != par['epochs']*par['M']:
        raise RuntimeError('Original driver did not consume all client permutations')


def main():
    public = json.loads(Path(os.environ['OPTIREPRO_CASES']).read_text())
    cases = public['cases'] if isinstance(public,dict) else public
    output=[]
    for case in cases:
        observations=[]
        row=dict(id=case['id'],observations=observations)
        try:
            if case['parameters']['algorithm']=='ProxRR': proximal(case,observations)
            elif case['parameters']['algorithm']=='FedRR': federation(case,observations)
            else: raise ValueError('Unsupported public algorithm')
        except Exception as exc:
            row.update(status='blocked',reason=f'{type(exc).__name__}: {exc}')
        required={(r['step'],r['name']) for r in case['observation_schema']}
        got={(r['step'],r['name']) for r in observations}
        missing=required-got
        if missing:
            row.setdefault('status','blocked')
            row.setdefault('reason','Original driver did not expose every required state')
            row['missing_observations']=[dict(step=s,name=n) for s,n in sorted(missing)]
        output.append(row)
    print('OPTIREPRO_OBSERVATIONS='+json.dumps(dict(cases=output),allow_nan=False,separators=(',',':')))

if __name__=='__main__': main()
