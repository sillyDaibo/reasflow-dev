"""Public-input adapter; calls original complete ADMM and reads frame-local states.
No paper/private expected values, ADMM replacement, solver changes or source edits.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

VARIANT = 'reasflow'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_original(workspace):
    package_name = '_optirepro_original_strat_' + VARIANT
    package = types.ModuleType(package_name)
    package.__path__ = [str(workspace / 'strat_models')]
    sys.modules[package_name] = package
    root = workspace / 'strat_models'
    if VARIANT == 'codex':
        graph = load_module(package_name + '.graph', root / 'graph.py')
        solver = load_module(package_name + '.solvers', root / 'solvers.py')
        return {'solver': solver, 'graph': graph, 'fn': solver.fit_admm,
                'anchor': 'primal = np.linalg.norm(np.concatenate((r1, r2)))',
                'mapping': {'theta':'theta', 'theta_tilde':'v', 'theta_hat':'z', 'u':'u', 'u_tilde':'w'}}
    fit = load_module(package_name + '.fit', root / 'fit.py')
    losses = load_module(package_name + '.losses', root / 'losses.py')
    regularizers = load_module(package_name + '.regularizers', root / 'regularizers.py')
    return {'solver': fit, 'losses': losses, 'regularizers': regularizers, 'fn': fit.fit_stratified_model,
            'anchor': 'primal_norm = float(np.linalg.norm(primal))',
            'mapping': {name:name for name in ['theta','theta_tilde','theta_hat','u','u_tilde']}}


def input_callbacks(case, original, np):
    loss = case['inputs']['loss']
    reg = case['inputs']['regularizer']
    if loss['type'] == 'quadratic':
        # Exact representation of the PUBLIC quadratic in the existing sum-squares
        # proximal interface; this prepares objective data, not algorithm iterates.
        xtx = np.asarray(loss['Q'], dtype=float) / 2
        xty = -np.asarray(loss['b'], dtype=float) / 2
        if VARIANT == 'codex':
            def loss_prox(t, nu, warm):
                return original['solver'].ridge_prox(t, nu, warm, (xtx, xty))
        else:
            model = original['losses'].sum_squares_loss(intercept=False)
            cache = {'XtX':xtx, 'XtY':xty, 'n':int(case['parameters']['parameter_dimension'])}
            def loss_prox(t, nu, warm, pool=None):
                return model.prox(t, nu, warm, pool, cache)
    elif loss['type'] == 'poisson':
        n = np.asarray(loss['counts'], dtype=float)
        s = np.asarray(loss['sums'], dtype=float)
        if VARIANT == 'codex':
            stats = np.stack((n,s),axis=-1)
            def loss_prox(t, nu, warm):
                return original['solver'].poisson_prox(t, nu, warm, stats)
        else:
            model = original['losses'].poisson_loss()
            cache = {'N':n, 'S':s}
            def loss_prox(t, nu, warm, pool=None):
                return model.prox(t, nu, warm, pool, cache)
    else:
        raise ValueError('Unsupported public loss type: '+str(loss['type']))
    coefficient = float(reg['coefficient'])
    if VARIANT == 'codex':
        if reg['type'] == 'ridge':
            def reg_prox(t, nu, warm):
                return original['solver'].ridge_regularizer_prox(t, nu, warm, lambd=coefficient, intercept_index=None)
        elif reg['type'] == 'l1':
            # This source has no L1 primitive. A public problem-input prox callback
            # is permitted; only this primitive is adapter-defined, never ADMM.
            def reg_prox(t, nu, warm):
                return np.sign(nu) * np.maximum(np.abs(nu)-t*coefficient,0.0)
        else:
            raise ValueError('Unsupported public regularizer type: '+str(reg['type']))
    else:
        if reg['type'] == 'ridge': model_reg=original['regularizers'].sum_squares_reg(lambd=coefficient)
        elif reg['type'] == 'l1': model_reg=original['regularizers'].L1_reg(lambd=coefficient)
        else: raise ValueError('Unsupported public regularizer type: '+str(reg['type']))
        reg_prox=model_reg.prox
    return loss_prox,reg_prox


def run_case(case, original, np):
    fn=original['fn']
    path=Path(fn.__code__.co_filename)
    matches=[i for i,line in enumerate(path.read_text().splitlines(),1) if line.strip()==original['anchor']]
    if len(matches)!=1:
        raise RuntimeError('Cannot locate unique read-only post-dual trace point')
    anchor_line=matches[0]
    requested={(entry['step'],entry['name']):entry['shape'] for entry in case['observation_schema']}
    captured={}
    def tracer(frame,event,arg):
        if frame.f_code is not fn.__code__:
            return None
        if event=='line' and frame.f_lineno==anchor_line:
            step=int(frame.f_locals['iteration'])
            for public_name,local_name in original['mapping'].items():
                key=(step,public_name)
                if key in requested:
                    value=np.array(frame.f_locals[local_name],dtype=float,copy=True)
                    if list(value.shape)!=requested[key]:
                        raise RuntimeError('Original state shape differs from public observation: '+str(key))
                    if not np.isfinite(value).all():
                        raise RuntimeError('Nonfinite original state: '+str(key))
                    captured[key]=value.tolist()
        return tracer
    loss_prox,reg_prox=input_callbacks(case,original,np)
    from scipy import sparse
    lap=sparse.csr_matrix(case['inputs']['L'],dtype=float)
    rho=1.0/float(case['parameters']['lambda'])
    iterations=int(case['parameters']['iterations'])
    shape=(int(case['parameters']['parameter_dimension']),)
    common={'maxiter':iterations, 'rho':rho, 'abs_tol':0.0, 'rel_tol':0.0, 'verbose':False}
    # Use existing constructor/API only. Supplied L is preserved byte-for-value;
    # no graph weight inference or consensus-system assembly occurs in the adapter.
    if VARIANT=='codex':
        from scipy.sparse.linalg import aslinearoperator
        graph=original['graph'].GraphOperator(list(range(lap.shape[0])),lap,aslinearoperator(lap),lap.diagonal())
        args=(graph,shape,loss_prox,reg_prox)
        kwargs=common
    else:
        args=(lap,shape,loss_prox,reg_prox)
        kwargs=dict(common, tau_incr=1.0,tau_decr=1.0,min_rho=rho,max_rho=rho,n_jobs=1)
    previous_trace=sys.gettrace()
    error=None
    try:
        sys.settrace(tracer)
        fn(*args,**kwargs)
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc)
    finally:
        sys.settrace(previous_trace)
    observations=[{'step':entry['step'],'name':entry['name'],'value':captured[(entry['step'],entry['name'])]} for entry in case['observation_schema'] if (entry['step'],entry['name']) in captured]
    missing=[{'step':entry['step'],'name':entry['name']} for entry in case['observation_schema'] if (entry['step'],entry['name']) not in captured]
    result={'id':case['id'],'observations':observations}
    if error or missing:
        result.update(status='blocked',reason=error or 'Original solver stopped before all requested full-iteration states were observed.',missing_observations=missing)
    return result


def main():
    public=json.loads(Path(os.environ['OPTIREPRO_CASES']).read_text())
    cases=public['cases']
    workspace=Path(os.environ['OPTIREPRO_WORKSPACE']).resolve()
    results=[]
    try:
        import numpy as np
        original=load_original(workspace)
    except Exception as exc:
        original=None
        import_error=type(exc).__name__+': '+str(exc)
    for case in cases:
        try:
            if original is None: raise RuntimeError(import_error)
            results.append(run_case(case,original,np))
        except Exception as exc:
            results.append({'id':case['id'],'observations':[],'status':'blocked',
                            'reason':type(exc).__name__+': '+str(exc),
                            'missing_observations':[{'step':o['step'],'name':o['name']} for o in case['observation_schema']]})
    print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':results},allow_nan=False,separators=(',',':')))

if __name__=='__main__':
    main()
