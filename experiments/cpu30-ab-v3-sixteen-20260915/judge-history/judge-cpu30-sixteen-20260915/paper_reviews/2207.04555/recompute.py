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
    i=case['inputs'];p={k:exact(v) for k,v in case['parameters'].items()};A=exact(i['A']);AT=tr(A)
    x=exact(i['x0']);y=exact(i['y0']);xf=x[:];yf=y[:];yprev=y[:];q=exact(i['q']);b=exact(i['c']);out={}
    # In this fixture Ker(A) is span([0,1,0,1]), hence x0 lies in Range(A^T).
    assert x[1]+x[3]==0
    scale=p['gamma_constraint_scale'];assert y[2]==scale*(y[0]-y[1]) and y[4]==-y[2] and y[5]==-y[3]
    for t in range(1,int(p['updates'])+1):
        ym=add(y,mul(p['theta'],sub(y,yprev)))
        xg=add(mul(p['tau_x'],x),mul(1-p['tau_x'],xf));yg=add(mul(p['tau_y'],y),mul(1-p['tau_y'],yf))
        gradient=[a*z+c for a,z,c in zip(q,xg,b)]
        xp=sub(sub(add(x,mul(p['eta_x']*p['alpha_x'],sub(xg,x))),mul(p['eta_x']*p['beta_x'],mv(AT,mv(A,x)))),mul(p['eta_x'],add(gradient,mv(AT,ym))))
        yn=add(sub(y,mul(p['eta_y']*p['beta_y'],mv(A,add(mv(AT,y),gradient)))),mul(p['eta_y'],mv(A,xp)))
        xf=add(xg,mul(p['sigma_x'],sub(xp,x)));yf=add(yg,mul(p['sigma_y'],sub(yn,y)))
        x,yprev,y=xp,y,yn
        for n,v in [('x_g_used',xg),('y_g_used',yg),('y_m_used',ym),('x',x),('y',y),('x_f',xf),('y_f',yf),('constraint_Ax',mv(A,x)),('objective',sum(a*z*z/2+c*z for a,z,c in zip(q,x,b)))]:emit(out,t,n,v)
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
