#!/usr/bin/env python3
"""Independent reviewer recomputation from original-paper equations and public inputs.
Does not import author's derivation or any implementation. Expected values are read
only by the comparison stage after the independently computed trajectory exists.
"""
from pathlib import Path
import json
from decimal import Decimal, getcontext
from fractions import Fraction
getcontext().prec=100

def rat(v):return Fraction(str(v))
def dec(v):return Decimal(str(v))
def nums(v):return [nums(w) for w in v] if isinstance(v,list) else float(v)
def avg(v):return sum(v)/len(v)
def put(out,k,name,value):out.append({'step':k,'name':name,'value':nums(value)})

def compute(case):
 i,p=case['inputs'],case['parameters'];x=list(map(rat,i['x_initial']));a=list(map(rat,i['quadratic_a']));b=list(map(rat,i['quadratic_b']));eta=rat(p['eta']);tau=p['tau'];out=[];noise=[list(map(rat,row)) for row in i['noise']]
 if i['method']=='local_sgd':
  for t,z in enumerate(noise):
   before=x[:];g=[a[j]*x[j]+b[j]+z[j] for j in range(len(x))];trial=[q-eta*v for q,v in zip(x,g)];x=[avg(trial)]*len(x) if (t+1)%tau==0 else trial
   for name,v in [('x_before',before),('sample_gradient',g),('local_proposal',trial),('x_after',x)]:put(out,t+1,name,v)
 else:
  for cycle in range(p['outer_cycles']):
   anchor_start=avg(x);anchor_samples=[];train_samples=[]
   for h in range(2*tau):
    t=2*tau*cycle+h;before=x[:];g=[a[j]*x[j]+b[j]+noise[t][j] for j in range(len(x))];put(out,t+1,'x_before',before);put(out,t+1,'sample_gradient',g)
    if h<tau:
     anchor_samples.append(g)
     if h==tau-1:
      anchor=[avg([row[j] for row in anchor_samples]) for j in range(len(x))];global_anchor=avg(anchor)
    else:
     cg=[g[j]-anchor[j]+global_anchor for j in range(len(x))];put(out,t+1,'corrected_gradient',cg);train_samples.append(g)
     if h<2*tau-1:x=[q-eta*v for q,v in zip(x,cg)]
     else:x=[anchor_start-eta*sum(sum(row) for row in train_samples)/len(x)]*len(x)
    put(out,t+1,'x_after',x)
    if h==tau-1:put(out,t+1,'anchor_local',anchor);put(out,t+1,'anchor_global',global_anchor)
 return out

HERE=Path(__file__).resolve().parent
contract=json.loads((HERE.parent.parent/'papers'/HERE.name/'contract.json').read_text())
trajectories=[{'id':case['id'],'observations':compute(case)} for case in contract['cases']]
(HERE/'recomputed.json').write_text(json.dumps(trajectories,indent=2)+'\n')
checks=[]
def compare(expected,observed,path,atol,rtol):
 if isinstance(expected,list):
  assert isinstance(observed,list) and len(expected)==len(observed)
  for j,(a,b) in enumerate(zip(expected,observed)):compare(a,b,path+[j],atol,rtol)
 else:
  error=abs(Decimal(str(expected))-Decimal(str(observed)));bound=atol+rtol*abs(Decimal(str(expected)))
  checks.append({'path':path,'expected':expected,'independent':observed,'absolute_error':float(error),'tolerance':float(bound),'passed':error<=bound})
for case,traj in zip(contract['cases'],trajectories):
 obs={(e['step'],e['name']):e['value'] for e in traj['observations']}
 assert set(obs)=={(e['step'],e['name']) for e in case['expected']}
 for entry in case['expected']:compare(entry['value'],obs[(entry['step'],entry['name'])],[case['id'],entry['step'],entry['name']],Decimal(str(case['atol'])),Decimal(str(case['rtol'])))
result={'paper_id':HERE.name,'method':'Independent original-paper recurrence; Decimal 100 digits for logistic, Fraction exact for polynomial arithmetic','numeric_leaves':len(checks),'all_passed':all(c['passed'] for c in checks),'max_absolute_error':max(c['absolute_error'] for c in checks),'checks':checks}
(HERE/'numeric_error.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
assert result['all_passed']
