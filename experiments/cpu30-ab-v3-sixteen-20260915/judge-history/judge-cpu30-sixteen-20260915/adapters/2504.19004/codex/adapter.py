import sys,os,json
sys.dont_write_bytecode=True
from pathlib import Path
import numpy as np
W=Path(os.environ['OPTIREPRO_WORKSPACE']);sys.path.insert(0,str(W/'src'))
import setwise_cd.problems as problems
import setwise_cd.graphs as graphs
from setwise_cd.solver import SetwiseCDSolver as Solver
def solve(c):
    i,p=c['inputs'],c['parameters'];n=i['nodes'];E=len(i['edges'])
    a=np.asarray(i['quadratic_curvatures']);centers=np.asarray(i['quadratic_centers'])
    A=np.asarray(i['incidence_matrix'],float).T
    class RNG:
        k=0
        def integers(self,*a,**kw):
            result=i['active_nodes'][self.k];self.k+=1;return result
        def choice(self,choices,*a,**kw):
            if len(choices)!=1: raise RuntimeError('Public contract guarantees no selection tie')
            return choices[0]
    rows=[]
    def emit(t,name,value):rows.append({'step':t+1,'name':name,'value':np.asarray(value).tolist()})
    meta=graphs.create_edge_metadata(A)
    class DataRNG:
        k=0
        def normal(self,*,size):
            j,phase=divmod(self.k,2);self.k+=1
            x=np.sqrt(a[j]/2.)
            return np.full(size,x if phase==0 else (x*centers[j]-x-np.cos(x))/.25)
    problem=problems.LLSProblem(n,1,1,A,[tuple(e) for e in i['edges']],DataRNG(),iid=True)
    solver=Solver(problem,meta,np.full(E,p['eta']),'SGS-CD',steps=p['iterations'],rng=RNG(),stop_tol=None)
    solver.lambdas[:]=-np.asarray(i['lambda_initial'])[:,None]
    solver.theta[:]=np.stack([solver._theta(j) for j in range(n)])
    def exact_theta(): return np.stack([solver._theta(j) for j in range(n)])
    def dual_value():return -problem.lagrangian(exact_theta(),solver.lambdas)
    def trace(f,event,arg):
        if f.f_code is Solver.solve.__code__ and event=='line':
            t=f.f_locals.get('t',0)
            if f.f_lineno==78:
                emit(t,'theta_before',solver.theta.ravel())
                emit(t,'dual_gradient_before',(A@exact_theta()).ravel())
                emit(t,'dual_objective_before',dual_value())
            if f.f_lineno==80:emit(t,'selected_edge',f.f_locals['e'])
            if f.f_lineno==90:
                emit(t,'lambda_after',-solver.lambdas.ravel())
                emit(t,'theta_after',solver.theta.ravel())
                emit(t,'dual_objective_after',dual_value())
        return trace
    try:
        sys.settrace(trace);solver.solve()
    finally:sys.settrace(None)
    return {'id':c['id'],'observations':rows}
print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':[solve(c) for c in json.load(open(os.environ['OPTIREPRO_CASES']))['cases']]}))
