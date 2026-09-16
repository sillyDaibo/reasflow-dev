import sys, os, json
sys.dont_write_bytecode=True
from pathlib import Path
import numpy as np
W=Path(os.environ['OPTIREPRO_WORKSPACE'])
sys.path.insert(0,str(W))
import localsgd_repro.core as m
def solve(c):
    i,p=c['inputs'],c['parameters']; N=i['workers']; T=p['microsteps']; tau=p['tau']
    scaffold=i['method']=='simplified_scaffold'
    counts=[0]*N
    values={name:np.full((T,N),np.nan) for name in ['x_before','sample_gradient','local_proposal','x_after','corrected_gradient','anchor_local']}
    anchors={}; pending=[]
    def frozen(t): return scaffold and (t//tau)%2==0
    def save_pending():
        for t,j,x in pending:
            values['local_proposal'][t,j]=float(x[0]); values['x_after'][t,j]=float(x[0])
        pending.clear()
    class RNG:
        def __init__(self,j): self.j=j; self.t=0
        def normal(self,*a,**kw):
            z=np.array([i['noise'][self.t][self.j]],dtype=float); self.t+=1
            return z
    original_init=m._Worker.__init__; original_oracle=m._Worker.oracle
    created=[]
    def init(self,x0,A,x_star,config,mu,rng):
        j=len(created); original_init(self,x0,A,x_star,config,mu,RNG(j)); self.public_index=j; created.append(self)
    def oracle(w):
        j=w.public_index; t=counts[j]; counts[j]+=1
        values['x_before'][t,j]=w.x[0]
        g=original_oracle(w); values['sample_gradient'][t,j]=g[0]
        if frozen(t): values['x_after'][t,j]=w.x[0]
        else:
            if scaffold: values['corrected_gradient'][t,j]=(g-w.g_local+w.g_global)[0]
            pending.append((t,j,w.x))
        return g
    m._Worker.__init__,m._Worker.oracle=init,oracle
    def trace(f,event,arg):
        if f.f_code is m.run_algorithm.__code__ and event=='line':
            save_pending()
            if f.f_lineno==227:
                t=max(counts)-1
                values['anchor_local'][t]=np.array(f.f_locals['controls']).ravel()
                anchors[t]=float(f.f_locals['global_control'][0])
            if f.f_lineno==239:
                t=max(counts)-1
                values['x_after'][t,:]=f.f_locals['mean_x'][0]
        return trace
    a=np.array(i['quadratic_a'],float); b=np.array(i['quadratic_b'],float)
    data=m.SyntheticDataset(np.sqrt(a)[:,None,None],(-b/a)[:,None],np.array([i['x_initial'][0]],float),0.,float(a.max()),0.,0.,'LocalSGD_data')
    cfg=m.ExperimentConfig(algorithm='SCAFFOLD' if scaffold else 'LocalSGD',d=1,n=N,rounds=T//tau,tau=tau,rho=0.,sigma=1.,eta=p['eta'],loss='sum-of-squares')
    try:
        sys.settrace(trace); m.run_algorithm(cfg,data)
    finally:
        sys.settrace(None); m._Worker.__init__,m._Worker.oracle=original_init,original_oracle
    rows=[]
    for item in c['observation_schema']:
        t=item['step']-1; name=item['name']; val=anchors[t] if name=='anchor_global' else values[name][t]
        if not np.isfinite(val).all(): raise RuntimeError('Missing actual state '+str(item))
        rows.append({'step':t+1,'name':name,'value':np.asarray(val).tolist()})
    return {'id':c['id'],'observations':rows}
print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':[solve(c) for c in json.load(open(os.environ['OPTIREPRO_CASES']))['cases']]}))
