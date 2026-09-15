"""Independent exact arithmetic for paper Algorithm 2 and PPS (1). No repository inputs."""
from fractions import Fraction as F
import json
from pathlib import Path

def frac(x):return [frac(a) for a in x] if isinstance(x,list) else F(str(x))
def num(x):return [num(a) for a in x] if isinstance(x,list) else float(x)
def add(x,y):return [a+b for a,b in zip(x,y)]
def sub(x,y):return [a-b for a,b in zip(x,y)]
def mul(a,x):return [a*b for b in x]

def case(id,q0,c0,adiag0,b0,up0,un0):
 q,c,ad,b,up,un=map(frac,[q0,c0,adiag0,b0,up0,un0]);alpha=frac([1,1,1.5,2]);beta=frac([4,5,6,7]);M=2
 def restore(mu):return [ci-ai*mi/qi for qi,ci,ai,mi in zip(q,c,ad,mu)]
 def oracle(mu):return [bi-ai*xi for bi,ai,xi in zip(b,ad,restore(mu))]
 def pps(raw,k):
  pos=[max(F(0),v) for v in raw];neg=[max(F(0),-v) for v in raw];pm,nm=sum(pos),sum(neg)
  assert pm>0 and nm>0, 'Fixture deliberately avoids zero-mass categorical ambiguity'
  def draw(weights,mass,us):
   ids=[]
   for u in us:
    cumulative=F(0)
    for j,w in enumerate(weights):
     cumulative+=w/mass
     if u<cumulative: ids.append(j);break
    else:raise AssertionError('invalid categorical draw')
   return ids
  ki,li=draw(pos,pm,up[k]),draw(neg,nm,un[k]);compressed=[pm*ki.count(j)/M-nm*li.count(j)/M for j in range(3)]
  return compressed,[pm,nm],ki,li
 mu=[F(0)]*3;raw=oracle(mu);G,masses,ki,li=pps(raw,0)
 lam=mul(-alpha[0]/beta[0],G);acc=alpha[0];weighted_g=mul(alpha[0],G);weighted_x=mul(alpha[0],restore(mu));ex=[];trace=[]
 def put(s,n,v):ex.append({'step':s,'name':n,'value':num(v)});trace.append(f'{s}:{n}={v}')
 for n,v in [('mu',mu),('oracle_g',raw),('PPS_G',G),('lambda',lam),('positive_negative_mass',masses),('sampled_positive_indices',ki),('sampled_negative_indices',li)]:put(0,n,v)
 for t in range(3):
  z=mul(-1/beta[t],weighted_g);accnext=acc+alpha[t+1];tau=alpha[t+1]/accnext
  mun=add(mul(tau,z),mul(1-tau,lam));raw=oracle(mun);Gn,masses,ki,li=pps(raw,t+1)
  muhat=sub(z,mul(alpha[t+1]/beta[t],Gn));lamn=add(mul(tau,muhat),mul(1-tau,lam))
  weighted_x=add(weighted_x,mul(alpha[t+1],restore(mun)));primal=mul(1/accnext,weighted_x)
  residual=[ai*xi-bi for ai,xi,bi in zip(ad,primal,b)];obj=sum(qi*(xi-ci)**2/2 for qi,xi,ci in zip(q,primal,c))
  for n,v in [('z_used',z),('mu',mun),('oracle_g',raw),('positive_negative_mass',masses),('sampled_positive_indices',ki),('sampled_negative_indices',li),('PPS_G',Gn),('mu_hat',muhat),('lambda',lamn),('restored_primal_at_mu',restore(mun)),('primal_average',primal),('constraint_residual',residual),('primal_objective',obj)]:put(t+1,n,v)
  weighted_g=add(weighted_g,mul(alpha[t+1],Gn));lam,acc=lamn,accnext
 return {'id':id,'purpose':'Check signed PPS categorical quantization inside the accelerated primal-dual recursion, varying beta, and weighted primal restoration across initialization and three updates.','covers':['signed_pps_quantization','weighted_dual_accumulation','accelerated_dual_updates','weighted_primal_restoration'],
 'inputs':{'network':'Algorithm 2 is the generic affine-constrained primal-dual method, evaluated centrally; no gossip matrix or decentralized Algorithm 3 is used.','primal_objective':'f(x)=sum_j q_j*(x_j-c_j)^2/2 on R^3, subject to A*x=b; A=diag(A_diagonal).','q':q0,'c':c0,'A_diagonal':adiag0,'b':b0,'conjugate':'f_star(v)=sum_j(c_j*v_j+v_j^2/(2*q_j)); exact deterministic stochastic oracle F_star=f_star.','dual_objective':'phi(mu)=dot(mu,b)+f_star(-A^T*mu).','primal_restoring_function':'x(-A^T*mu)=c-diag(A_diagonal/q)*mu.','oracle':'g(mu)=b-A*x(-A^T*mu)=b-A*c+diag(A_diagonal^2/q)*mu; r=1 at all calls, no xi noise.','initialization':'mu0=[0,0,0]; draw PPS at mu0; lambda0=-alpha0/beta0*G0; A0=alpha0.','positive_uniforms':up0,'negative_uniforms':un0,'randomness':'At each oracle call k=0,1,2,3 use the corresponding two uniforms for positive and negative signs. For weights max(g,0) and max(-g,0), choose smallest zero-based index whose normalized cumulative weight is strictly greater than u. Use all two draws with replacement separately per sign, and PPS=sum_positive_mass/2*counts_positive-sum_negative_mass/2*counts_negative. Both masses remain positive in these fixtures. No other randomness.','observations':'step0 is initialization after the first PPS call and lambda0. step s=t+1 is after completing the t-th loop. z_used uses beta_t and weighted G0..Gt; mu, PPS_G, mu_hat, lambda correspond to subscript t+1; restored_primal_at_mu uses unquantized restoring function at mu_{t+1}; primal_average includes alpha0*x(-A^T*mu0) through alpha_{t+1}*x(-A^T*mu_{t+1}), divided by their sum. Residual and objective are evaluated at that average.','scope_limitation':'This smooth quadratic fixture checks finite algebraic recurrences. Its dual gradient is bounded on the visited points, but not uniformly on all R^3; it therefore does not instantiate the global bounded-oracle hypothesis of Section 2 or validate the large-deviation theorems.'},
 'parameters':{'T':3,'alpha':[1,1,1.5,2],'beta':[4,5,6,7],'beta_minus_one_for_coefficient_condition':4,'r':[1,1,1,1],'M':[2,2,2,2],'dual_gradient_L':1,'uniform_draw_interpretation':'Exact decimals in [0,1); no PRNG seed semantics.'},'atol':1e-10,'rtol':1e-10,'expected':ex,
 'derivation':'PDF p.7 equation (1), p.8 equations (3),(5), p.11 Algorithm 2. The conjugate follows by maximizing each scalar quadratic; derivative is c+v/q. All algebra, CDF comparisons, and weighted sums use exact Fraction arithmetic. Coefficients obey alpha0 in (0,1], beta increasing and >L, alpha_t^2 beta_t <= beta_(t-1) sum_(i=0)^t alpha_i. '+ '\n'.join(trace)}

