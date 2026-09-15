"""Independent paper-only BEER derivation; reads no implementation or existing answers.
Original source: arXiv:2201.13320v3, PDF pp.5-7, Definition2.2 and Algorithm1.
Primary oracle uses exact Fraction matrix arithmetic. A separately written node-wise
floating-point recurrence checks every state. No third-party/project imports.
"""
from fractions import Fraction as F
from pathlib import Path
import hashlib
import json

OUT=Path(__file__).resolve().parent
PAPER=Path('/Users/zanehuang/work/OptiRepro/datasets/benchmarks/cpu30_v1/input/2201.13320/paper.pdf')
MECHANISMS=['paper_initialization','model_descent_with_compressed_consensus','residual_model_compression_accumulation','gradient_tracking_with_old_compressed_gradient_consensus','residual_gradient_compression_accumulation','columnwise_biased_contractive_compression']

def rational(x):
    if isinstance(x,list): return [rational(v) for v in x]
    return F(str(x))
def floats(x):
    if isinstance(x,list): return [floats(v) for v in x]
    return float(x)
def plus(a,b): return [[x+y for x,y in zip(ar,br)] for ar,br in zip(a,b)]
def minus(a,b): return [[x-y for x,y in zip(ar,br)] for ar,br in zip(a,b)]
def scale(k,a): return [[k*x for x in row] for row in a]
def matmul(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]
def grad(x,inp):
    a=rational(inp['quadratic_centers_by_client'])
    d=rational(inp['quadratic_diagonals_by_client'])
    return [[d[i][j]*(x[j][i]-a[i][j]) for i in range(len(a))] for j in range(len(x))]
def compress(x,c):
    if c['name']=='scale': return scale(F(str(c['factor'])),x)
    assert c['name']=='top1'
    y=[[F(0) for _ in row] for row in x]
    for i in range(len(x[0])):
        magnitudes=[abs(x[j][i]) for j in range(len(x))]
        m=max(magnitudes)
        # Cases deliberately avoid nonzero maximum ties; explicit tie rule is public anyway.
        assert m==0 or sum(z==m for z in magnitudes)==1
        selected=magnitudes.index(m)
        y[selected][i]=x[selected][i]
    return y

def matrix_oracle(case):
    inp,par=case['inputs'],case['parameters']
    n=len(inp['mixing_matrix_W']); d=len(inp['initial_common_point'])
    x=[[F(str(inp['initial_common_point'][j])) for _ in range(n)] for j in range(d)]
    h=[[F(0) for _ in range(n)] for _ in range(d)]
    g=[[F(0) for _ in range(n)] for _ in range(d)]
    v=grad(x,inp)
    W=rational(inp['mixing_matrix_W'])
    assert all(W[i][j]==W[j][i] for i in range(n) for j in range(n))
    assert all(sum(row)==1 for row in W)
    D=[[W[i][j]-(1 if i==j else 0) for j in range(n)] for i in range(n)]
    eta=F(str(par['eta'])); gamma=F(str(par['gamma']))
    trace=[{'X':x,'H':h,'V':v,'G':g}]
    detail=[]
    for step in range(1,par['iterations']+1):
        mx=scale(gamma,matmul(h,D))
        xn=minus(plus(x,mx),scale(eta,v))
        rh=minus(xn,h); qh=compress(rh,par['compressor']); hn=plus(h,qh)
        mv=scale(gamma,matmul(g,D))
        dg=minus(grad(xn,inp),grad(x,inp))
        vn=plus(plus(v,mv),dg)
        rg=minus(vn,g); qg=compress(rg,par['compressor']); gn=plus(g,qg)
        # Independent algebraic invariants: doubly stochastic consensus preserves sums.
        assert [sum(row) for row in vn]==[sum(row) for row in grad(xn,inp)]
        assert [sum(row) for row in xn]==[sum(x[j])-eta*sum(v[j]) for j in range(d)]
        # Compression contraction definition checked exactly on every message input.
        alpha=F(str(par['compressor']['contraction_alpha']))
        for residual,message in [(rh,qh),(rg,qg)]:
            for i in range(n):
                assert sum((message[j][i]-residual[j][i])**2 for j in range(d)) <= (1-alpha)*sum(residual[j][i]**2 for j in range(d))
        detail.append({'step':step,'gamma_H_W_minus_I':mx,'Q_h':qh,'gamma_G_W_minus_I':mv,'gradient_difference':dg,'Q_g':qg})
        x,h,v,g=xn,hn,vn,gn
        trace.append({'X':x,'H':h,'V':v,'G':g})
    return trace,detail

