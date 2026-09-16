#!/usr/bin/env python3
"""Paper-only Algorithm 3 derivation. No implementation, adapter, or run imports."""
from pathlib import Path
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PDF = ROOT / 'datasets/benchmarks/cpu30_v1/input/2501.18312/paper.pdf'
spec = importlib.util.spec_from_file_location('paper_contract_schema', ROOT / 'repo_judge/src/judge/paper_contract.py')
schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema)
D = lambda x: Decimal(str(x))

def matrix(a):
    return [[D(x) for x in row] for row in a]

def scale(a, c):
    return [[x*c for x in row] for row in a]

def add(a,b):
    return [[x+y for x,y in zip(ar,br)] for ar,br in zip(a,b)]

def multiply(w,g):
    return [[sum((w[i][j]*g[j][h] for j in range(len(w))), D(0)) for h in range(len(g[0]))] for i in range(len(w))]

def numeric(v):
    if isinstance(v, list): return [numeric(x) for x in v]
    return float(v) if isinstance(v,Decimal) else v

MECHANISMS = ['barycenter_sample_softmax_and_minibatch', 'simplex_pps_empirical_frequencies', 'laplacian_neighbor_coupling', 'weighted_graph_history', 'accelerated_dual_predictor_corrector']
COMMON = {
    'T': 2,
    'cost': 'c(y,xi)=(y-xi)^2',
    'local_oracle': 'For local argument mu and each fixed source sample xi: p_h=exp((mu_h-c(y_h,xi))/gamma)/sum_l exp((mu_l-c(y_l,xi))/gamma); oracle_mean is the arithmetic mean over the r samples.',
    'pps_rule': 'For each public uniform u choose the first one-based h with u < cumulative_sum(oracle_mean)[h]. G[h]=count(h)/M. The vector is positive with l1 mass 1; the negative PPS contribution is zero and requires no negative draw.',
    'graph_rule': 'Use W @ G over node rows, including W_ii; local state is the argument passed directly to the Lemma 3 oracle. No extra m factor is inserted into the stated Algorithm 3 recurrence or oracle.',
    'array_layout': 'All state matrices have node rows and target-support columns. source_samples and pps_uniforms have outer axis oracle call s=0,1,2, then node, then sample. Indices are one-based.',
    'step_semantics': 'step 0 is initialization. step s=1,2 is completion of loop t=s-1. At step s, z_previous denotes z_(s-1); mu_hat denotes hat_mu_s. All nodes evaluate an oracle before graph multiplication in that iteration.',
    'observation_semantics': 'oracle_mean is unquantized minibatch; pps_indices are selected one-based categories; quantized_gradient is G_s; graph_gradient is W G_s; weighted_graph_sum is sum_(k=0)^s alpha_k W G_k; mu is oracle argument; lambda is Algorithm 3 dual output; A is cumulative alpha.',
    'scope': 'Only the explicitly specified Algorithm 3 dual trajectory with the Lemma 3 barycenter oracle is mandatory. x_T recovery, its unspecified x_0/time indexing, objective evaluation, convergence rates, transport solvers, and additional stopping procedures are excluded.'
}

