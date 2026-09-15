"""Paper-only RSA oracle: stdlib arithmetic, no tested/official implementation imports.
Source: local arXiv:1811.03761v2 PDF, pp.3-4 Eqs.(7),(8),(10),(11), Proposition 1.
Run this script only against this frozen paper-derived input specification.
"""
import hashlib
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent
PAPER = Path('/Users/zanehuang/work/OptiRepro/datasets/benchmarks/cpu30_v1/input/1811.03761/paper.pdf')

def sub(a,b): return [u-v for u,v in zip(a,b)]
def add(a,b): return [u+v for u,v in zip(a,b)]
def scale(c,a): return [c*u for u in a]
def sg(v,p):
    if p == 1:
        assert all(t != 0 for t in v), 'Ambiguous sign(0) deliberately excluded'
        return [1 if t>0 else -1 for t in v]
    if p == 2:
        n=math.sqrt(sum(t*t for t in v))
        assert n>0
        return [t/n for t in v]
    assert p == 'infinity'
    maximum=max(abs(t) for t in v)
    ix=[j for j,t in enumerate(v) if abs(t)==maximum]
    assert maximum>0 and len(ix)==1, 'Ambiguous max tie deliberately excluded'
    return [(1 if v[j]>0 else -1) if j==ix[0] else 0 for j in range(len(v))]

def derive(case):
    inp,par=case['inputs'],case['parameters']
    master=inp['initial_master'][:]
    workers=[x[:] for x in inp['initial_regular_workers']]
    centers=inp['regular_worker_quadratic_centers']
    master_center=inp['master_quadratic_center']
    expected=[{'step':0,'name':'master','value':master},{'step':0,'name':'regular_workers','value':workers}]
    records=[]
    for step,alpha in enumerate(par['step_sizes'],1):
        worker_grad=[sub(x,a) for x,a in zip(workers,centers)]
        worker_pen=[sg(sub(x,master),par['p']) for x in workers]
        byz_pen=[sg(sub(master,z),par['p']) for z in inp['byzantine_messages_by_step'][step-1]]
        master_pen=[sum(-q[j] for q in worker_pen)+sum(q[j] for q in byz_pen) for j in range(len(master))]
        master_grad=sub(master,master_center)
        new_workers=[sub(x,scale(alpha,add(g,scale(par['lambda'],q)))) for x,g,q in zip(workers,worker_grad,worker_pen)]
        new_master=sub(master,scale(alpha,add(master_grad,scale(par['lambda'],master_pen))))
        record={
            'worker_loss_gradients_before_update':worker_grad,
            'worker_penalty_subgradients_before_update':worker_pen,
            'byzantine_master_subgradients_before_update':byz_pen,
            'master_penalty_subgradient_sum_before_update':master_pen,
            'master_regularizer_gradient_before_update':master_grad,
            'regular_workers':new_workers,
            'master':new_master,
        }
        records.append(record)
        expected.extend({'step':step,'name':name,'value':value} for name,value in record.items())
        workers,master=new_workers,new_master
    case['expected']=expected
    # Every named derivative at step t is evaluated at state t-1. A state at step t is post-update.
    case['derivation'] += '\n\nAll loss functions are F_i(x)=0.5*||x-a_i||_2^2 and f0(x)=0.5*||x-c0||_2^2. Thus gradients are x-a_i and x-c0, with no stochastic noise. Define s_i=partial||x_i-x0||_p and b_j=partial||x0-z_j||_p from OLD states. Master sum S=-sum_i s_i+sum_j b_j. Then x_i_new=x_i-alpha*(x_i-a_i+lambda*s_i); x0_new=x0-alpha*(x0-c0+lambda*S). No division by worker count. Derivative fields at step t refer to state t-1; master and regular_workers at step t are post-update. Final output is the last master; regular local states are also required.\n'
    for t,r in enumerate(records,1):
        case['derivation'] += f'\nStep {t}, alpha={par["step_sizes"][t-1]}: gradients={r["worker_loss_gradients_before_update"]}; s_i={r["worker_penalty_subgradients_before_update"]}; b_j={r["byzantine_master_subgradients_before_update"]}; S={r["master_penalty_subgradient_sum_before_update"]}; g0={r["master_regularizer_gradient_before_update"]}; new master={r["master"]}; new workers={r["regular_workers"]}.\n'
    return case

