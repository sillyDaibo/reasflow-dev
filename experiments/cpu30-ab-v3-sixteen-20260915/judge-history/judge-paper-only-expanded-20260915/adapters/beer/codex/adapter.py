#!/usr/bin/env python3
"""Public-input adapter: execute the original BEER driver and observe its state."""
import json
import os
from pathlib import Path
import sys
import tempfile


def execute(case, workspace):
    import numpy as np
    sys.path.insert(0, str(workspace))
    import beer_repro.algorithms as algorithms
    import beer_repro.runner as runner
    from beer_repro.data import ClientData

    requested = {(v['step'], v['name']) for v in case['observation_schema']}
    observations = []
    inputs, parameters = case['inputs'], case['parameters']
    centers = np.asarray(inputs['quadratic_centers_by_client'], dtype=float)
    diagonals = np.asarray(inputs['quadratic_diagonals_by_client'], dtype=float)
    initial = np.asarray(inputs['initial_common_point'], dtype=float)
    mixing = np.asarray(inputs['mixing_matrix_W'], dtype=float)
    n, dimension = centers.shape
    clients = [ClientData(np.asarray([[i]], dtype=float), np.asarray([i])) for i in range(n)]

    def objective(point, data, labels, alpha=0):
        client = int(labels[0])
        difference = point-centers[client]
        return float(0.5*np.sum(diagonals[client]*difference*difference)), diagonals[client]*difference

    def public_compressor(value, *args, **kwargs):
        specification = parameters['compressor']
        if specification['name'] == 'scale':
            return value*specification['factor']
        if specification['name'] == 'top1':
            result = np.zeros_like(value)
            index = int(np.argmax(np.abs(value)))
            result[index] = value[index]
            return result
        raise ValueError('Unsupported public compressor: '+specification['name'])

    def capture(algorithm, step):
        for name, attribute in [('X','x'),('H','h'),('V','v'),('G','g')]:
            if (step,name) in requested:
                observations.append({'step':step,'name':name,'value':getattr(algorithm,attribute).T.copy().tolist()})

    init_code = algorithms.BEER.initialize.__code__
    step_code = algorithms.BEER.step.__code__
    previous_trace = sys.gettrace()
    def tracer(frame, event, argument):
        if event == 'return' and frame.f_code is init_code:
            capture(frame.f_locals['self'], 0)
        elif event == 'return' and frame.f_code is step_code and frame.f_locals['self'].round > 0:
            capture(frame.f_locals['self'], frame.f_locals['self'].round)
        return tracer

    replacements = [(runner,'load_a9a',lambda *args, **kwargs:(clients,clients[0],{'features':dimension,'name':'public synthetic quadratics'})),
        (runner,'_initial_params',lambda *args, **kwargs:initial.copy()),
        (runner,'mixing_matrix',lambda *args, **kwargs:mixing.copy()),
        (runner,'logistic_loss_gradient',objective),
        (runner,'logistic_accuracy',lambda *args, **kwargs:0.0),
        (algorithms,'compress',public_compressor)]
    originals = [(module,name,getattr(module,name)) for module,name,value in replacements]
    try:
        for module,name,value in replacements:
            setattr(module,name,value)
        sys.settrace(tracer)
        with tempfile.TemporaryDirectory(prefix='optirepro-beer-driver-') as directory:
            # Original run_experiment computes every next-point gradient location.
            runner.run_experiment({'task':'a9a','clients':n,'data_root':'public-fixture',
                'rounds':parameters['iterations'],'lr':parameters['eta'],'gamma':parameters['gamma'],
                'batch_size':1,'methods':['BEER'],'compressor':'identity','compression_param':0,
                'seed':0,'topology':'public-W'}, directory)
        result = {'id':case['id'],'observations':observations}
    except Exception as exc:
        result = {'id':case['id'],'observations':observations,'status':'blocked','reason':type(exc).__name__+': '+str(exc)}
    finally:
        sys.settrace(previous_trace)
        for module,name,value in originals:
            setattr(module,name,value)
    present={(v['step'],v['name']) for v in observations}
    missing=[v for v in case['observation_schema'] if (v['step'],v['name']) not in present]
    if missing:
        result.update(status='blocked',missing_observations=missing)
        result.setdefault('reason','Original execution did not expose every requested state.')
    return result


def main():
    public=json.loads(Path(os.environ['OPTIREPRO_CASES']).read_text())
    workspace=Path(os.environ['OPTIREPRO_WORKSPACE']).resolve()
    results=[]
    for case in public['cases']:
        try:
            results.append(execute(case,workspace))
        except Exception as exc:
            results.append({'id':case['id'],'observations':[],'status':'blocked','reason':type(exc).__name__+': '+str(exc),'missing_observations':case['observation_schema']})
    print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':results},allow_nan=False))

if __name__=='__main__':
    main()