def case_specs():
    a = {
      'id':'alg3_two_nodes_binary_support_two_updates',
      'purpose':'Two distinct bounded continuous source laws activate the barycenter softmax, minibatch-before-PPS, graph disagreement, and two accelerated updates on the smallest connected graph.',
      'covers':MECHANISMS,
      'inputs':{
        'W':[[1,-1],[-1,1]], 'target_support':[0,1], 'source_space':[0,1],
        'source_distributions':[{'law':'uniform','interval':[0,0.5]},{'law':'uniform','interval':[0.5,1]}],
        'source_samples':[[[0.1,0.4],[0.6,0.9]],[[0.2,0.35],[0.55,0.8]],[[0.05,0.3],[0.7,0.95]]],
        'pps_uniforms':[[[0.08,0.32,0.6,0.91],[0.11,0.42,0.72,0.96]],[[0.12,0.4,0.74,0.94],[0.07,0.2,0.3,0.88]],[[0.09,0.27,0.58,0.89],[0.14,0.38,0.68,0.93]]]
      },
      'parameters':{**COMMON,'gamma':0.5,'alpha':[0.5,0.75,1],'beta':[16,20,24],'r':2,'M':4},
      'atol':1e-10,'rtol':1e-9,
      'derivation':'Apply Lemma 3 to each of the two listed samples per node, average the two probability vectors, and apply Eq. (1) with mass 1 and four supplied uniform draws. With H_s=W G_s and S_s=sum_(k=0)^s alpha_k H_k, lambda_0=-alpha_0 H_0/beta_0. For s=1,2 use A_s=A_(s-1)+alpha_s, tau=alpha_s/A_s, z_(s-1)=-S_(s-1)/beta_(s-1), mu_s=tau*z_(s-1)+(1-tau)*lambda_(s-1), then compute the oracle and H_s; hat_mu_s=z_(s-1)-alpha_s H_s/beta_(s-1), lambda_s=tau*hat_mu_s+(1-tau)*lambda_(s-1). All expected entries are evaluated by the accompanying independent Decimal derivation at 60-digit precision. PAPER_BASIS.md records the exact rational graph trace.'
    }
    b = {
      'id':'alg3_three_node_path_three_support_two_updates',
      'purpose':'A three-node path with unequal degrees and three support points distinguishes diagonal and non-neighbor graph behavior, categorical PPS, changing beta, weighted graph history and synchronous predictor-corrector updates.',
      'covers':MECHANISMS,
      'inputs':{
        'W':[[1,-1,0],[-1,2,-1],[0,-1,1]], 'target_support':[-1,0,1], 'source_space':[-1,1],
        'source_distributions':[{'law':'uniform','interval':[-1,-0.2]},{'law':'uniform','interval':[-0.4,0.6]},{'law':'uniform','interval':[0.2,1]}],
        'source_samples':[[[-0.9,-0.3],[-0.25,0.45],[0.35,0.85]],[[-0.7,-0.4],[-0.1,0.5],[0.25,0.7]],[[-0.85,-0.25],[-0.3,0.25],[0.5,0.95]]],
        'pps_uniforms':[[[0.04,0.22,0.47,0.73,0.96],[0.03,0.31,0.53,0.78,0.97],[0.02,0.26,0.51,0.77,0.94]],[[0.06,0.24,0.44,0.75,0.95],[0.08,0.29,0.56,0.81,0.98],[0.05,0.23,0.49,0.74,0.93]],[[0.07,0.28,0.48,0.72,0.97],[0.04,0.26,0.54,0.76,0.96],[0.03,0.27,0.52,0.79,0.95]]]
      },
      'parameters':{**COMMON,'gamma':1,'alpha':[1,0.5,1.25],'beta':[24,30,36],'r':2,'M':5},
      'atol':1e-10,'rtol':1e-9,
      'derivation':a['derivation'].replace('two listed samples per node','two listed samples per node and three support points').replace('four supplied uniform draws','five supplied uniform draws')
    }
    return [a,b]

def derive(case):
    inp,p=case['inputs'],case['parameters']
    w,y=matrix(inp['W']),[D(x) for x in inp['target_support']]
    alpha,beta=[D(x) for x in p['alpha']],[D(x) for x in p['beta']]
    n,m=len(y),len(w)
    mu=[[D(0)]*n for _ in range(m)]
    obs=[]
    min_margin=D(1)
    def emit(s,name,val): obs.append({'step':s,'name':name,'value':numeric(val)})
    def oracle(s,mu):
        nonlocal min_margin
        means=[]; indices=[]; q=[]
        for node in range(m):
            prob=[D(0)]*n
            for sample in inp['source_samples'][s][node]:
                ex=[((mu[node][j]-(y[j]-D(sample))**2)/D(p['gamma'])).exp() for j in range(n)]
                den=sum(ex)
                prob=[v+e/den/D(p['r']) for v,e in zip(prob,ex)]
            assert abs(sum(prob)-1)<D('1e-55') and all(x>0 for x in prob)
            cdf=[sum(prob[:j+1]) for j in range(n)]
            ids=[]
            for u in inp['pps_uniforms'][s][node]:
                ud=D(u)
                min_margin=min(min_margin,*(abs(ud-c) for c in cdf[:-1]))
                ids.append(next(j+1 for j,c in enumerate(cdf) if ud<c))
            means.append(prob); indices.append(ids)
            q.append([D(ids.count(j+1))/D(p['M']) for j in range(n)])
        return means,indices,q
    A=alpha[0]
    mean,indices,g=oracle(0,mu)
    h=multiply(w,g); S=scale(h,alpha[0]); lam=scale(S,-1/beta[0])
    for name,v in [('A',A),('mu',mu),('oracle_mean',mean),('pps_indices',indices),('quantized_gradient',g),('graph_gradient',h),('weighted_graph_sum',S),('lambda',lam)]: emit(0,name,v)
    for s in range(1,p['T']+1):
        z=scale(S,-1/beta[s-1]); A+=alpha[s]; tau=alpha[s]/A
        mu=add(scale(z,tau),scale(lam,1-tau))
        mean,indices,g=oracle(s,mu); h=multiply(w,g)
        hat=add(z,scale(h,-alpha[s]/beta[s-1]))
        lam=add(scale(hat,tau),scale(lam,1-tau)); S=add(S,scale(h,alpha[s]))
        for name,v in [('A',A),('tau',tau),('z_previous',z),('mu',mu),('oracle_mean',mean),('pps_indices',indices),('quantized_gradient',g),('graph_gradient',h),('weighted_graph_sum',S),('mu_hat',hat),('lambda',lam)]: emit(s,name,v)
    case['expected']=obs
    assert min_margin>D('0.001'), f'CDF boundary too close: {min_margin}'
    return min_margin