def build():
 return {'schema_version':'optirepro.paper_algorithm_contract.v1','paper':{'paper_id':'2501.18312','title':'Decentralised convex optimisation with probability-proportional-to-size quantization','sha256':'65ac545e80f254228f3678602b8c08626f469816c43c524769c2043d8c4e2566'},'algorithm':{'name':'PPS Primal-dual method (Algorithm 2)','citations':['PDF pp.6-7, Section 2 and PPS equation (1)','PDF pp.8-9, Section 3, equations (2)-(6)','PDF p.11, Algorithm 2 and coefficient conditions'],'core_mechanisms':['signed_pps_quantization','weighted_dual_accumulation','accelerated_dual_updates','weighted_primal_restoration'],'assumptions':['Three-dimensional smooth strongly convex primal quadratics and positive-definite diagonal affine A.','Exact zero-noise conjugate oracle and fixed supported PPS uniform draws; both sign masses stay positive.','Coefficient inequalities following Algorithm 2 hold with dual gradient Lipschitz bound L=1.','Finite algebraic validation only: quadratics do not satisfy the paper global uniform bounded-oracle hypothesis, so no probabilistic convergence theorem is asserted.','The decentralized Algorithm 3, barycenter specialization, and Algorithm 1 are outside the tested scope.']},'cases':[case('pps_two_positive_coordinates',[1,1,1],[-2,-1,3],[1,1,1],[0,0,0],[[0.1,0.2],[0.1,0.9],[0.6,0.8],[0.2,0.7]],[[0.2,0.6],[0.4,0.8],[0.1,0.7],[0.3,0.9]]),case('pps_two_negative_coordinates',[2,4,2],[3,-2,1],[1,2,1],[0.5,-0.5,0.25],[[0.1,0.8],[0.2,0.7],[0.3,0.9],[0.1,0.6]],[[0.1,0.2],[0.1,0.95],[0.85,0.95],[0.15,0.8]])]}
if __name__=='__main__':Path(__file__).with_name('contract.json').write_text(json.dumps(build(),indent=2,ensure_ascii=False)+'\n')
