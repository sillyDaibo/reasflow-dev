"""Independent reviewer recomputation from original paper. Does not import author code."""
from fractions import Fraction as Q
from pathlib import Path
import json, hashlib

def exact(x):
    if isinstance(x,list): return [exact(v) for v in x]
    return Q(str(x))
def mv(A,x):return [sum(a*b for a,b in zip(row,x)) for row in A]
def tr(A):return [list(row) for row in zip(*A)]
def add(x,y):return [a+b for a,b in zip(x,y)]
def sub(x,y):return [a-b for a,b in zip(x,y)]
def mul(a,x):return [a*b for b in x]
def emit(out,t,n,v):out[(t,n)]=v

def recompute(case):
    i=case['inputs'];p=case['parameters'];x=exact(i['x0']);h=exact(i['h0']);A=exact(i['operator_matrices']);b=exact(i['operator_offsets']);gamma=exact(p['gamma']);prob=exact(p['p']);out={};count=0
    assert all(sum(v)==0 for v in zip(*h))
    for t,coin in enumerate(i['communication_coins'],1):
        op=[add(mv(M,z),v) for M,z,v in zip(A,x,b)]
        hat=[sub(z,mul(gamma,sub(g,c))) for z,g,c in zip(x,op,h)]
        if coin:
            messages=[sub(z,mul(gamma/prob,c)) for z,c in zip(hat,h)]
            mean=[sum(col)/len(x) for col in zip(*messages)];x=[mean[:] for _ in x];count+=1
        else:x=[z[:] for z in hat]
        h=[add(c,mul(prob/gamma,sub(z,zhat))) for c,z,zhat in zip(h,x,hat)]
        assert all(sum(v)==0 for v in zip(*h))
        for n,v in [('operator_used',op),('x_hat',hat),('x',x),('h',h),('mean_x',[sum(col)/len(x) for col in zip(*x)]),('communication_count',Q(count))]:emit(out,t,n,v)
    return out

if __name__=='__main__':
    directory=Path(__file__).resolve().parent
    contract_path=directory.parents[1]/'papers'/directory.name/'contract.json'
    c=json.loads(contract_path.read_text())
    checks=[];counts={}
    for case in c['cases']:
        independent=recompute(case)
        required={(e['step'],e['name']) for e in case['expected']}
        assert set(independent)==required, (set(independent)-required,required-set(independent))
        def compare(v,w,path,step,name):
            if isinstance(v,list):
                assert isinstance(w,list) and len(v)==len(w)
                for j,(a,b) in enumerate(zip(v,w)):compare(a,b,path+[j],step,name)
            else:
                error=abs(v-Q(str(w)));tolerance=Q(str(case['atol']))+Q(str(case['rtol']))*abs(Q(str(w)))
                checks.append(dict(case_id=case['id'],step=step,name=name,path=path,independent_exact=str(v),contract_value=w,abs_error=float(error),tolerance=float(tolerance),passed=error<=tolerance))
        for e in case['expected']:compare(independent[(e['step'],e['name'])],e['value'],[],e['step'],e['name'])
        counts[case['id']]=sum(x['case_id']==case['id'] for x in checks)
    result=dict(paper_id=c['paper']['paper_id'],contract_digest=hashlib.sha256(json.dumps(c,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest(),numeric_leaves=len(checks),case_leaves=counts,max_abs_error=max(x['abs_error'] for x in checks),passed=all(x['passed'] for x in checks),checks=checks)
    (directory/'numeric_errors.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
