"""Standalone exact rational instantiation of this paper's Eq.(4) and Algorithm 1."""
from fractions import Fraction as Q
import json
from pathlib import Path
MECH=['local_sgd_periodic_averaging','scaffold_frozen_anchor_batch','scaffold_corrected_steps_and_global_update']
def numeric(v): return [numeric(x) for x in v] if isinstance(v,list) else float(v)
def build_case(method):
    a=[Q(1),Q(3)];b=[Q(-1),Q(2)];eta=Q(1,10);x=[Q(4,5)]*2
    noise=[[Q(1,4),Q(-1,4)],[Q(1,4),Q(1,4)],[Q(-1,4),Q(1,4)],[Q(1,4),Q(-1,4)],
           [Q(-1,4),Q(1,4)],[Q(-1,4),Q(-1,4)],[Q(1,4),Q(1,4)],[Q(-1,4),Q(1,4)]]
    entries=[]
    def emit(t,n,v):entries.append(dict(step=t,name=n,value=numeric(v)))
    if method=='local_sgd':
        for r in range(2):
            base=x[0]
            for k in range(2):
                t=2*r+k;g=[a[j]*x[j]+b[j]+noise[t][j] for j in range(2)]
                emit(t+1,'x_before',x);emit(t+1,'sample_gradient',g)
                trial=[x[j]-eta*g[j] for j in range(2)]
                emit(t+1,'local_proposal',trial)
                x=trial if k==0 else [sum(trial)/2]*2
                emit(t+1,'x_after',x)
        covers=MECH[:1];steps=4
    else:
        for r in range(2):
            base=x[0];anchor_sum=[Q(0),Q(0)]
            for k in range(2):
                t=4*r+k;g=[a[j]*x[j]+b[j]+noise[t][j] for j in range(2)]
                emit(t+1,'x_before',x);emit(t+1,'sample_gradient',g)
                anchor_sum=[anchor_sum[j]+g[j] for j in range(2)]
                emit(t+1,'x_after',x)
            gh=[s/2 for s in anchor_sum];gb=sum(gh)/2
            emit(4*r+2,'anchor_local',gh);emit(4*r+2,'anchor_global',gb)
            train_sum=[Q(0),Q(0)]
            for k in range(2,4):
                t=4*r+k;g=[a[j]*x[j]+b[j]+noise[t][j] for j in range(2)]
                emit(t+1,'x_before',x);emit(t+1,'sample_gradient',g)
                corrected=[g[j]-gh[j]+gb for j in range(2)]
                emit(t+1,'corrected_gradient',corrected)
                train_sum=[train_sum[j]+g[j] for j in range(2)]
                if k==2:x=[x[j]-eta*corrected[j] for j in range(2)]
                else:x=[base-eta*sum(train_sum)/2]*2
                emit(t+1,'x_after',x)
        covers=MECH[1:];steps=8
    return dict(id=method,purpose=('Two synchronization periods of Eq.(4).' if method=='local_sgd' else 'Two complete anchor-and-training cycles of the specific simplified SCAFFOLD in Algorithm 1.'),covers=covers,
      inputs=dict(method=method,dimension=1,workers=2,x_initial=[.8,.8],quadratic_a=[1,3],quadratic_b=[-1,2],
          local_objective='f_i(x)=a_i*x^2/2+b_i*x; global f=(f_1+f_2)/2',
          stochastic_objective='F_i(x,z)=f_i(x)+z*x, so g_i(x,z)=a_i*x+b_i+z',
          noise=numeric(noise[:steps]),randomness='Independent Rademacher noise +/-0.25 equiprobably for every worker and microstep; condition on supplied [microstep][worker] realization.',
          network='Full synchronous participation; central arithmetic averaging of both workers.'),
      parameters=dict(eta=.1,tau=2,microsteps=steps,outer_cycles=2,
         observation_timing='step=t+1 for microstep t. x_before and sample_gradient precede action; x_after follows freeze/local update/broadcast. anchor_local/global appear after second frozen microstep of each SCAFFOLD cycle. corrected_gradient at last microstep is the gradient whose average contribution enters Algorithm 1 line 14; no separate last local update is required.',
         method_definition='LocalSGD is Eq.(4): average after each 2 local updates. SCAFFOLD is this paper Algorithm 1: freeze two steps and estimate anchors, perform one corrected local update, then global line-14 update using both training gradients and broadcast; recompute anchors next cycle. Not persistent-control-variate SCAFFOLD.'),
      atol=1e-12,rtol=1e-12,expected=entries,
      derivation='Exact Fraction arithmetic. LocalSGD: g_i=a_i*x_i+b_i+z_i; trial=x_i-eta*g_i; average trials when t+1 is divisible by tau. Algorithm 1 SCAFFOLD: anchor_i is mean of two gradients at unchanged cycle start; anchor_global is worker mean; first training step subtracts eta*(g_i-anchor_i+anchor_global); line 14 gives next broadcast=cycle_start-eta/2*sum_i(sum of two training gradients). Repeat with new anchors. Every value is converted to float only for serialization.')
def build():
    return dict(schema_version='optirepro.paper_algorithm_contract.v1',paper=dict(paper_id='2501.04443',title='Revisiting LocalSGD and SCAFFOLD: Improved Rates and Missing Analysis',sha256='8bb1c22f50d76d0d719e90f9f8a2a55b58404f958cd3cc63682ffcf1603d0085'),
      algorithm=dict(name='LocalSGD Eq.(4) and simplified SCAFFOLD Algorithm 1',citations=['PDF pp.4-5 Section 3.2, Eq.(4) and Algorithm 1 lines 1-15'],core_mechanisms=MECH,
          assumptions=['This is primarily an analysis paper; the test instantiates the algorithms it explicitly defines, without inventing a proposed method.','Smooth convex scalar quadratic local objectives, same initial model, full participation, unbiased bounded additive gradient noise.','Unequal Hessians are intentional. These trajectories test recursion only, not the global gradient-similarity assumptions of every convergence theorem.']),cases=[build_case('local_sgd'),build_case('simplified_scaffold')])
if __name__=='__main__':Path(__file__).with_name('contract.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