def client_oracle(case):
    # A distinct scalar implementation with client-major arrays, independent from
    # the exact matrix helpers above, directly spells out each neighbor sum.
    inp,par=case['inputs'],case['parameters']
    a=inp['quadratic_centers_by_client']; diag=inp['quadratic_diagonals_by_client']
    n=len(a); d=len(a[0]); w=inp['mixing_matrix_W']
    x=[list(map(float,inp['initial_common_point'])) for i in range(n)]
    h=[[0.0]*d for i in range(n)]; g=[[0.0]*d for i in range(n)]
    v=[[diag[i][j]*(x[i][j]-a[i][j]) for j in range(d)] for i in range(n)]
    trace=[]
    def columns(nodes): return [[nodes[i][j] for i in range(n)] for j in range(d)]
    def message(z):
        if par['compressor']['name']=='scale': return [value*par['compressor']['factor'] for value in z]
        chosen=sorted(range(d),key=lambda j:(-abs(z[j]),j))[0]
        return [z[j] if j==chosen else 0.0 for j in range(d)]
    for t in range(par['iterations']+1):
        trace.append({key:columns(val) for key,val in [('X',x),('H',h),('V',v),('G',g)]})
        if t==par['iterations']: break
        nx=[]; nh=[]; nv=[]; ng=[]
        for i in range(n):
            local=[]
            for j in range(d):
                mixed=sum(w[i][neighbor]*(h[neighbor][j]-h[i][j]) for neighbor in range(n))
                local.append(x[i][j]+par['gamma']*mixed-par['eta']*v[i][j])
            nx.append(local)
        for i in range(n):
            msg=message([nx[i][j]-h[i][j] for j in range(d)])
            nh.append([h[i][j]+msg[j] for j in range(d)])
            local=[]
            for j in range(d):
                mixed=sum(w[i][neighbor]*(g[neighbor][j]-g[i][j]) for neighbor in range(n))
                delta=diag[i][j]*(nx[i][j]-a[i][j])-diag[i][j]*(x[i][j]-a[i][j])
                local.append(v[i][j]+par['gamma']*mixed+delta)
            nv.append(local)
        for i in range(n):
            msg=message([nv[i][j]-g[i][j] for j in range(d)])
            ng.append([g[i][j]+msg[j] for j in range(d)])
        x,h,v,g=nx,nh,nv,ng
    return trace

