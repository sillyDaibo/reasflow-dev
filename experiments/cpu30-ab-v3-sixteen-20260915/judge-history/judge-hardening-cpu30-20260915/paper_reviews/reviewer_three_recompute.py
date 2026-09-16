#!/usr/bin/env python3
"""Reproduce reviewer-three paper-only arithmetic for ADMM, ProxRR/FedRR and BEER.
Run from any working directory with Python 3. Uses only the standard library.
Reads the frozen private contracts, designated original PDFs and contract schema.
Writes reviewer_three_recompute_results.json beside this script. Does not modify
contracts, review decisions or production code. Decimal arithmetic uses 95 digits.
"""
from decimal import Decimal as D, getcontext
from pathlib import Path
import json, hashlib, importlib.util
getcontext().prec=95
ROOT=Path(__file__).resolve().parents[3]
def dec(v):
 if isinstance(v,list): return [dec(z) for z in v]
 return D(str(v))
def zeros(n,d): return [[D(0) for _ in range(d)] for _ in range(n)]
def cholsolve(a,b):
 n=len(b);l=zeros(n,n)
 for i in range(n):
  for j in range(i+1):
   r=a[i][j]-sum(l[i][k]*l[j][k] for k in range(j))
   l[i][j]=r.sqrt() if i==j else r/l[j][j]
 y=[]
 for i in range(n): y.append((b[i]-sum(l[i][k]*y[k] for k in range(i)))/l[i][i])
 x=[D(0)]*n
 for i in reversed(range(n)): x[i]=(y[i]-sum(l[k][i]*x[k] for k in range(i+1,n)))/l[i][i]
 return x

def enet(v,alpha,l1,l2):
 # Solve the scalar subgradient inclusion by active sign, rather than a shared soft-threshold helper.
 out=[]
 for u in v:
  if -alpha*l1<=u<=alpha*l1: out.append(D(0))
  elif u>0: out.append((u-alpha*l1)/(1+alpha*l2))
  else: out.append((u+alpha*l1)/(1+alpha*l2))
 return out

def admm(c):
 inp,p=c['inputs'],c['parameters'];K=len(inp['L']);n=p['parameter_dimension'];lam=D(str(p['lambda']));r=D(str(inp['regularizer']['coefficient']));L=dec(inp['L']);h=zeros(K,n);u=zeros(K,n);ut=zeros(K,n);obs={}
 A=[[lam*L[i][j]+2*(i==j) for j in range(K)] for i in range(K)]
 for s in range(1,p['iterations']+1):
  th=[];tt=[]
  for k in range(K):
   v=[h[k][j]-u[k][j] for j in range(n)]
   if inp['loss']['type']=='quadratic':
    Q=dec(inp['loss']['Q'][k]);b=dec(inp['loss']['b'][k]);th.append(cholsolve([[Q[i][j]+D(i==j)/lam for j in range(n)] for i in range(n)],[v[j]/lam-b[j] for j in range(n)]))
   else:
    N=D(inp['loss']['counts'][k]);S=D(inp['loss']['sums'][k]);z=D(1)
    # Damped Newton on strictly convex proximal objective derivative; no closed-form square root or bisection.
    for _ in range(150):
     f=N-S/z+(z-v[0])/lam;delta=f/(S/(z*z)+1/lam);scale=D(1)
     while z-scale*delta<=0: scale/=2
     zn=z-scale*delta
     if abs(zn-z)<D('1e-85'): z=zn;break
     z=zn
    assert abs(N-S/z+(z-v[0])/lam)<D('1e-80')
    th.append([z])
   vt=[h[k][j]-ut[k][j] for j in range(n)]
   tt.append(enet(vt,lam,r if inp['regularizer']['type']=='l1' else D(0),r if inp['regularizer']['type']=='ridge' else D(0)))
  nh=zeros(K,n)
  for j in range(n):
   sol=cholsolve(A,[th[k][j]+tt[k][j]+u[k][j]+ut[k][j] for k in range(K)])
   for k in range(K):nh[k][j]=sol[k]
  u=[[u[k][j]+th[k][j]-nh[k][j] for j in range(n)] for k in range(K)];ut=[[ut[k][j]+tt[k][j]-nh[k][j] for j in range(n)] for k in range(K)];h=nh
  for name,val in [('theta',th),('theta_tilde',tt),('theta_hat',h),('u',u),('u_tilde',ut)]:obs[s,name]=val
 return obs

def exp_series(x):
 # Independent high precision exponential: range reduction, Taylor sum, repeated squaring.
 x=x/64; term=D(1);res=term
 for k in range(1,1000):
  term=term*x/k;res+=term
  if abs(term)<D('1e-92'):break
 for _ in range(6):res*=res
 return res

