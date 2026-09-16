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
 i,p=case['inputs'],case['parameters'];l=list(map(rat,i['lambda_initial']));A=[list(map(rat,row)) for row in i['incidence_matrix']];a=list(map(rat,i['quadratic_curvatures']));c=list(map(rat,i['quadratic_centers']));eta=rat(p['eta']);out=[]
 def calc(l):
  y=[sum(z*v for z,v in zip(row,l)) for row in A];theta=[c[j]+y[j]/a[j] for j in range(len(a))];value=sum(c[j]*y[j]+y[j]*y[j]/(2*a[j]) for j in range(len(a)))
  return theta,value
 for k,node in enumerate(i['active_nodes'],1):
  theta,val=calc(l);g=[sum(A[j][e]*theta[j] for j in range(len(a))) for e in range(len(l))];accessible=[e for e in range(len(l)) if A[node][e]!=0];order=sorted(accessible,key=lambda e:abs(g[e]),reverse=True);e=order[0]
  assert len(order)==1 or abs(g[e])>abs(g[order[1]])
  put(out,k,'theta_before',theta);put(out,k,'dual_gradient_before',g);put(out,k,'selected_edge',e);put(out,k,'dual_objective_before',val)
  l[e]-=eta*g[e];nexttheta,val=calc(l)
  assert all(nexttheta[j]==theta[j] for j in range(len(a)) if A[j][e]==0)
  for name,v in [('lambda_after',l),('theta_after',nexttheta),('dual_objective_after',val)]:put(out,k,name,v)
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
