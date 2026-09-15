"""Exact paper-derived dual SGS-CD experiments; no reproduction code inputs."""
from fractions import Fraction as Q
import json
from pathlib import Path
MECH=['dual_conjugate_gradient','restricted_gauss_southwell_selection','single_edge_dual_update_and_endpoint_refresh']
def numeric(v):return [numeric(x) for x in v] if isinstance(v,list) else float(v)
def make_case(cid,centers,curvatures,edges,initial,active):
    c=[Q(z) for z in centers];a=[Q(z) for z in curvatures];lam=[Q(z) for z in initial];eta=Q(1,8)
    n=len(c);E=len(edges);A=[[Q(0) for _ in edges] for _ in c]
    for l,(i,j) in enumerate(edges):A[i][l]=Q(1);A[j][l]=Q(-1)
    def state(lamb):
        y=[sum(A[i][l]*lamb[l] for l in range(E)) for i in range(n)]
        theta=[c[i]+y[i]/a[i] for i in range(n)]
        grad=[sum(A[i][l]*theta[i] for i in range(n)) for l in range(E)]
        F=sum(c[i]*y[i]+y[i]*y[i]/(2*a[i]) for i in range(n))
        return theta,grad,F
    entries=[]
    def emit(k,name,v):entries.append(dict(step=k,name=name,value=numeric(v)))
    for k,node in enumerate(active,1):
        theta,grad,F=state(lam)
        eligible=[l for l,e in enumerate(edges) if node in e]
        chosen=max(eligible,key=lambda l:abs(grad[l]))
        assert sum(abs(grad[l])==abs(grad[chosen]) for l in eligible)==1
        emit(k,'theta_before',theta);emit(k,'dual_gradient_before',grad);emit(k,'selected_edge',chosen);emit(k,'dual_objective_before',F)
        lam[chosen]-=eta*grad[chosen]
        newtheta,newgrad,newF=state(lam)
        emit(k,'lambda_after',lam);emit(k,'theta_after',newtheta);emit(k,'dual_objective_after',newF)
    return dict(id=cid,purpose='Four serial SGS-CD activations on '+('a cycle with redundant dual coordinates.' if cid=='triangle_cycle' else 'a path, including single-neighbor and two-neighbor active sets.'),covers=MECH,
       inputs=dict(dimension=1,nodes=n,edges=edges,incidence_matrix=numeric(A),quadratic_centers=numeric(c),quadratic_curvatures=numeric(a),lambda_initial=numeric([Q(z) for z in initial]),
           primal_objective='f_i(theta)=a_i*(theta-c_i)^2/2; original objective sum_i f_i(theta) subject to consensus',
           dual_definition='F(lambda)=sum_i f_i^*((A lambda)_i), f_i^*(y)=c_i*y+y^2/(2*a_i); theta_i(lambda)=grad f_i^*((A lambda)_i)=c_i+(A lambda)_i/a_i',
           active_nodes=active,randomness='Uniform independent active node sampling; condition on listed zero-based active_nodes. Serial events, no overlapping in-flight updates. SGS neighbor selection itself is deterministic.',
           graph='Undirected graph defined by edges; each edge orientation is +1 at first endpoint and -1 at second. All node and edge identifiers are zero-based.'),
       parameters=dict(algorithm='SGS-CD Algorithm 2',eta=.125,iterations=4,
           selection='At each event select the edge incident to active node with largest absolute current dual partial gradient. No ties occur; no global max over inaccessible edges. Only selected lambda changes.',
           initial_primal='Initialize theta_i to grad f_i^*((A lambda_initial)_i), as used for local conjugate-gradient caches. theta observations mean these cached conjugate gradients, not an independent gradient-descent primal state.',
           observation_timing='step=k is serial event k. theta_before and full dual_gradient_before use lambda at start. selected_edge is zero-based chosen edge. lambda_after,theta_after,dual_objective_after are after one update. Refresh only the selected edge endpoints; full theta is observable through caches.'),
       atol=1e-12,rtol=1e-12,expected=entries,
       derivation='Fenchel conjugating a_i*(theta-c_i)^2/2 gives f_i^*(y)=c_i*y+y^2/(2*a_i). Eq.(6) gives dual gradient A^T*(c+diag(1/a)A lambda). Algorithm 2 picks argmax absolute gradient over the active incident-edge set, then Eq.(4) subtracts eta times that coordinate gradient. All values and objectives use Fraction exact arithmetic; each maximum is verified unique.')
def build():
    return dict(schema_version='optirepro.paper_algorithm_contract.v1',
       paper=dict(paper_id='2504.19004',title='Setwise Coordinate Descent for Dual Asynchronous Decentralized Optimization',sha256='4fe686f80dfa8d1f1cb35b45614252ef4bb24527d114c6f16bba3f173723915c'),
       algorithm=dict(name='Setwise Gauss-Southwell CD (SGS-CD), Algorithm 2',citations=['PDF p.4 Eq.(3), conjugate definition and incidence convention','PDF p.5 Eq.(4), p.6 Eq.(6), p.8 Algorithm 2 and Section 4.2'],core_mechanisms=MECH,
          assumptions=['Connected undirected graph, scalar strongly convex smooth local quadratics, serial asynchronous activations.','All incident edges are queried before SGS selection; use current dual gradients with the supplied fixed orientation.','Fixed eta=1/8 is conservative: ||A||^2/min(a)<=4 for these graphs, so eta<=1/L_upper.','Scope is unweighted SGS-CD; SU-CD, coordinate-Lipschitz variants, communication latency, and convergence rates are not tested.']),
       cases=[make_case('triangle_cycle',['-1','2','1/2'],['1','2','4'],[[0,1],[1,2],[0,2]],['1/2','-1/4','1/8'],[0,1,2,0]),
              make_case('path_restricted',['-1','2','1/2','-2'],['1','2','4','3'],[[0,1],[1,2],[2,3]],['0','0','0'],[1,2,0,2])])
if __name__=='__main__':Path(__file__).with_name('contract.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
