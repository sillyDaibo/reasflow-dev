"""Independent review arithmetic; Decimal scalar RSA and spectral-mode DREAM.
Does not import or run the original derivation scripts or any implementation.
"""
import json, hashlib, importlib.util
from decimal import Decimal as D, getcontext
from pathlib import Path
getcontext().prec = 65
BASE=Path('/Users/zanehuang/work/OptiRepro')
OUT=BASE/'reports/judge-hardening-cpu30-20260915/paper_reviews'
def dec(x):
    return [dec(v) for v in x] if isinstance(x,list) else D(str(x))
def subgrad(v,p):
    if p==1:
        assert all(v); return [D(1) if x>0 else D(-1) for x in v]
    if p==2:
        norm=sum(x*x for x in v).sqrt(); assert norm>0
        return [x/norm for x in v]
    maximum=max(abs(x) for x in v); assert sum(abs(x)==maximum for x in v)==1
    return [D(0) if abs(x)!=maximum else (D(1) if x>0 else D(-1)) for x in v]
def rsa(case):
    i,p=case['inputs'],case['parameters']; m=dec(i['initial_master']); w=dec(i['initial_regular_workers']); a=dec(i['regular_worker_quadratic_centers']); c=dec(i['master_quadratic_center']); lam=D(str(p['lambda']))
    obs={(0,'master'):m,(0,'regular_workers'):w}
    for step,alpha in enumerate(dec(p['step_sizes']),1):
        grads=[[x-center for x,center in zip(row,ctr)] for row,ctr in zip(w,a)]
        ws=[subgrad([x-y for x,y in zip(row,m)],p['p']) for row in w]
        bs=[subgrad([x-y for x,y in zip(m,row)],p['p']) for row in dec(i['byzantine_messages_by_step'][step-1])]
        total=[sum(b[d] for b in bs)-sum(s[d] for s in ws) for d in range(len(m))]
        gm=[x-y for x,y in zip(m,c)]
        values={'worker_loss_gradients_before_update':grads,'worker_penalty_subgradients_before_update':ws,'byzantine_master_subgradients_before_update':bs,'master_penalty_subgradient_sum_before_update':total,'master_regularizer_gradient_before_update':gm}
        w=[[w[r][d]-alpha*(grads[r][d]+lam*ws[r][d]) for d in range(len(m))] for r in range(len(w))]
        m=[m[d]-alpha*(gm[d]+lam*total[d]) for d in range(len(m))]
        values.update(master=m,regular_workers=w);obs.update({(step,k):v for k,v in values.items()})
    return obs
# Derived symbolically in the disagreement eigenmode: r0=1, r1=27/40,
# r2=(13/10)(27/40)-5/8=101/400, r3=(13/10)(101/400)-(5/8)(27/40).
R=[D(1),D(27)/40,D(101)/400,-D(749)/8000]
def spectral(A,K):
    return [[(A[0][j]+A[1][j])/2 + (D(1) if n==0 else D(-1))*R[K]*(A[0][j]-A[1][j])/2 for j in range(2)] for n in range(2)]
def mean_gradient(coeffs,z):
    # First average polynomial coefficients, then differentiate the mean objective.
    a,c,d,e,h=[sum(row[k] for row in coeffs)/len(coeffs) for k in range(5)]
    return [a*z[0]+c*z[1]+e,c*z[0]-d*z[1]+h]
def dream(case,extra_mix=0):
    i,p=case['inputs'],case['parameters']; coeff=dec(i['component_coefficients']); z=[dec(i['initial_z']) for _ in range(2)]
    g=[mean_gradient(coeff[n],z[n]) for n in range(2)]
    s=spectral(g,p['K0']+extra_mix); obs={(0,'z'):z,(0,'g'):g,(0,'s'):s}; history=[]
    eta,gamma,q=map(lambda k:D(str(p[k])),['eta','gamma','q'])
    for t in range(p['T']):
        history += [z[n][0] for n in range(2)]
        raw=[[z[n][0]-eta*gamma*s[n][0],z[n][1]+eta*s[n][1]] for n in range(2)]
        proj=[row[:] for row in raw]
        if i['y_interval']:
            lo,hi=dec(i['y_interval'])
            for row in proj: row[1]=min(max(row[1],lo),hi)
        nz=spectral(proj,p['K']+extra_mix)
        ng=[row[:] for row in g]
        if i['refresh_draws'][t]:
            ng=[mean_gradient(coeff[n],nz[n]) for n in range(2)]
        else:
            for n in range(2):
                # Paired gradient difference of each quadratic equals Hessian * state difference.
                # Sum selected Hessians first, avoiding two gradient evaluations used by original script.
                selected=[coeff[n][j] for j in i['sample_indices'][t][n]]
                a,c,d=[sum(row[k] for row in selected) for k in range(3)]
                dx,dy=[nz[n][k]-z[n][k] for k in range(2)]
                fac=D(i['active_draws'][t][n])/(p['b']*q)
                ng[n]=[g[n][0]+fac*(a*dx+c*dy),g[n][1]+fac*(c*dx-d*dy)]
        ti=[[s[n][j]+ng[n][j]-g[n][j] for j in range(2)] for n in range(2)]
        ns=spectral(ti,(p['K_prime'] if i['refresh_draws'][t] else p['K'])+extra_mix)
        assert all(abs(sum(ns[n][j]-ng[n][j] for n in range(2)))<D('1e-60') for j in range(2))
        vals={'pre_projection':raw,'projected':proj,'z':nz,'g':ng,'tracker_input':ti,'s':ns,'mean_z':[(nz[0][j]+nz[1][j])/2 for j in range(2)]}
        obs.update({(t+1,k):v for k,v in vals.items()}); z,g,s=nz,ng,ns
    obs[(p['T'],'output_candidates')]=history
    obs[(p['T'],'x_out')]=history[i['output_draw_index']]
    return obs

def leaves(v):
    if isinstance(v,list):
        for x in v:yield from leaves(x)
    else:yield D(str(v))
def compare(case,actual):
    errors=[]; ratios=[]; mismatch=[]
    for e in case['expected']:
        av=list(leaves(actual[(e['step'],e['name'])]));ev=list(leaves(e['value']));assert len(av)==len(ev)
        for idx,(a,b) in enumerate(zip(av,ev)):
            err=abs(a-b);tol=D(str(case['atol']))+D(str(case['rtol']))*abs(b)
            errors.append(err);ratios.append(err/tol)
            if err>tol:mismatch.append([e['step'],e['name'],idx,str(err)])
    return {'numeric_leaves':len(errors),'maximum_absolute_error':str(max(errors)),'maximum_tolerance_fraction':str(max(ratios)),'mismatches':mismatch}
spec=importlib.util.spec_from_file_location('paper_contract',BASE/'repo_judge/src/judge/paper_contract.py'); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
result={}
for id,fn in [('1811.03761',rsa),('2212.02387',dream)]:
    contract=json.loads((BASE/f'reports/judge-paper-only-20260915/papers/{id}/contract.json').read_text())
    sha=hashlib.sha256((BASE/f'datasets/benchmarks/cpu30_v1/input/{id}/paper.pdf').read_bytes()).hexdigest()
    mod.validate_contract(contract,paper_sha256=sha)
    result[id]={'contract_digest':mod.contract_digest(contract),'paper_sha256':sha,'cases':{c['id']:compare(c,fn(c)) for c in contract['cases']}}
(OUT/'independent_arithmetic_rsa_dream.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