def rr(c):
 i,p=c['inputs'],c['parameters'];x=dec(i['x0']);obs={};l1=D(str(p['lambda1']));l2=D(str(p['lambda2']))
 def path(start,order,g,diag=None,cen=None):
  v=start[:];trace=[]
  for idx in order:
   if diag is None:
    a=dec(i['features'][idx]);dot=sum(a[j]*v[j] for j in range(len(v)));y=2*i['labels'][idx]-1
    # signed-label loss log(1+exp(-y*dot)), equivalent to paper's {0,1} formulation.
    mult=-D(y)/(1+exp_series(D(y)*dot));v=[v[j]-g*mult*a[j] for j in range(len(v))]
   else:
    v=[(1-g*D(str(diag[idx][j])))*v[j]+g*D(str(diag[idx][j]))*D(str(cen[idx][j])) for j in range(len(v))]
   trace.append(v[:])
  return trace
 for s in range(1,p['epochs']+1):
  if p['algorithm']=='ProxRR':
   g=D(str(p['epoch_stepsizes'][s-1]));tr=path(x,i['epoch_sample_orders'][s-1],g,i.get('diagonals'),i.get('centers'));obs[s,'inner_iterates']=tr;x=enet(tr[-1],p['n']*g,l1,l2)
  else:
   g=D(str(p['stepsize']));trs=[path(x,o,g,i['client_diagonals'][m],i['client_centers'][m]) for m,o in enumerate(i['epoch_client_sample_orders'][s-1])];ends=[t[-1] for t in trs];mean=[sum(v[j] for v in ends)/p['M'] for j in range(len(x))];obs[s,'local_after_first_sample']=[t[0] for t in trs];obs[s,'local_endpoints']=ends;obs[s,'aggregate']=mean;x=enet(mean,g*p['N']/p['M'],l1,l2)
  obs[s,'iterate']=x
 return obs

def beer(c):
 i,p=c['inputs'],c['parameters'];w=dec(i['mixing_matrix_W']);a=dec(i['quadratic_centers_by_client']);di=dec(i['quadratic_diagonals_by_client']);n=len(w);d=len(a[0]);x=[dec(i['initial_common_point']) for _ in range(n)];h=zeros(n,d);g=zeros(n,d);v=[[di[k][j]*(x[k][j]-a[k][j]) for j in range(d)] for k in range(n)];eta=D(str(p['eta']));gamma=D(str(p['gamma']));obs={}
 def compressed(z):
  if p['compressor']['name']=='scale':return [D(str(p['compressor']['factor']))*q for q in z]
  ix=max(range(d),key=lambda j:abs(z[j]));return [z[j] if j==ix else D(0) for j in range(d)]
 for s in range(p['iterations']+1):
  for name,val in [('X',x),('H',h),('V',v),('G',g)]:obs[s,name]=[list(row) for row in zip(*val)]
  if s==p['iterations']:break
  nx=[[x[k][j]-eta*v[k][j]+gamma*sum(w[k][q]*(h[q][j]-h[k][j]) for q in range(n) if q!=k) for j in range(d)] for k in range(n)]
  # For quadratic objectives, gradient difference is Hessian times displacement.
  nv=[[v[k][j]+di[k][j]*(nx[k][j]-x[k][j])+gamma*sum(w[k][q]*(g[q][j]-g[k][j]) for q in range(n) if q!=k) for j in range(d)] for k in range(n)]
  nh=[];ng=[]
  for k in range(n):
   rh=[nx[k][j]-h[k][j] for j in range(d)];rg=[nv[k][j]-g[k][j] for j in range(d)];qh=compressed(rh);qg=compressed(rg)
   for res,q in [(rh,qh),(rg,qg)]:assert sum((z-y)**2 for z,y in zip(res,q)) <= (1-D(str(p['compressor']['contraction_alpha'])))*sum(z*z for z in res)+D('1e-80')
   nh.append([h[k][j]+qh[j] for j in range(d)]);ng.append([g[k][j]+qg[j] for j in range(d)])
  for j in range(d):assert abs(sum(nv[k][j] for k in range(n))-sum(di[k][j]*(nx[k][j]-a[k][j]) for k in range(n)))<D('1e-80')
  x,h,v,g=nx,nh,nv,ng
 return obs

def serial(a):
 if isinstance(a,list): return [serial(z) for z in a]
 return str(a)

def flat(a):
 if isinstance(a,list):
  for z in a:yield from flat(z)
 else:yield D(str(a))
spec=importlib.util.spec_from_file_location('schema',ROOT/'repo_judge/src/judge/paper_contract.py');schema=importlib.util.module_from_spec(spec);spec.loader.exec_module(schema)
res={}
for pid,fn in [('1904.12017',admm),('2102.06704',rr),('2201.13320',beer)]:
 c=json.loads((ROOT/f'reports/judge-paper-only-expanded-20260915/papers/{pid}/contract.json').read_text());sha=hashlib.sha256((ROOT/f'datasets/benchmarks/cpu30_v1/input/{pid}/paper.pdf').read_bytes()).hexdigest();schema.validate_contract(c,sha);rrs=[]
 for case in c['cases']:
  ob=fn(case);err=D(0);leaves=0;checks=[]
  for e in case['expected']:
   got=list(flat(ob[e['step'],e['name']]));want=list(flat(e['value']));assert len(got)==len(want)
   for a,b in zip(got,want):
    delta=abs(a-b);err=max(err,delta);leaves+=1;assert delta<=D(str(case['atol']))+D(str(case['rtol']))*abs(b),(case['id'],e['step'],e['name'],a,b)
   checks.append({'step':e['step'],'name':e['name'],'expected':e['value'],'computed':serial(ob[e['step'],e['name']]),'absolute_errors':[str(abs(a-b)) for a,b in zip(got,want)]})
  rrs.append({'checks':checks,'all_computed_observations':[{'step':s,'name':name,'value':serial(value)} for (s,name),value in ob.items()],'case_id':case['id'],'observations':len(case['expected']),'numeric_leaves':leaves,'maximum_absolute_error':str(err),'final':{name:[[str(y) for y in x] if isinstance(x,list) else str(x) for x in val] for (step,name),val in ob.items() if step==max(k[0] for k in ob)}})
 res[pid]={'contract_digest':schema.contract_digest(c),'paper_sha256':sha,'cases':rrs}
Path(__file__).resolve().with_name('reviewer_three_recompute_results.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
