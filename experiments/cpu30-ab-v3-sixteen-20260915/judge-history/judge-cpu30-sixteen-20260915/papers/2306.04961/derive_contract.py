#!/usr/bin/env python3
"""Independent paper-only 70-digit IRLS derivation; reads no files."""
import json
from decimal import Decimal as D,getcontext
getcontext().prec=70
Z=D(0);O=D(1)
def mat(a): return [[D(str(v)) for v in r] for r in a]
def eye(n): return [[O if i==j else Z for j in range(n)] for i in range(n)]
def trans(a):return list(map(list,zip(*a)))
def mv(a,x):return [sum(v*w for v,w in zip(r,x)) for r in a]
def mm(a,b):return [mv(trans(b),r) for r in a]
def solve(a,b):
 a=[r[:]+[v] for r,v in zip(a,b)];n=len(b)
 for i in range(n):
  piv=max(range(i,n),key=lambda j:abs(a[j][i]));a[i],a[piv]=a[piv],a[i]
  q=a[i][i];assert q!=0;a[i]=[v/q for v in a[i]]
  for j in range(n):
   if j!=i:
    q=a[j][i];a[j]=[v-q*w for v,w in zip(a[j],a[i])]
 return [r[-1] for r in a]
def eigvals(a):
 disc=((a[0][0]-a[1][1])**2+4*a[0][1]**2).sqrt();return [(a[0][0]+a[1][1]+disc)/2,(a[0][0]+a[1][1]-disc)/2]
def filt(a,eps):
 hi,lo=eigvals(a);assert hi>lo>0
 wh=min(O,eps/hi.sqrt());wl=min(O,eps/lo.sqrt())
 # Spectral calculus: f(A)=wl I+(wh-wl)(A-lo I)/(hi-lo).
 return [[wl*(i==j)+(wh-wl)*(a[i][j]-lo*(i==j))/(hi-lo) for j in range(2)] for i in range(2)]
def num(x):return [num(v) for v in x] if isinstance(x,list) else float(x)
cases=[]
for cid,A,y,target in [('row_one_recovery',[[1,0,0,2],[0,1,1,0],[1,0,0,-1]],[2,1,2],[[2,1],[0,0]]),('row_two_recovery',[[1,1,0,1],[0,1,2,-1]],[2,0],[[0,0],[1,2]])]:
 inp={'matrix_shape':[2,2],'vectorization':'row-major: [X11,X12,X21,X22]','measurement_matrix':A,'measurements':y,'feasible_structured_example':target,'objective':'At each iteration minimize <X,W_previous(X)> subject to A vec(X)=y','randomness':'none'}
 A=mat(A);y=list(map(D,y));W=eye(4);eps=D('Infinity');delta=D('Infinity');out=[];trace=[]
 for step in range(1,4):
  # W^-1 A^T (A W^-1 A^T)^-1 y, Eq. (3.1).
  WinvAt=trans([solve(W,row) for row in A]);lam=solve(mm(A,WinvAt),y);x=mv(WinvAt,lam);X=[x[:2],x[2:]]
  assert max(abs(a-b) for a,b in zip(mv(A,x),y))<D('1e-60')
  XXt=mm(X,trans(X));XtX=mm(trans(X),X);sigma=[v.sqrt() for v in eigvals(XXt)];rows=[sum(v*v for v in r).sqrt() for r in X]
  eps=min(eps,sigma[1]);delta=min(delta,min(rows));L=filt(XXt,eps);R=filt(XtX,eps);sp=[min(O,delta**2/(q*q)) for q in rows]
  def weight(v):
   Q=[v[:2],v[2:]];lr=mm(mm(L,Q),R)
   return [lr[i][j]+sp[i]*Q[i][j] for i in range(2) for j in range(2)]
  W=trans([weight(col) for col in eye(4)])
  for name,val in [('X',X),('singular_values',sigma),('row_norms',rows),('epsilon',eps),('delta',delta),('low_rank_left',L),('low_rank_right',R),('row_weight_diagonal',sp),('weight_operator',W)]:out.append({'step':step,'name':name,'value':num(val)})
  trace.append(f'k={step}: X={num(X)}, epsilon={float(eps)}, delta={float(delta)}, row weights={num(sp)}')
 cases.append({'id':cid,'purpose':'Recover a row-sparse rank-one feasible matrix through three nontrivial constrained weighted solves, with distinct spectral and row weights, left/right spectral factors and updated smoothing.','covers':['equality-constrained-weighted-least-squares','two-sided-spectral-reweighting','row-sparsity-reweighting','monotone-smoothing-update'],'inputs':inp,'parameters':{'rank_estimate':1,'row_sparsity_estimate':1,'iterations':3,'initial_weight_operator':'identity on R^(2x2), as mandated by Algorithm 2.1','initial_epsilon':'positive infinity','initial_delta':'positive infinity','observation_timing':'step k records X^(k) after weighted minimization and all singular values, row norms, smoothing and weights computed FROM that X after steps 5-6 of Algorithm 2.1','spectral_weight_convention':'left/right factors have eigenvalues min(epsilon/sigma_i,1); W_lr(Z)=L Z R; W_sp is left row scaling; W=W_lr+W_sp. Operator matrix uses row-major coordinates.'},'derivation':'70-digit Decimal evaluation of paper Eqs. (2.4)-(2.8), (3.1). For each 2x2 Gram matrix, compute eigenvalues (trace +/- sqrt((a-c)^2+4b^2))/2 and spectral filter by degree-one interpolation, independent of singular-vector signs. Weighted equality solution uses direct Gaussian elimination. Initial W=I; then epsilon=min(old epsilon,sigma_2), delta=min(old delta,second largest row norm). Distinct nontrivial L,R and row weights are recomputed at every iteration. '+ '; '.join(trace),'expected':out,'atol':1e-10,'rtol':1e-8})
print(json.dumps({'schema_version':'optirepro.paper_algorithm_contract.v1','paper':{'paper_id':'2306.04961','title':'Recovering Simultaneously Structured Data via Non-Convex Iteratively Reweighted Least Squares','sha256':'6486027b50634a90a4ebd40cf40c6b1cca4c32cdbd133dfbfea499fb523aaf48'},'algorithm':{'name':'Algorithm 2.1: IRLS for simultaneously low-rank and row-sparse matrices','citations':['PDF p.5 Definition 2.1, Eqs. (2.2)-(2.6)','PDF p.6 Algorithm 2.1, Eqs. (2.7)-(2.8)','PDF p.8 Eq. (3.1)'], 'core_mechanisms':['equality-constrained-weighted-least-squares','two-sided-spectral-reweighting','row-sparsity-reweighting','monotone-smoothing-update'],'assumptions':['Use the row-sparsity variant, no optional additional column-sparsity term.','Both rank and sparsity estimates are 1, so the printed inconsistent rank/sparsity subscript in Eq. (2.8) coincides and requires no inferred correction.','Initial weight is identity because Algorithm 2.1 explicitly requires it; subsequent operators are nonidentity and both structural penalties are active.','All three iterates are full rank with positive second row norm and smoothing, so zero-smoothing termination is outside scope.','Finite deterministic operator tests do not certify RIP, asymptotic recovery rate or sample complexity.']},'cases':cases},ensure_ascii=False,indent=2))