def main():
    with localcontext() as ctx:
        ctx.prec=60
        cases=case_specs()
        margins=[derive(c) for c in cases]
    contract={
      'schema_version':schema.SCHEMA_VERSION,
      'paper':{'paper_id':'2501.18312','title':'Decentralised convex optimisation with probability-proportional-to-size quantization','sha256':hashlib.sha256(PDF.read_bytes()).hexdigest()},
      'algorithm':{'name':'Algorithm 3: Decentralised primal-dual fast gradient method, instantiated with the graph Wasserstein barycenter oracle (dual trajectory)',
        'citations':['PDF p. 17, Algorithm 3 (initialization and both graph-coupled update loops)','PDF pp. 17-18, Section 5, Laplacian W and distributed Wx identity','PDF pp. 19-20, Section 6.1 and Lemma 3 (semi-discrete barycenter and conjugate gradient)','PDF pp. 6-7, Section 2, minibatching and PPS Eq. (1), including fixed-uniform interpretation','PDF p. 11, Section 4.2, admissible alpha and beta coefficient conditions'],
        'core_mechanisms':MECHANISMS,
        'assumptions':['Sources are the specified bounded continuous uniform probability laws; supplied source samples are fixed realizations within their supports. No finite discrete measure is substituted for a required continuous source law.',
          'Squared distance is the chosen continuous transport cost; gamma is strictly positive. Each sampled oracle lies in the simplex, so its l1 bound is B=1 and its negative part has zero mass.',
          'The fixed uniforms implement the explicit p. 7 interpretation of PPS random arguments; no random-number generator or seed convention is required.',
          'W is the complete combinatorial graph Laplacian. Section 5 explicitly identifies the update as Wx; local diagonal contributions are included along with received neighbor messages.',
          'Algorithm 3 is instantiated using the local Lemma 3 oracle specified in parameters. Local state denotes that oracle argument; the inconsistent rescaled notation across Sections 5 and 6 is not used to assert any additional factor m.',
          'Only the dual trajectory is required. Algorithm 3 omits x_0 and time subscripts in its primal restoring call; these omissions do not affect the dual recurrence, and no mandatory x observations are invented.',
          'alpha and beta are supplied positive schedules satisfying the p. 11 inequalities for the stated small cases. These are finite trajectory tests, not claims of the theorem-specific optimal noise schedule or convergence after two iterations.']},
      'cases':cases}
    schema.validate_contract(contract)
    public=schema.public_contract(contract)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'contract.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False)+'\n')
    pub=ROOT/'reports/judge-followup-cpu30-20260915/public/2501.18312/public_cases.json'
    pub.parent.mkdir(parents=True,exist_ok=True)
    pub.write_text(json.dumps(public,indent=2,ensure_ascii=False)+'\n')
    assert all('expected' not in x and 'derivation' not in x for x in public['cases'])
    for c,margin in zip(cases,margins):
        print(c['id'], 'min CDF boundary margin',margin)
        for e in c['expected']:
            if e['name'] in ['pps_indices','graph_gradient','lambda']: print(e)
    print('Validated cases:',len(cases),'numeric leaves:',sum(len(list(leaves(e['value']))) for c in cases for e in c['expected']))

def leaves(x):
    if isinstance(x,list):
        for y in x: yield from leaves(y)
    else: yield x

if __name__=='__main__': main()