common=['independent_local_states_and_heterogeneous_gradients','synchronous_old_state_updates','sum_model_penalties_with_master_regularizer']
cases=[
 {'id':'rsa_l1_sign_crossing_byzantine','purpose':'Nonzero heterogeneous states, active l1 penalty, sign reversal after first step, master regularizer, saturated Byzantine influence and summed old-model aggregation.','covers':common+['l1_signed_penalty_and_bounded_attack'],
  'inputs':{'initial_master':[1,-1],'initial_regular_workers':[[1.2,-0.8],[-2,2]],'regular_worker_quadratic_centers':[[-2,-3],[3,-1]],'master_quadratic_center':[0,0],'byzantine_messages_by_step':[[[100,-100]],[[1000000000,-1000000000]],[[100,-100]]]},
  'parameters':{'p':1,'lambda':0.5,'step_sizes':[0.25,0.125,0.1]},
  'derivation':'At k=0 worker signs are (+,+),(-,+), while the Byzantine master sign is (-,+). Therefore S=(-1,-1). Worker 1 crosses below the master in both coordinates after the first update, so its next sign is (-,-) and S becomes (+,+). This distinguishes the synchronous old-state formula from using already-updated worker messages. The Byzantine message magnitude alternates 100, 1e9, 100; its sign remains (-,+) and hence its penalty contribution remains (-0.5,+0.5).','atol':1e-9,'rtol':1e-7},
 {'id':'rsa_l2_vector_normalization','purpose':'Distinguish the unsquared Euclidean norm subgradient from elementwise signs, squared norm gradients, clipping and mean aggregation.','covers':common+['l2_unit_norm_subgradient'],
  'inputs':{'initial_master':[1,-1],'initial_regular_workers':[[4,3],[-3,2]],'regular_worker_quadratic_centers':[[-1,1],[2,-2]],'master_quadratic_center':[0,0],'byzantine_messages_by_step':[[[7,-9]],[[7,-9]]]},
  'parameters':{'p':2,'lambda':0.5,'step_sizes':[0.2,0.1]},
  'derivation':'For p=2 and a nonzero difference v, Proposition 1 implies s=v/||v||2. Initially worker differences are (3,4),(-4,3), with norms 5,5, and the Byzantine master difference is (-6,8), norm 10. Thus s1=(0.6,0.8), s2=(-0.8,0.6), b=(-0.6,0.8), S=(-0.4,-0.6). On step 2 all subgradients are recomputed from the changed full vector differences; they are not cached.','atol':1e-9,'rtol':1e-7},
 {'id':'rsa_linf_unique_maximum','purpose':'Check the general-p variant: infinity-norm subgradient uses the signed uniquely largest absolute coordinate, with all other coordinates zero.','covers':common+['linf_max_coordinate_subgradient'],
  'inputs':{'initial_master':[1,-1],'initial_regular_workers':[[4,0],[0,3]],'regular_worker_quadratic_centers':[[-1,2],[3,-1]],'master_quadratic_center':[0,0],'byzantine_messages_by_step':[[[11,1]],[[11,1]]]},
  'parameters':{'p':'infinity','lambda':0.5,'step_sizes':[0.2,0.1]},
  'derivation':'For p=infinity, the dual norm in Proposition 1 is l1. At a uniquely largest absolute coordinate, the unique subgradient is its signed coordinate basis vector. Initially v1=(3,1), v2=(-1,4), and vB=(-10,-2), so s1=(1,0),s2=(0,1),b=(-1,0),S=(-2,-1). On step 2 differences are (1.9,1.1),(-0.4,2.8),(-10,-1.7), so the same unique supporting coordinates remain.','atol':1e-9,'rtol':1e-7},
]
contract={
 'schema_version':'optirepro.paper_algorithm_contract.v1',
 'paper':{'paper_id':'1811.03761','title':'RSA: Byzantine-Robust Stochastic Aggregation Methods for Distributed Learning from Heterogeneous Datasets','sha256':hashlib.sha256(PAPER.read_bytes()).hexdigest()},
 'algorithm':{'name':'RSA (l1, l2 and linfinity norm variants)',
  'citations':['PDF p.3 Eq.(5): unsquared l1 distance penalty added to each regular local objective.','PDF p.3 Eqs.(7),(8): local stochastic gradient plus signed penalty; master regularizer plus summed signs of regular and Byzantine model messages.','PDF p.4 Algorithm 2: master broadcasts x0^k, workers send xi^k, then both update; all right-hand sides use iteration k states.','PDF p.4 Eqs.(9)-(11) and Proposition 1: general lp norm penalty and subgradient characterized by inner product equality and dual norm bound.','PDF pp.4-5 Assumptions 1-3: strong convexity, Lipschitz gradients, independent-in-time local sampling and bounded variance; heterogeneous distributions across workers allowed.','PDF p.5 Theorem 1: consensus optimum requires lambda >= max_i ||gradient E F(x_tilde_star,xi_i)||_b; short trajectories do not assert this condition.'],
  'core_mechanisms':common+['l1_signed_penalty_and_bounded_attack','l2_unit_norm_subgradient','linf_max_coordinate_subgradient'],
  'assumptions':['All oracle functions are deterministic strongly convex quadratic losses with identity Hessian; stochastic variance is zero and worker centers differ.','All updates are simultaneous from a shared old-state snapshot. The master receives current local models, not gradients, and does not identify or remove Byzantine senders.','lambda is positive. Step sizes are explicit finite-probe inputs; no convergence claim is made for these short schedules.','The p=infinity parameter is JSON string infinity as a configuration value; all expected values are numeric. A variant missing from an implementation should be reported unsupported, not silently replaced by another p.','No l1 coordinate difference is zero, no l2 difference vector is zero, and every infinity-norm difference has a unique maximum absolute coordinate. Thus no arbitrary subgradient choice affects expected results.','Paper Algorithm 2 does not define a generic stopping condition or API return shape; here the prescribed final master iterate is the observable output, consistent with p.5 evaluation using x0.']},
 'cases':[derive(case) for case in cases]
}
(OUT/'contract.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
for case in contract['cases']:
    print(case['id'])
    print(case['derivation'])
print('paper_sha256',contract['paper']['sha256'])
print('contract_sha256',hashlib.sha256((OUT/'contract.json').read_bytes()).hexdigest())
