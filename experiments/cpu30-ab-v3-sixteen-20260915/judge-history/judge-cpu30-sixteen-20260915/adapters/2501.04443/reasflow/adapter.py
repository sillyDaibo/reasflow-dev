import sys, os, json
sys.dont_write_bytecode=True
from pathlib import Path
import numpy as np
W=Path(os.environ['OPTIREPRO_WORKSPACE'])
sys.path.insert(0,str(W/'src'))
import reproduction.algorithms as m
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
    class Objective:
        def __init__(self,j): self.j=j
        def gradient(self,x): return i['quadratic_a'][self.j]*x+i['quadratic_b'][self.j]
    class Problem:
        n=N
        x0=np.array([i['x_initial'][0]],float)
        def objectives(self,rho): return [Objective(j) for j in range(N)]
        def gradient(self,x,rho=0.): return np.mean([w.gradient(x) for w in self.objectives(rho)],axis=0)
    original_oracle=m._oracle; original_rngs=m._worker_rngs
    m._worker_rngs=lambda seed,n:[RNG(j) for j in range(n)]
    def oracle(fn,x,rng,sigma):
        j=rng.j; t=counts[j]; counts[j]+=1
        values['x_before'][t,j]=x[0]
        g=original_oracle(fn,x,rng,sigma); values['sample_gradient'][t,j]=g[0]
        if frozen(t): values['x_after'][t,j]=x[0]
        else: pending.append((t,j,x))
        return g
    m._oracle=oracle
    target=m.run_scaffold if scaffold else m.run_localsgd
    def trace(f,event,arg):
        if f.f_code is target.__code__ and event=='line':
            # corrected is available just before the original subtraction.
            if scaffold and f.f_lineno==97:
                t,j,_=pending[-1]; values['corrected_gradient'][t,j]=f.f_locals['corrected'][0]
            else: save_pending()
            if scaffold and f.f_lineno==86:
                t=max(counts)-1; values['anchor_local'][t]=np.array(f.f_locals['controls']).ravel(); anchors[t]=float(f.f_locals['global_control'][0])
            if f.f_lineno==(100 if scaffold else 62):
                t=max(counts)-1; values['x_after'][t,:]=f.f_locals['x'][0]
        return trace
    try:
        sys.settrace(trace); target(Problem(),rounds=T//tau,tau=tau,eta=p['eta'],sigma=1.,rho=0.,seed=0)
    finally:
        sys.settrace(None);m._oracle=original_oracle;m._worker_rngs=original_rngs
    rows=[]
    for item in c['observation_schema']:
        t=item['step']-1; name=item['name']; val=anchors[t] if name=='anchor_global' else values[name][t]
        if not np.isfinite(val).all(): raise RuntimeError('Missing actual state '+str(item))
        rows.append({'step':t+1,'name':name,'value':np.asarray(val).tolist()})
    return {'id':c['id'],'observations':rows}
print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':[solve(c) for c in json.load(open(os.environ['OPTIREPRO_CASES']))['cases']]}))
