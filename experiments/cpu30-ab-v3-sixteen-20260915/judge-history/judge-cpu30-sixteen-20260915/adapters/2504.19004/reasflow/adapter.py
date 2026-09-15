import sys,os,json
sys.dont_write_bytecode=True
from pathlib import Path
import numpy as np
W=Path(os.environ['OPTIREPRO_WORKSPACE']);sys.path.insert(0,str(W/'src'))
import setwise_cd.problems as problems
import setwise_cd.graphs as graphs
from setwise_cd.solvers import SxCD as Solver
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
    adjacency=np.zeros((n,n))
    for u,v in i['edges']:adjacency[u,v]=adjacency[v,u]=1
    meta=graphs.prepare_graph(adjacency)
    # Original metadata orders edges lexicographically; map observations back.
    order=[i['edges'].index(list(e)) for e in meta['edge_to_nodes']]
    A=meta['A']
    problem=problems.QuadraticProblem(n,1,A,meta['edge_to_nodes'],np.random.default_rng(0),c_choice='diagonal')
    problem.P=[np.array([[aj/2.]]) for aj in a]
    problem.q=[np.array([-aj*cj]) for aj,cj in zip(a,centers)]
    problem.r=[float(aj*cj*cj/2.) for aj,cj in zip(a,centers)]
    problem._precompute()
    solver=Solver(problem,meta,'SGS-CD',p['iterations'],rng=RNG(),py_rng=RNG())
    solver.lambdas[:]=-np.asarray(i['lambda_initial'])[order,None]
    solver._all_local_thetas()
    def trace(f,event,arg):
        if f.f_code is Solver.solve.__code__ and event=='line' and f.f_locals.get('t')==0:
            if f.f_lineno==88:
                emit(0,'theta_before',solver.thetas.ravel())
                native=np.array([solver._edge_gradient(e)[0] for e in range(E)])
                public=np.empty(E);public[order]=native
                emit(0,'dual_gradient_before',public)
                emit(0,'dual_objective_before',-problem.lagrangian(solver.thetas,solver.lambdas))
            if f.f_lineno==90:emit(0,'selected_edge',order[f.f_locals['e']])
        return trace
    try:
        sys.settrace(trace);solver.solve()
    finally:sys.settrace(None)
    present={(r['step'],r['name']) for r in rows}
    missing=[item for item in c['observation_schema'] if (item['step'],item['name']) not in present]
    return {'id':c['id'],'status':'blocked','reason':'Original SxCD.solve line 95 updates lambdas by grad / self.L[e], with L derived by QuadraticProblem._precompute from public curvature. Neither a fixed eta argument nor self.stepsizes is used. Changing L would replace the algorithm step rule. Only first-event observations preceding that incompatible update are reported; later actual native trajectory is not substituted for the requested fixed-eta experiment.', 'missing_observations':missing,'observations':rows}
print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':[solve(c) for c in json.load(open(os.environ['OPTIREPRO_CASES']))['cases']]}))
