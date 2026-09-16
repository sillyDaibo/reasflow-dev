"""Independent original-paper arithmetic review. No author derivation or implementation imports."""
from decimal import Decimal as D, getcontext
from pathlib import Path
import json,hashlib
getcontext().prec=70
ZERO=D(0);ONE=D(1)
def cv(x):return [cv(a) for a in x] if isinstance(x,list) else D(str(x))
def num(x):return [num(a) for a in x] if isinstance(x,list) else float(x)
def tr(A):return [list(c) for c in zip(*A)]
def dot(a,b):return sum((x*y for x,y in zip(a,b)),ZERO)
def mv(A,x):return [dot(r,x) for r in A]
def mm(A,B):return [[dot(r,c) for c in zip(*B)] for r in A]
def eye(n):return [[D(i==j) for j in range(n)] for i in range(n)]
def add(x,y):return [a+b for a,b in zip(x,y)]
def sub(x,y):return [a-b for a,b in zip(x,y)]
def smul(a,x):return [a*b for b in x]
def solve(A,b):
 aug=[r[:]+[s] for r,s in zip(A,b)];n=len(b)
 for i in range(n):
  j=max(range(i,n),key=lambda k:abs(aug[k][i]));aug[i],aug[j]=aug[j],aug[i]
  assert aug[i][i]!=0
  p=aug[i][i];aug[i]=[v/p for v in aug[i]]
  for k in range(n):
   if k!=i:
    p=aug[k][i];aug[k]=[a-p*b for a,b in zip(aug[k],aug[i])]
 return [r[-1] for r in aug]
def power(x,p):return ZERO if x==0 else (p*x.ln()).exp()
def output_obs(step,vals):return [{'step':step,'name':k,'value':num(v)} for k,v in vals.items()]
def run_review(calculate):
 here=Path(__file__).resolve().parent;id=here.name;report=here.parent.parent
 contract=json.loads((report/'papers'/id/'contract.json').read_text());results=[];checks=[]
 for case in contract['cases']:
  actual=calculate(case);results.append({'id':case['id'],'observations':actual})
  actual_index={(e['step'],e['name']):e['value'] for e in actual}
  assert set(actual_index)=={(e['step'],e['name']) for e in case['expected']}
  def compare(a,b,path):
   if isinstance(a,list):
    assert isinstance(b,list) and len(a)==len(b)
    for i,(aa,bb) in enumerate(zip(a,b)):compare(aa,bb,path+[i])
   else:
    err=abs(D(str(a))-D(str(b)));bound=D(str(case['atol']))+D(str(case['rtol']))*abs(D(str(a)))
    checks.append({'case_id':case['id'],'step':entry['step'],'name':entry['name'],'path':path,'absolute_error':float(err),'tolerance':float(bound),'passed':err<=bound})
  for entry in case['expected']:compare(entry['value'],actual_index[(entry['step'],entry['name'])],[])
 digest=hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
 summary={'contract_digest':digest,'precision_decimal_digits':70,'checked_scalar_count':len(checks),'maximum_absolute_error':max(c['absolute_error'] for c in checks),'all_within_tolerance':all(c['passed'] for c in checks),'checks':checks,'recomputed_observations':results}
 (here/'recomputation.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
 print(id,{k:v for k,v in summary.items() if k not in ['checks','recomputed_observations']})

def column(x):return [[v] for v in x]
def calculate(case):
 d=case['inputs'];p=case['parameters'];x=[D(str(r[0])) for r in d['X0']];Q=cv(d['Q']);c=cv(d['linear_c']);mu=D(str(d['mu']));delta=D(str(p['delta']));sigma=D(str(p['sigma']));gamma=D(str(p['gamma']));history=[];result=[]
 def F(x):return dot(x,mv(Q,x))/2+dot(c,x)+mu*sum(abs(v) for v in x)
 def grad(x):
  eu=add(mv(Q,x),c);return sub(eu,smul(dot(x,eu),x))
 for k in range(p['iterations']):
  g=grad(x);damp=ONE
  if k==0:B=eye(2)
  else:
   s=sub(x,oldx);y=sub(g,oldg);ss=dot(s,s);sy=dot(s,y)
   if sy<D('0.25')*delta*ss:damp=D('0.75')*delta*ss/(delta*ss-sy)
   ybar=add(smul(damp,y),smul((1-damp)*delta,s));den=dot(s,ybar)
   B=[[delta*D(i==j)-delta*s[i]*s[j]/ss+ybar[i]*ybar[j]/den for j in range(2)] for i in range(2)]
  metric=[B[0][0],B[1][1]];vbase=[-x[1],x[0]];mcoef=sum(metric[j]*vbase[j]**2 for j in range(2));linear=dot(g,vbase)
  roots=sorted(set(-x[j]/vbase[j] for j in range(2) if vbase[j]!=0));candidates=roots[:]
  intervals=[D('-Infinity')]+roots+[D('Infinity')]
  for lo,hi in zip(intervals,intervals[1:]):
   mid=hi-1 if lo.is_infinite() else lo+1 if hi.is_infinite() else (lo+hi)/2
   signs=[ONE if x[j]+mid*vbase[j]>0 else -ONE for j in range(2)]
   t=-(linear+mu*dot(signs,vbase))/mcoef
   if lo<=t<=hi:candidates.append(t)
  def model(t):return linear*t+mcoef*t*t/2+mu*sum(abs(x[j]+t*vbase[j]) for j in range(2))
  t=min(candidates,key=model);V=smul(t,vbase);norm=sum(metric[j]*V[j]**2 for j in range(2));history.append(F(x));ref=max(history[max(0,k-p['nonmonotone_m']):k+1]);alpha=ONE;backs=0
  while True:
   trial=add(x,smul(alpha,V));trial=smul(1/dot(trial,trial).sqrt(),trial)
   if F(trial)<=ref-sigma*alpha*norm/2:break
   alpha*=gamma;backs+=1
   assert backs<100
  result+=output_obs(k+1,{'X_before':column(x),'riemannian_gradient':column(g),'B_matrix':B,'metric_diagonal':metric,'damping_beta':damp,'V':column(V),'tangent_metric_norm_squared':norm,'line_search_reference':ref,'alpha':alpha,'backtracks':D(backs),'X':column(trial),'objective':F(trial)})
  oldx,oldg=x,g;x=trial
 return result
if __name__=='__main__':run_review(calculate)
