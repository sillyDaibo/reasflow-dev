#!/usr/bin/env python3
"""Public-input adapter observing the original staggered BEER driver, unchanged."""
import inspect
import json
import os
from pathlib import Path
import sys


def execute(case, workspace):
    import numpy as np
    sys.path.insert(0,str(workspace))
    import beer_repro.core as core
    observations=[]
    requested={(v['step'],v['name']) for v in case['observation_schema']}
    inputs,parameters=case['inputs'],case['parameters']
    centers=np.asarray(inputs['quadratic_centers_by_client'],dtype=float)
    diagonals=np.asarray(inputs['quadratic_diagonals_by_client'],dtype=float)
    initial=np.asarray(inputs['initial_common_point'])
    mixing=np.asarray(inputs['mixing_matrix_W'],dtype=float)
    n,dimension=centers.shape
    clients=[(np.asarray([[i]],dtype=float),np.asarray([i])) for i in range(n)]

    class SyntheticQuadratic:
        def __init__(self):
            self.dimension=dimension
        def loss_grad(self,point,data,labels):
            client=int(labels[0])
            # Keep the model gradient output in the source model's float32 convention.
            delta=point-centers[client]
            return float(0.5*np.sum(diagonals[client]*delta*delta)),(diagonals[client]*delta).astype(np.float32)
        def accuracy(self,*args):
            return 0.0

    def public_compressor(value):
        specification=parameters['compressor']
        if specification['name']=='scale':
            return value*specification['factor']
        if specification['name']=='top1':
            result=np.zeros_like(value)
            index=int(np.argmax(np.abs(value)))
            result[index]=value[index]
            return result
        raise ValueError('Unsupported public compressor: '+specification['name'])

    lines,start=inspect.getsourcelines(core.run_decentralized)
    def source_line(text):
        matches=[start+i for i,line in enumerate(lines) if line.strip()==text]
        if len(matches)!=1:
            raise RuntimeError('Source observation boundary is not unique: '+text)
        return matches[0]
    initialize_input_line=source_line('x = np.repeat(x0[None, :], n, axis=0)')
    initialized_line=source_line('x -= learning_rate * v')
    complete_round_line=source_line('x_new = x + gamma * ((mixing @ h) - h) - learning_rate * v')
    code=core.run_decentralized.__code__
    def capture(local,step):
        for name,attribute in [('X','x'),('H','h'),('V','v'),('G','gstate')]:
            if (step,name) in requested:
                observations.append({'step':step,'name':name,'value':local[attribute].T.copy().tolist()})
    def tracer(frame,event,argument):
        if frame.f_code is code and event=='line':
            if frame.f_lineno==initialize_input_line:
                # Replace the public initial vector before replication or gradients;
                # np.copyto retains the original x0 float32 allocation and dtype.
                np.copyto(frame.f_locals['x0'],initial,casting='unsafe')
            elif frame.f_lineno==initialized_line:
                capture(frame.f_locals,0)
            elif frame.f_lineno==complete_round_line:
                # x/h have advanced once already; v/gstate just caught up.
                capture(frame.f_locals,int(frame.f_locals['iteration']))
        return tracer
    previous_trace=sys.gettrace()
    original_compressor=core.compressor
    try:
        core.compressor=lambda *args,**kwargs:public_compressor
        sys.settrace(tracer)
        core.run_decentralized(clients=clients,test=clients[0],model=SyntheticQuadratic(),algorithm='beer',
            learning_rate=parameters['eta'],gamma=parameters['gamma'],compressor_name='identity',
            compressor_parameter=0,mixing=mixing,n_iters=parameters['iterations'],batch_size=1,eval_every=parameters['iterations'],seed=0)
        result={'id':case['id'],'observations':observations}
    except Exception as exc:
        result={'id':case['id'],'observations':observations,'status':'blocked','reason':type(exc).__name__+': '+str(exc)}
    finally:
        sys.settrace(previous_trace)
        core.compressor=original_compressor
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
