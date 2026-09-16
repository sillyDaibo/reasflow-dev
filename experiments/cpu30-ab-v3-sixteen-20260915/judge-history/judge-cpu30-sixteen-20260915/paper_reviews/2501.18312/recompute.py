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
    i=case['inputs'];p=case['parameters'];a=exact(i['A_diagonal']);q=exact(i['q']);c=exact(i['c']);b=exact(i['b']);alpha=exact(p['alpha']);beta=exact(p['beta']);out={}
    def restore(mu):return [ci-ai*mi/qi for ai,qi,ci,mi in zip(a,q,c,mu)]
    def oracle(mu):return sub(b,[ai*xi for ai,xi in zip(a,restore(mu))])
    def categorical(w,u):
        total=sum(w);assert total>0;acc=Q(0)
        for j,z in enumerate(w):
            acc+=z
            if acc>u*total:return j
        raise AssertionError('invalid categorical draw')
    def pps(mu,t):
        raw=oracle(mu);pos=[max(z,Q(0)) for z in raw];neg=[max(-z,Q(0)) for z in raw]
        ip=[categorical(pos,u) for u in exact(i['positive_uniforms'][t])]
        im=[categorical(neg,u) for u in exact(i['negative_uniforms'][t])]
        M=p['M'][t];assert len(ip)==len(im)==M
        G=[sum(pos)*ip.count(j)/M-sum(neg)*im.count(j)/M for j in range(3)]
        for name,v in [('mu',mu),('oracle_g',raw),('PPS_G',G),('positive_negative_mass',[sum(pos),sum(neg)]),('sampled_positive_indices',[Q(z) for z in ip]),('sampled_negative_indices',[Q(z) for z in im])]:emit(out,t,name,v)
        return G
    mu=[Q(0)]*3;G=pps(mu,0);lam=mul(-alpha[0]/beta[0],G);emit(out,0,'lambda',lam)
    acc=mul(alpha[0],G);primal_acc=mul(alpha[0],restore(mu));weight=alpha[0]
    for t in range(p['T']):
        z=mul(-1/beta[t],acc);weight+=alpha[t+1];tau=alpha[t+1]/weight
        mu=add(mul(tau,z),mul(1-tau,lam));G=pps(mu,t+1)
        muhat=sub(z,mul(alpha[t+1]/beta[t],G));lam=add(mul(tau,muhat),mul(1-tau,lam))
        acc=add(acc,mul(alpha[t+1],G));restored=restore(mu);primal_acc=add(primal_acc,mul(alpha[t+1],restored));primal=mul(1/weight,primal_acc)
        residual=sub([ai*xi for ai,xi in zip(a,primal)],b);objective=sum(qi*(xi-ci)**2/2 for qi,xi,ci in zip(q,primal,c))
        for n,v in [('z_used',z),('mu_hat',muhat),('lambda',lam),('restored_primal_at_mu',restored),('primal_average',primal),('constraint_residual',residual),('primal_objective',objective)]:emit(out,t+1,n,v)
    # Directly check stated coefficient inequalities, with explicit beta[-1].
    beta_before=[exact(p['beta_minus_one_for_coefficient_condition'])]+beta[:-1]
    assert all(alpha[t]**2*beta[t]<=beta_before[t]*sum(alpha[:t+1]) for t in range(len(alpha)))
    assert all(beta[t]>p['dual_gradient_L'] for t in range(len(beta)))
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
