#!/usr/bin/env python3
"""Paper-only Decimal derivation; no repository/implementation input. Emits private JSON."""
import json
from decimal import Decimal as D, getcontext
getcontext().prec=70

def mat(a): return [[D(str(v)) for v in r] for r in a]
def mv(a,x): return [sum(v*w for v,w in zip(r,x)) for r in a]
def trans(a): return list(map(list,zip(*a)))
def mm(a,b): return [mv(trans(b),r) for r in a]
def solve(a,b):
 a=[r[:]+[v] for r,v in zip(a,b)]; n=len(b)
 for i in range(n):
  q=a[i][i]; a[i]=[v/q for v in a[i]]
  for j in range(n):
   if j!=i:
    q=a[j][i]; a[j]=[x-q*y for x,y in zip(a[j],a[i])]
 return [r[-1] for r in a]
def num(x):
 if isinstance(x,list): return [num(v) for v in x]
 return float(x)
K=mat([[.75,.25,0],[0,.75,.25],[.25,0,.75]])
G=mat([[-1,1,0],[0,-1,1],[1,0,-1]])
cases=[]
for cid,u,z,f,mu,beta in [('mixed_threshold',[0,1,1.2],[1,0,.5],[.5,1.5,-.25],'.2','1'),('signed_reweight',[2,-1,.5],[-.01,1,.2],[1,-.5,2],'.8','.5')]:
 inp={'image_shape':[1,3],'flatten_order':'row-major','K':num(K),'gradient_matrix':num(G),'boundary':'periodic forward difference on the three pixels','u0':u,'z0':z,'f':f,'objective':'0.5*||K u-f||_2^2 + mu*sum_i |z_i|^p + beta/2*||z-G u||_2^2','randomness':'none'}
 u=list(map(lambda v:D(str(v)),u));z=list(map(lambda v:D(str(v)),z));f=list(map(lambda v:D(str(v)),f));mu=D(mu);beta=D(beta);p=D('.1');eps=D('.01')
 M=[[x+beta*y for x,y in zip(r,s)] for r,s in zip(mm(trans(K),K),mm(trans(G),G))];ktf=mv(trans(K),f); out=[]; arithmetic=[]
 for step in range(1,4):
  bar=mv(G,u); thresholds=[p*mu/beta/(abs(v)+eps)**(1-p) for v in z]
  z=[(D(1) if v>0 else D(-1) if v<0 else D(0))*max(D(0),abs(v)-t) for v,t in zip(bar,thresholds)]
  rhs=[v+beta*w for v,w in zip(ktf,mv(trans(G),z))];u=solve(M,rhs)
  objective=sum(v*v for v in [v-w for v,w in zip(mv(K,u),f)])/2+mu*sum(abs(v)**p for v in z)+beta*sum((v-w)**2 for v,w in zip(z,mv(G,u)))/2
  for name,val in [('gradient_before',bar),('thresholds',thresholds),('z',z),('u',u),('objective',objective)]: out.append({'step':step,'name':name,'value':num(val)})
  arithmetic.append(f'iteration {step}: bar={num(bar)}, thresholds={num(thresholds)}, z={num(z)}, u={num(u)}')
 cases.append({'id':cid,'purpose':'Exercise changing IRL1 weights, signed/zero soft-threshold branches and a coupled nonidentity blur/gradient linear solve for three complete AM iterations.','covers':['previous-z-reweighting','signed-soft-threshold','alternating-blur-solve'],'inputs':inp,'parameters':{'mu':float(mu),'beta':float(beta),'p':.1,'L':1,'epsilon':.01,'iterations':3,'variant':'Algorithm 1 PIRL1-AM, not accelerated','weight_base':'previous z_k as printed in Eq. (12) and Algorithm 1, not bar_z_k in Eq. (11)','bar_z_definition':'G @ u_k','observation_timing':'step j is full iteration k=j-1; gradient_before and thresholds are computed before z update; z,u,objective are after their respective updates; objective uses updated z and u'},'derivation':'70-digit Decimal arithmetic. Eq. (12): threshold_i=p*mu/(L*beta)*(abs(z_old_i)+epsilon)^(p-1); z_new=sign(G*u_old)*max(abs(G*u_old)-threshold,0). Eq. (14) solved by exact-arithmetic-form Gaussian elimination on the stated 3x3 matrix. '+ '; '.join(arithmetic),'expected':out,'atol':1e-10,'rtol':1e-9})
print(json.dumps({'schema_version':'optirepro.paper_algorithm_contract.v1','paper':{'paper_id':'2309.05204','title':'Accelerated Proximal Iterative re-Weighted ℓ1 Alternating Minimization for Image Deblurring','sha256':'67b486882088b75001d71389caaedb3baea251ddc2296f333addda4678ea22a1'},'algorithm':{'name':'PIRL1-AM (Algorithm 1 only; accelerated Algorithm 2 is outside verified scope)','citations':['PDF p.2 Eq. (3), (7), (12), (14)','PDF p.3 Algorithm 1'], 'core_mechanisms':['previous-z-reweighting','signed-soft-threshold','alternating-blur-solve'],'assumptions':['Only the explicitly stated nonaccelerated Algorithm 1 is evaluated. The paper title emphasizes APIRL1-AM, but Algorithm 2 computes y without specifying its feedback into the printed z/u updates; that acceleration mechanism is not uniquely determined and is not claimed covered.','The Eq. (12)/Algorithm 1 denominator is based on previous z, resolving the conflicting bar-z denominator in Eq. (11) by selecting the final explicit pseudocode.','A three-pixel periodic 1D image is a deterministic finite-dimensional instance of the stated linear-operator model; K and gradient are explicitly supplied.','epsilon=0.01 is an explicitly fixed positive smoothing value for numerical separation of threshold branches; no noise generation, clipping, continuation, FFT normalization or early stopping.']},'cases':cases},ensure_ascii=False,indent=2))
