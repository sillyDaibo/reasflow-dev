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

def calculate(case):
 d=case['inputs'];p=case['parameters'];K=cv(d['K']);G=cv(d['gradient_matrix']);f=cv(d['f']);u=cv(d['u0']);z=cv(d['z0']);mu,beta,exponent,epsilon,L=[D(str(p[k])) for k in ['mu','beta','p','epsilon','L']]
 KTK=mm(tr(K),K);GTG=mm(tr(G),G);system=[[a+beta*b for a,b in zip(ar,br)] for ar,br in zip(KTK,GTG)];base=mv(tr(K),f);result=[]
 for step in range(1,p['iterations']+1):
  grad=mv(G,u);threshold=[exponent*mu/(L*beta*power(abs(v)+epsilon,1-exponent)) for v in z]
  z=[(ONE if g>0 else -ONE if g<0 else ZERO)*max(ZERO,abs(g)-t) for g,t in zip(grad,threshold)]
  u=solve(system,add(base,smul(beta,mv(tr(G),z))))
  err=sub(mv(K,u),f);r=sub(z,mv(G,u));obj=dot(err,err)/2+mu*sum((power(abs(v),exponent) for v in z),ZERO)+beta*dot(r,r)/2
  result+=output_obs(step,{'gradient_before':grad,'thresholds':threshold,'z':z,'u':u,'objective':obj})
 return result
if __name__=='__main__':run_review(calculate)
