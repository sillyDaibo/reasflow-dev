#!/usr/bin/env python3
"""Independent paper-only reconstruction of PPS Algorithm 3.

No author derivation or implementation is imported. Exact Fraction arithmetic
is used for graph/dual states; 90-digit Decimal exp for the local WB oracle.
The expected fields are accessed only after an entire independent trajectory
has been computed from the input and parameter sections.
"""
from __future__ import annotations
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
DEFAULT = HERE.parents[1] / 'papers' / '2501.18312' / 'contract.json'

def rational(x):
    return F(str(x))

def dec(x):
    if isinstance(x, F):
        return Decimal(x.numerator) / Decimal(x.denominator)
    return Decimal(str(x))

def zeros(m,n):
    return [[F(0) for _ in range(n)] for _ in range(m)]

def scale(a,c):
    return [[v*c for v in row] for row in a]

def add(a,b):
    return [[u+v for u,v in zip(ar,br)] for ar,br in zip(a,b)]

def graph_product(w,g):
    # Deliberately independent scalar matrix product, including every diagonal.
    return [[sum((w[i][j]*g[j][h] for j in range(len(w))),F(0))
             for h in range(len(g[0]))] for i in range(len(w))]

def exact_shape(value):
    if not isinstance(value,list): return []
    if not value: return [0]
    shapes=[exact_shape(x) for x in value]
    assert all(s==shapes[0] for s in shapes)
    return [len(value)]+shapes[0]

def leaves(value):
    if isinstance(value,list):
        for x in value: yield from leaves(x)
    else: yield dec(value)

def serial(value):
    if isinstance(value,list): return [serial(x) for x in value]
    if isinstance(value,F): return {'fraction':str(value),'decimal':str(dec(value))}
    if isinstance(value,Decimal): return str(value)
    return value

def solve_from_paper(case):
    i,p=case['inputs'],case['parameters']
    w=[[rational(v) for v in row] for row in i['W']]
    support=[rational(v) for v in i['target_support']]
    alpha=[rational(v) for v in p['alpha']]
    beta=[rational(v) for v in p['beta']]
    m,n,T=len(w),len(support),p['T']
    gamma=rational(p['gamma']); r=p['r']; M=p['M']
    assert m>1 and n>1 and T==2 and r>0 and M>0 and gamma>0
    assert len(alpha)>=T+1 and len(beta)>=T+1
    assert all(len(row)==m for row in w)
    assert all(sum(row)==0 for row in w)
    assert all(w[a][b]==w[b][a] for a in range(m) for b in range(m))
    assert all(w[a][a]>0 for a in range(m))
    assert all(w[a][b]<=0 for a in range(m) for b in range(m) if a!=b)
    reached={0}
    while True:
        newer=reached|{b for a in reached for b in range(m) if a!=b and w[a][b]<0}
        if newer==reached:break
        reached=newer
    assert len(reached)==m
    assert 0<alpha[0]<=1 and all(a>0 for a in alpha)
    assert all(beta[t]<=beta[t+1] for t in range(T))
    # A conservative version of the p.18 m*||W||/gamma bound is sufficient.
    laplacian_norm_upper=2*max(w[j][j] for j in range(m))
    L_upper=m*laplacian_norm_upper/gamma
    assert all(b>L_upper for b in beta)
    coefficient_checks=[]
    for t in range(1,T+1):
        left=alpha[t]**2*beta[t]
        right=beta[t-1]*sum(alpha[:t+1])
        printed_repeat=beta[t-1]*(t+1)*alpha[t]
        assert left<=right and left<=printed_repeat
        coefficient_checks.append(dict(t=t,left=str(left),cumulative_alpha_right=str(right),literal_repeated_alpha_right=str(printed_repeat)))
    assert len(i['source_samples'])==T+1 and len(i['pps_uniforms'])==T+1
    observations=[]; oracle_evidence=[]; min_gap=Decimal('Infinity')
    quantized_diff=[]
    def emit(t,name,value):observations.append(dict(step=t,name=name,value=value))
    def oracle(t,mu):
        nonlocal min_gap
        means=[]; indices=[]; messages=[]; sample_probs=[]
        assert len(i['source_samples'][t])==len(i['pps_uniforms'][t])==m
        for node in range(m):
            law=i['source_distributions'][node]
            assert law['law']=='uniform'
            low,high=map(rational,law['interval'])
            assert low<high
            assert rational(i['source_space'][0])<=low<high<=rational(i['source_space'][1])
            samples=i['source_samples'][t][node]
            uniforms=i['pps_uniforms'][t][node]
            assert len(samples)==r and len(uniforms)==M
            probs=[]
            for sample in samples:
                sample=rational(sample);assert low<sample<high
                logits=[dec((mu[node][h]-(support[h]-sample)**2)/gamma) for h in range(n)]
                # Stable local Lemma 3 probability; same sample in every term.
                common=max(logits)
                exp_values=[(v-common).exp() for v in logits]
                denominator=sum(exp_values)
                probs.append([v/denominator for v in exp_values])
            q=[sum(probs[a][h] for a in range(r))/Decimal(r) for h in range(n)]
            running=Decimal(0);cdf=[]
            for probability in q:
                running+=probability;cdf.append(running)
            assert abs(sum(q)-1)<Decimal('1e-85') and all(v>0 for v in q)
            categories=[]
            for raw in uniforms:
                u=dec(raw);assert 0<u<1
                for boundary in cdf[:-1]:min_gap=min(min_gap,abs(u-boundary))
                categories.append(next(h+1 for h,boundary in enumerate(cdf) if u<boundary))
            counts=Counter(categories)
            g=[F(counts[h+1],M) for h in range(n)]
            assert sum(g)==1
            quantized_diff.append(max(abs(dec(v)-prob) for v,prob in zip(g,q)))
            means.append(q);indices.append(categories);messages.append(g);sample_probs.append(probs)
        H=graph_product(w,messages)
        assert all(sum(row)==0 for row in H)
        assert all(sum(H[node][h] for node in range(m))==0 for h in range(n))
        assert any(v for row in H for v in row)
        emit(t,'mu',mu);emit(t,'oracle_mean',means);emit(t,'pps_indices',indices)
        emit(t,'quantized_gradient',messages);emit(t,'graph_gradient',H)
        oracle_evidence.append(dict(step=t,sample_probabilities=sample_probs))
        return H
    mu=zeros(m,n);A=alpha[0]
    emit(0,'A',A)
    H=oracle(0,mu)
    weighted=scale(H,alpha[0])
    lam=scale(weighted,-1/beta[0])
    emit(0,'weighted_graph_sum',weighted);emit(0,'lambda',lam)
    for t in range(T):
        s=t+1;A+=alpha[s];tau=alpha[s]/A
        z=scale(weighted,-1/beta[t])
        mu=add(scale(z,tau),scale(lam,1-tau))
        emit(s,'A',A);emit(s,'tau',tau);emit(s,'z_previous',z)
        H=oracle(s,mu)
        hat=add(z,scale(H,-alpha[s]/beta[t]))
        lam=add(scale(hat,tau),scale(lam,1-tau))
        weighted=add(weighted,scale(H,alpha[s]))
        emit(s,'weighted_graph_sum',weighted);emit(s,'mu_hat',hat);emit(s,'lambda',lam)
        assert all(sum(lam[node][h] for node in range(m))==0 for h in range(n))
        assert all(sum(row)==0 for row in lam)
    checks=dict(graph_connected=True,full_laplacian=True,laplacian_norm_upper=str(laplacian_norm_upper),
                conservative_m_scaled_L_upper=str(L_upper),coefficient_checks=coefficient_checks,
                min_categorical_boundary_distance=str(min_gap),min_nonzero_quantization_difference=str(min(quantized_diff)),
                source_samples_strictly_inside_support=True,exact_graph_and_dual_invariants=True,
                expected_oracle_calls=T+1,observed_oracle_calls=len(oracle_evidence))
    assert min_gap>Decimal('1e-6') and min(quantized_diff)>0
    return observations,checks,oracle_evidence

