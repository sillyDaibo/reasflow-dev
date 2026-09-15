#!/usr/bin/env python3
"""Original-paper-only Decimal derivation on St(2,1); no file inputs."""
import json
from decimal import Decimal as D,getcontext
getcontext().prec=70
ZERO=D(0);ONE=D(1)
def dv(a):return [D(str(v)) for v in a]
def dot(a,b):return sum(v*w for v,w in zip(a,b))
def mv(a,x):return [dot(r,x) for r in a]
def num(v):return [num(w) for w in v] if isinstance(v,list) else float(v)
def col(x):return [[v] for v in x]
def run(cid,Q,c,x,mu,delta,sigma):
 raw={'manifold':'St(2,1), embedded Euclidean metric','X0':[[v] for v in x],'Q':Q,'linear_c':c,'mu':mu,'smooth_objective':'f(X)=0.5*X^T Q X + c^T X','nonsmooth_objective':'h(X)=mu*(abs(X_1)+abs(X_2))','randomness':'none'}
 Q=[dv(r) for r in Q];c=dv(c);x=dv(x);mu=D(str(mu));delta=D(str(delta));sigma=D(str(sigma));gam=D('.5');hist=[];out=[];trace=[];prev_x=prev_g=None
 def grad(x):return [v+w for v,w in zip(mv(Q,x),c)]
 def rgrad(x):
  g=grad(x);d=dot(x,g);return [v-d*w for v,w in zip(g,x)]
 def obj(x):return dot(x,mv(Q,x))/2+dot(c,x)+mu*sum(abs(v) for v in x)
 for k in range(3):
  g=rgrad(x)
  if k==0:B=[[ONE,ZERO],[ZERO,ONE]];damp=ONE
  else:
   s=[v-w for v,w in zip(x,prev_x)];y=[v-w for v,w in zip(g,prev_g)];ss=dot(s,s);sy=dot(s,y)
   assert ss>D('1e-50')
   damp=D('.75')*delta*ss/(delta*ss-sy) if sy<D('.25')*delta*ss else ONE
   ybar=[damp*v+(1-damp)*delta*w for v,w in zip(y,s)];syb=dot(s,ybar)
   B=[[delta*(i==j)-delta*s[i]*s[j]/ss+ybar[i]*ybar[j]/syb for j in range(2)] for i in range(2)]
  t=[-x[1],x[0]];a=dot(grad(x),t);b=sum(t[i]*B[i][i]*t[i] for i in range(2))
  candidates=[-x[i]/t[i] for i in range(2) if t[i]!=0]
  # Enumerate smooth sign-region stationary points plus the two nonsmooth knots.
  for p in [-1,1]:
   for q in [-1,1]:
    z=-(a+mu*(p*t[0]+q*t[1]))/b
    if p*(x[0]+z*t[0])>=0 and q*(x[1]+z*t[1])>=0:candidates.append(z)
  def model(z):return a*z+b*z*z/2+mu*sum(abs(v+z*w) for v,w in zip(x,t))
  z=min(candidates,key=model);v=[z*w for w in t];normb=b*z*z
  assert abs(dot(x,v))<D('1e-60')
  hist.append(obj(x));reference=max(hist[max(0,k-1):k+1]);alpha=ONE;rejected=0;trials=[]
  while True:
   xn=[a+alpha*b for a,b in zip(x,v)];norm=dot(xn,xn).sqrt();xn=[v/norm for v in xn];fn=obj(xn);rhs=reference-sigma*alpha*normb/2;trials.append((float(alpha),float(fn),float(rhs)))
   if fn<=rhs:break
   alpha*=gam;rejected+=1;assert rejected<40
  assert abs(dot(xn,xn)-1)<D('1e-60')
  step=k+1
  vals=[('X_before',col(x)),('riemannian_gradient',col(g)),('B_matrix',B),('metric_diagonal',[B[0][0],B[1][1]]),('damping_beta',damp),('V',col(v)),('tangent_metric_norm_squared',normb),('line_search_reference',reference),('alpha',alpha),('backtracks',D(rejected)),('X',col(xn)),('objective',fn)]
  for name,val in vals:out.append({'step':step,'name':name,'value':num(val)})
  trace.append(f'k={k}: beta={float(damp)}, diagB={num([B[0][0],B[1][1]])}, tangent scalar={float(z)}, trials(alpha,F,bound)={trials}, Xnew={num(xn)}')
  prev_x=x;prev_g=g;x=xn
 return {'id':cid,'purpose':'Three complete ManPQN iterations with an active l1 proximal tangent solve, diagonal damped BFGS curvature, polar retraction, and nonmonotone Armijo backtracking.','covers':['tangent-proximal-subproblem','diagonal-damped-lbfgs','polar-retraction','nonmonotone-armijo'],'inputs':raw,'parameters':{'iterations':3,'memory_p':1,'delta':float(delta),'sigma':float(sigma),'gamma':.5,'nonmonotone_m':1,'B0':'identity as required by Algorithm 1','curvature_initialization_each_k_ge_1':'B_k,0=delta*I, retain exactly the most recent pair','curvature_pairs':'s=X_k-X_(k-1); y=grad f(X_k)-grad f(X_(k-1)) using Riemannian smooth gradients, Eqs. (2.1),(2.2)','metric':'Use diag(B_k), projected as Eq. (3.7), not full B_k in the subproblem','retraction':'polar/SVD: R_X(V)=(X+V)/sqrt((X+V)^T(X+V)) for r=1','inner_solver':'exact minimizer of Eq. (3.6); do not use approximate inner stopping','stopping':'exactly 3 iterations, no early stopping','observation_timing':'step j means k=j-1. X_before,g,B,beta,V,norm and reference precede retraction; alpha/backtracks are accepted line search results; X and objective are after retraction. At k=0 damping_beta=1 is a neutral no-pair sentinel.'},'derivation':'70-digit Decimal original-paper derivation. On St(2,1), V=z*t with t=(-x2,x1). Minimize a*z+0.5*b*z^2+mu*sum_i|x_i+z*t_i| by all valid sign-region stationary points and knots; a=grad_f dot t and b=t^T diag(B)t. Compute damped memory-one BFGS exactly by Eqs. (3.9)-(3.10). Test alpha=1,1/2,... against max(F(X_k),F(X_(k-1)))-sigma*alpha*norm_B(V)^2/2 using polar retraction. '+ '; '.join(trace),'expected':out,'atol':1e-9,'rtol':1e-8}