OBS={
 'state_layout':'All observed X,H,V,G matrices have shape [dimension][number_of_clients]; columns index clients in the same order as W rows/columns. Objectives below use [client][dimension] arrays.',
 'step_semantics':'Step 0 is immediately after Algorithm 1 initialization. Step t>=1 is after completing lines 3-8 for iteration t-1. Report exactly X,H,V,G at every requested step. Q_h,Q_g and averages are not requested observations.',
 'initialization':'X^0 has every column equal to initial_common_point; H^0=G^0=zero matrices; V^0=the exact local gradient at each corresponding column of X^0.',
 'objective':'Client i has f_i(x)=0.5*sum_j quadratic_diagonals_by_client[i][j]*(x[j]-quadratic_centers_by_client[i][j])^2. Gradient coordinate j is diagonal[i][j]*(x[j]-center[i][j]). Global f is (1/n)*sum_i f_i. No extra regularization, momentum, projection, clipping, or stochastic noise.',
 'update_order':'Execute Algorithm 1: Xnew=X+gamma*H*(W-I)-eta*V; Qh=C(Xnew-H); Hnew=H+Qh; Vnew=V+gamma*G*(W-I)+gradF(Xnew)-gradF(X); Qg=C(Vnew-G); Gnew=G+Qg. Unsubscripted X,H,V,G on right sides denote pre-round values, except the explicitly named Xnew/Vnew.',
 'compression_scope':'Invoke the same deterministic compressor independently on each client column of each residual matrix, for both the H and G channels. Do not compress globally across the matrix or compress the raw X/V in place of residuals.'
}
cases=[
 {'id':'beer_top1_two_clients_three_rounds',
  'purpose':'Activate biased sparse communication, residual accumulation and support changes in both control sequences, and distinguish gradient tracking from plain local gradients after consensus starts.',
  'covers':MECHANISMS[:],
  'inputs':{'initial_common_point':[1,-1],'quadratic_centers_by_client':[[-1,2],[3,-2]],'quadratic_diagonals_by_client':[[1,1],[2,2]],'mixing_matrix_W':[[0.75,0.25],[0.25,0.75]]},
  'parameters':{'eta':0.1,'gamma':0.5,'iterations':3,'gradient_oracle':'full_deterministic','minibatch_size':1,'compressor':{'name':'top1','rule':'Retain the original value at the coordinate of largest absolute value; set all other coordinates to zero. On an exact tie choose the lowest zero-based coordinate index. C(0)=0. No rescaling.','contraction_alpha':0.5},'observation_semantics':OBS},
  'derivation':'Algorithm 1 p.7 uses exactly its specified common-point initialization. Initial gradients are columns (2,-3),(-4,2). Because H0=G0=0, first-round consensus increments are zero, yet gradient descent and both compression channels are nonzero. At round 2, H1 has row (0.8,1.4) while G1 has columns (0,-2.7),(-3.2,0), producing distinct model/gradient consensus increments. Nonzero Top1 maximum ties are absent throughout. Later Qh/Qg retain previously omitted residual components, so replacing the accumulated controls by compressed raw values is distinguishable.',
  'atol':1e-9,'rtol':1e-7},
 {'id':'beer_half_compressor_three_client_path',
  'purpose':'Exercise a different valid biased contractive map on both residual channels with a noncomplete graph, dimension unequal to client count, and client-specific anisotropic quadratic curvature.',
  'covers':MECHANISMS[:],
  'inputs':{'initial_common_point':[-1,2],'quadratic_centers_by_client':[[2,-1],[-2,3],[1,0]],'quadratic_diagonals_by_client':[[1,2],[2,1],[3,1]],'mixing_matrix_W':[[0.75,0.25,0],[0.25,0.5,0.25],[0,0.25,0.75]]},
  'parameters':{'eta':0.125,'gamma':0.25,'iterations':3,'gradient_oracle':'full_deterministic','minibatch_size':1,'compressor':{'name':'scale','factor':0.5,'rule':'For every residual vector v return C(v)=0.5*v, coordinatewise. This deterministic biased map satisfies Definition 2.2 with alpha=0.75; it is an algebraic compression-map test, not a claim of bit savings.','contraction_alpha':0.75},'observation_semantics':OBS},
  'derivation':'Initial gradients are columns (-3,6),(2,-1),(-6,2). Use the exact Algorithm 1 initialization, not H0=X0 or G0=V0. The path mixing matrix is symmetric doubly stochastic and connected; its eigenvalues are 1,0.75,0.25. The compressor obeys ||C(v)-v||^2=0.25||v||^2, so alpha=0.75 is valid, although this scaling map alone is not a sparse encoding. Both Hnew=0.5*H+0.5*Xnew and Gnew=0.5*G+0.5*Vnew retain old information. Each client gradient difference uses its own diagonal curvature.',
  'atol':1e-9,'rtol':1e-7}
]
report=[]
for case in cases:
    trace,detail=matrix_oracle(case)
    reference=client_oracle(case)
    for t,(a,b) in enumerate(zip(trace,reference)):
        for name in ['X','H','V','G']:
            assert all(abs(float(a[name][j][i])-b[name][j][i])<1e-12 for j in range(len(a[name])) for i in range(len(a[name][0]))),(case['id'],t,name)
    case['expected']=[{'step':t,'name':name,'value':floats(state[name])} for t,state in enumerate(trace) for name in ['X','H','V','G']]
    case['derivation']+='\nAll following matrices are coordinate-by-client. Exact rational arithmetic generated the values; an independent client-wise floating-point recurrence checked every state to 1e-12. At each round, sums of V and exact local gradients agree, and sum(Xnew)=sum(Xold)-eta*sum(Vold).\n'
    case['derivation']+='Initial state: '+json.dumps({k:floats(v) for k,v in trace[0].items()},separators=(',',':'))+'\n'
    for t,parts in enumerate(detail,1):
        case['derivation']+='Round '+str(t)+' intermediate arithmetic: '+json.dumps({k:floats(v) if isinstance(v,list) else v for k,v in parts.items()},separators=(',',':'))+'\n'
        case['derivation']+='Round '+str(t)+' states: '+json.dumps({k:floats(v) for k,v in trace[t].items()},separators=(',',':'))+'\n'
    report.append({'case':case['id'],'final':{k:floats(v) for k,v in trace[-1].items()},'detail':[{k:floats(v) if isinstance(v,list) else v for k,v in r.items()} for r in detail]})