def main():
    path=Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT
    raw=path.read_bytes();contract=json.loads(raw,parse_float=Decimal)
    output=[];overall_max=Decimal(0)
    with localcontext() as ctx:
        ctx.prec=90
        for case in contract['cases']:
            # expected deliberately excluded from the independent solver input.
            independent,checks,oracle=solve_from_paper({'inputs':case['inputs'],'parameters':case['parameters']})
            actual={(x['step'],x['name']):x['value'] for x in independent}
            expected={(x['step'],x['name']):x['value'] for x in case['expected']}
            assert len(actual)==len(independent)==len(expected)==len(case['expected'])
            assert set(actual)==set(expected)
            comparisons=[];case_max=Decimal(0);numeric_count=0
            for key in sorted(expected):
                av,ev=actual[key],expected[key]
                assert exact_shape(av)==exact_shape(ev),(key,'shape mismatch')
                pairs=list(zip(leaves(av),leaves(ev)))
                errors=[abs(a-e) for a,e in pairs]
                all_ok=all(error<=dec(case['atol'])+dec(case['rtol'])*abs(e) for error,(a,e) in zip(errors,pairs))
                if key[1]=='pps_indices':assert all(error==0 for error in errors)
                assert all_ok,(case['id'],key,errors)
                max_error=max(errors);case_max=max(case_max,max_error);numeric_count+=len(pairs)
                comparisons.append(dict(step=key[0],name=key[1],shape=exact_shape(av),max_absolute_error=str(max_error),within_tolerance=all_ok))
            overall_max=max(overall_max,case_max)
            output.append(dict(case_id=case['id'],observation_count=len(independent),scalar_entry_count=numeric_count,
                               max_absolute_error=str(case_max),checks=checks,comparisons=comparisons,
                               independent_observations=serial(independent),sample_probability_evidence=serial(oracle)))
        # serial must traverse dictionaries too, without losing rational evidence.
        def all_serial(v):
            if isinstance(v,dict):return {k:all_serial(x) for k,x in v.items()}
            if isinstance(v,list):return [all_serial(x) for x in v]
            return serial(v)
        report=dict(contract_file_sha256=hashlib.sha256(raw).hexdigest(),precision_digits=ctx.prec,
                    method='Independent scalar Fraction graph recurrence and 90-digit Decimal softmax; no author derivation or implementation imported.',
                    all_pass=True,max_absolute_error=str(overall_max),cases=all_serial(output))
        (HERE/'INDEPENDENT_ARITHMETIC.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
        for r in output:
            print(r['case_id'],r['observation_count'],r['scalar_entry_count'],r['max_absolute_error'],r['checks']['min_categorical_boundary_distance'])
if __name__=='__main__':main()
