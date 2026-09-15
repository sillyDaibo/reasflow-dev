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

def spectrum(M):
 gap=((M[0][0]-M[1][1])**2+4*M[0][1]**2).sqrt();s=M[0][0]+M[1][1]
 return [(s+gap)/2,(s-gap)/2]
def factor(M,e):
 l1,l2=spectrum(M);w1=min(ONE,e/l1.sqrt());w2=min(ONE,e/l2.sqrt());I=eye(2)
 return [[w2*I[i][j]+(w1-w2)*(M[i][j]-l2*I[i][j])/(l1-l2) for j in range(2)] for i in range(2)]
def calculate(case):
 data=case['inputs'];A=cv(data['measurement_matrix']);y=cv(data['measurements']);W=eye(4);epsilon=delta=D('Infinity');result=[]
 for k in range(1,case['parameters']['iterations']+1):
  n=len(y);K=[W[i][:]+[A[j][i] for j in range(n)] for i in range(4)]+[row[:]+[ZERO]*n for row in A]
  xv=solve(K,[ZERO]*4+y)[:4];X=[xv[:2],xv[2:]]
  XX=mm(X,tr(X));XT=mm(tr(X),X);sig=[l.sqrt() for l in spectrum(XX)];rows=[dot(row,row).sqrt() for row in X]
  epsilon=min(epsilon,sig[1]);delta=min(delta,min(rows));L=factor(XX,epsilon);R=factor(XT,epsilon);diag=[min(ONE,delta*delta/(v*v)) for v in rows]
  # Explicit basis action avoids relying on a vectorization Kronecker convention.
  cols=[]
  for j in range(4):
   E=[[ZERO,ZERO],[ZERO,ZERO]];E[j//2][j%2]=ONE;Y=mm(mm(L,E),R)
   for a in range(2):
    for b in range(2):Y[a][b]+=diag[a]*E[a][b]
   cols.append(Y[0]+Y[1])
  W=tr(cols)
  result+=output_obs(k,{'X':X,'singular_values':sig,'row_norms':rows,'epsilon':epsilon,'delta':delta,'low_rank_left':L,'low_rank_right':R,'row_weight_diagonal':diag,'weight_operator':W})
 return result
if __name__=='__main__':run_review(calculate)
