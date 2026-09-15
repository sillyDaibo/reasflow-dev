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
    i=case['inputs'];p=case['parameters'];q=exact(i['q']);b=exact(i['b']);x=exact(i['x0']);h=exact(i['h0_regular']);g=exact(i['g0_regular']);eta=exact(p['gamma']);a=Q(p['a_exact']);attack=exact(i['byzantine_g_states']);out={}
    def full(j,z):return [sum(q[j][s][k]*z[k]+b[j][s][k] for s in range(2))/2 for k in range(2)]
    assert h==g==[full(j,x) for j in range(5)]
    def aggregate(states,permutation):
        pairs=[[sum(states[permutation[k]][d] for k in range(start,start+2))/2 for d in range(2)] for start in range(0,6,2)]
        return pairs,[sorted(col)[1] for col in zip(*pairs)]
    buckets,server=aggregate(g+[attack[0]],i['bucket_permutations'][0])
    for t,coin in enumerate(i['page_coins'],1):
        xn=sub(x,mul(eta,server));hn=[];cin=[];msg=[]
        for j in range(5):
            if coin:hj=full(j,xn)
            else:
                sample=i['sampled_component_indices'][t-1][j]
                hj=add(h[j],[q[j][sample][k]*(xn[k]-x[k]) for k in range(2)])
            hn.append(hj);v=sub(sub(hj,h[j]),mul(a,sub(g[j],h[j])));cin.append(v)
            kept=i['rand1_kept_coordinate'][t-1][j];msg.append([2*v[k] if k==kept else Q(0) for k in range(2)])
        g=[add(gi,mi) for gi,mi in zip(g,msg)];h=hn;x=xn
        buckets,server=aggregate(g+[attack[t]],i['bucket_permutations'][t])
        obj=sum(q[j][s][k]*x[k]*x[k]/2+b[j][s][k]*x[k] for j in range(5) for s in range(2) for k in range(2))/10
        for n,v in [('x',x),('h_regular',h),('compression_input_regular',cin),('message_regular',msg),('g_regular',g),('bucket_means',buckets),('g_aggregate',server),('objective',obj)]:emit(out,t,n,v)
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