cases=[run('quadratic_l1',[[12,1.5],[1.5,3]],[0,0],[.6,.8],.2,1,.5),run('indefinite_l1',[[1,1],[1,-2]],[.5,-.2],[.8,.6],.3,2,.5)]
print(json.dumps({'schema_version':'optirepro.paper_algorithm_contract.v1','paper':{'paper_id':'2501.09516','title':'Proximal Quasi-Newton Method for Composite Optimization over the Stiefel Manifold','sha256':'760d1ac9d4201cf630b174585acf192612eacd60ac39c4a0eb3155c89d62d0cc'},'algorithm':{'name':'ManPQN Algorithm 1 with diagonal damped LBFGS, memory one','citations':['PDF p.4 Eqs. (2.1)-(2.2)','PDF pp.6-7 Eqs. (3.1)-(3.4) and Algorithm 1','PDF pp.8-9 Eqs. (3.6)-(3.10)','PDF p.21 SVD retraction choice'],'core_mechanisms':['tangent-proximal-subproblem','diagonal-damped-lbfgs','polar-retraction','nonmonotone-armijo'],'assumptions':['Use St(2,1), exact tangent subproblem solve and memory p=1; this is the smallest nontrivial curved Stiefel case with nonsmooth h and anisotropic diagonal curvature.','Algorithm 1 requires identity only on initial k=0; every later curvature is independently updated, and no fixed identity surrogate is substituted.','Only the prescribed finite iterates are tested, not semismooth-Newton inner iteration details, r>1 matrix-column interactions or global/local convergence rates.','This is an explicitly requested exact-inner-solve specialization. The paper defines V by argmin but its numerical procedure uses ASSN and a maximum of 100 inner iterations (pp.10-11 and pp.20-21), without a complete uniquely specified inner accuracy policy in the supplied text. A valid implementation using a permitted inexact inner solve can therefore return a different trajectory; mismatch against this exact-direction contract alone must not be labeled a general ManPQN algorithm error.','Use the practical Euclidean secant and diagonal approximation Eqs. (3.6)-(3.10), not the vector-transported theoretical formula (3.5).']},'cases':cases},ensure_ascii=False,indent=2))
