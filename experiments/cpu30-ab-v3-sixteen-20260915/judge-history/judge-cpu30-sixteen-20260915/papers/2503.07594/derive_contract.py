"""Paper Algorithm 1 reference, exact rational arithmetic, no repository inputs."""
from fractions import Fraction as Q
import json
from pathlib import Path
MECH=['corrected_stochastic_local_updates','full_client_averaging','persistent_zero_sum_control_update']
def numeric(v):return [numeric(x) for x in v] if isinstance(v,list) else float(v)
def make_case(cid,theta0,xi0,H):
    theta=Q(theta0);xi=[Q(z) for z in xi0];gamma=Q(1,20)
    a=[Q(1),Q(3)];b=[Q(-1),Q(2)]
    signs=[[[1,-1],[-1,-1],[1,1]],[[-1,1],[1,1],[-1,1]],[[1,1],[1,-1],[-1,-1]]]
    noise=[[[Q(s,4) for s in row] for row in rnd[:H]] for rnd in signs]
    entries=[]
    def emit(t,n,v):entries.append(dict(step=t,name=n,value=numeric(v)))
    for t in range(3):
        x=[theta]*2;trajectory=[x[:]];grads=[];corrected=[]
        emit(t+1,'theta_before',theta);emit(t+1,'xi_before',xi)
        for h in range(H):
            g=[a[j]*x[j]+b[j]+noise[t][h][j] for j in range(2)]
            gc=[g[j]+xi[j] for j in range(2)]
            grads.append(g);corrected.append(gc)
            x=[x[j]-gamma*gc[j] for j in range(2)];trajectory.append(x[:])
        theta=sum(x)/2
        xi=[xi[j]+(x[j]-theta)/(gamma*H) for j in range(2)]
        assert sum(xi)==0
        emit(t+1,'local_theta',trajectory);emit(t+1,'sample_gradient',grads);emit(t+1,'corrected_gradient',corrected)
        emit(t+1,'theta_after',theta);emit(t+1,'xi_after',xi)
    return dict(id=cid,purpose='Three rounds of the paper SCAFFOLD with heterogeneous quadratics, explicit stochastic draws, and persistent centered controls.',covers=MECH,
       inputs=dict(dimension=1,clients=2,theta_initial=float(Q(theta0)),xi_initial=numeric([Q(z) for z in xi0]),quadratic_a=[1,3],quadratic_b=[-1,2],
          local_objective='f_c(theta)=a_c*theta^2/2+b_c*theta; global f=(f_1+f_2)/2',
          stochastic_objective='F_c(theta,z)=f_c(theta)+z*theta; grad F_c=a_c*theta+b_c+z',
          noise=numeric(noise),randomness='Each z independently equals +/-0.25 equiprobably; condition on given [round][local_step][client] draws.',
          network='Two clients, central server, full participation every round, equal weights.'),
       parameters=dict(gamma=.05,H=H,rounds=3,control_convention='The paper xi enters the gradient with a PLUS sign and xi_next=xi+(local_endpoint-global_next)/(gamma*H). xi is fixed during all H local steps and updated only after global aggregation. sum(xi_initial)=0.',
          observation_timing='step=t+1 represents round t. theta_before,xi_before precede local reset. local_theta rows h=0..H and columns clients; sample_gradient and corrected_gradient rows h=0..H-1 at pre-update local theta. theta_after is mean of local endpoints. xi_after is after Eq.(5).'),
       atol=1e-12,rtol=1e-12,expected=entries,
       derivation='From PDF p.3 Eq.(4): theta_local<-theta_local-gamma*(a_c*theta_local+b_c+z+xi_c), with xi fixed for H steps. Average all local endpoints for theta_next; apply Eq.(5) xi_next=xi+(endpoint-theta_next)/(gamma*H). Reinitialize local theta to new global theta next round, preserving xi. All arithmetic uses Fraction, and zero sum is asserted exactly at each round.')
def build():
    return dict(schema_version='optirepro.paper_algorithm_contract.v1',
      paper=dict(paper_id='2503.07594',title='Scaffold with Stochastic Gradients: New Analysis with Linear Speed-Up',sha256='e35ce132f53c9d957958b85c564b042a0431c1c3571dc7db6b18c40686bb50e0'),
      algorithm=dict(name='SCAFFOLD, Algorithm 1 with centered persistent xi',citations=['PDF p.3 Algorithm 1, Eqs.(4)-(5)','PDF pp.2-3 assumptions A1-A5'],core_mechanisms=MECH,
        assumptions=['Strongly convex smooth scalar quadratics; bounded additive iid gradient noise; full client participation.','Control vectors have zero sum initially and retain zero sum.','This is an analysis paper; these tests instantiate its stated SCAFFOLD, not a newly invented algorithm.']),
      cases=[make_case('zero_control_H2','4/5',['0','0'],2),make_case('nonzero_centered_control_H3','-2/5',['1/2','-1/2'],3)])
if __name__=='__main__':Path(__file__).with_name('contract.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
