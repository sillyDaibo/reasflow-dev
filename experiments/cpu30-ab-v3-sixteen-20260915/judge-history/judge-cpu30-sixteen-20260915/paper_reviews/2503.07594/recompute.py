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
 i,p=case['inputs'],case['parameters'];theta=rat(i['theta_initial']);xi=list(map(rat,i['xi_initial']));a=list(map(rat,i['quadratic_a']));b=list(map(rat,i['quadratic_b']));eta=rat(p['gamma']);H=p['H'];out=[]
 for k,noises in enumerate(i['noise'],1):
  put(out,k,'theta_before',theta);put(out,k,'xi_before',xi);local=[theta]*i['clients'];track=[local[:]];raw=[];corr=[]
  for noise in noises:
   g=[a[j]*local[j]+b[j]+rat(noise[j]) for j in range(i['clients'])];cg=[g[j]+xi[j] for j in range(i['clients'])];local=[v-eta*w for v,w in zip(local,cg)];raw.append(g);corr.append(cg);track.append(local[:])
  theta=avg(local);xi=[xi[j]+(local[j]-theta)/(eta*H) for j in range(i['clients'])];assert sum(xi)==0
  for name,v in [('local_theta',track),('sample_gradient',raw),('corrected_gradient',corr),('theta_after',theta),('xi_after',xi)]:put(out,k,name,v)
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