contract={
 'schema_version':'optirepro.paper_algorithm_contract.v1',
 'paper':{'paper_id':'2201.13320','title':'BEER: Fast O(1/T) Rate for Decentralized Nonconvex Optimization with Communication Compression','sha256':hashlib.sha256(PAPER.read_bytes()).hexdigest()},
 'algorithm':{'name':'BEER (Algorithm 1), full-gradient deterministic specialization',
  'citations':['PDF p.4 Assumption 2.1 and Eq.(2): symmetric doubly stochastic mixing W with positive spectral gap.','PDF p.5 Definition 2.2, Eq.(3): E||C(v)-v||^2 <= (1-alpha)||v||^2; biased compression is allowed.','PDF p.6 Section 3 matrix notation: X=[x1,...,xn] is d by n and compression applies independently to columns.','PDF p.7 Algorithm 1 line 1: common X0, H0=G0=0 and V0=grad F(X0).','PDF p.7 Algorithm 1 lines 3-5: descent using V and consensus using H, then compress Xnew-H and accumulate into H.','PDF p.7 Algorithm 1 lines 6-8: gradient tracking using old G consensus plus consecutive gradient difference, then compress Vnew-G and accumulate into G.','PDF p.7 Section 4.1: exact full gradients may replace stochastic minibatch gradients when local variance is zero.'],
  'core_mechanisms':MECHANISMS,
  'assumptions':['The allowed source is only the designated arXiv:2201.13320v3 PDF. Cases are independently derived finite trajectories; no implementation or prior evaluation output was consulted.','The deterministic diagonal quadratic objectives are smooth, bounded below, have a minimizer, and are a valid zero-variance specialization. They test the algorithmic recurrence, not nonconvex convergence rates or stochastic minibatch sampling.','Mixing matrices are symmetric, nonnegative, doubly stochastic, connected and have positive spectral gap: first case eigenvalues (1,0.5), second case (1,0.75,0.25).','Top1 in dimension two satisfies Definition 2.2 with alpha=1/2; scaling by 1/2 satisfies it with alpha=3/4. The scale case tests the mathematical compressor interface and makes no claim of actual communication savings.','The finite input step sizes are explicit; the paper convergence theorem contains unspecified absolute constants, so these three-round probes do not claim a theorem-certified learning-rate choice or eventual convergence.','Matrix and objective layouts, exact gradient formula, compressor tie rule, initialization, update order, observation timing and output names are fully specified in each public case.','The paper does not prescribe a generic software return object or stopping rule. After exactly three full rounds, observe all four algorithm states; no implicit averaging or random-iterate selection is used.']},
 'cases':cases}
(OUT/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps(report,indent=2))
print('paper_sha256',contract['paper']['sha256'])
print('contract_file_sha256',hashlib.sha256((OUT/'contract.json').read_bytes()).hexdigest())
print('crosscheck: every state matched; exact gradient-sum and model-sum invariants passed; compressor contraction passed')
