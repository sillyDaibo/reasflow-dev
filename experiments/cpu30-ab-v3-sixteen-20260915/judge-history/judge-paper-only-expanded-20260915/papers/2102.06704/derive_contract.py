#!/usr/bin/env python3
"""Paper-only oracle. No implementation, benchmark metadata or run artifacts are read.
Rational recurrences are independently checked using affine compositions and KKT;
logistic recurrences use 80-digit Decimal and independent binary64 math.
"""
from pathlib import Path
from fractions import Fraction as Q
from decimal import Decimal as D, localcontext
import hashlib
import importlib.util
import json
import math

ROOT = Path('/Users/zanehuang/work/OptiRepro')
PDF = ROOT / 'datasets/benchmarks/cpu30_v1/input/2102.06704/paper.pdf'
SCHEMA = ROOT / 'repo_judge/src/judge/paper_contract.py'
OUT = Path(__file__).resolve().parent


def numeric(x):
    if isinstance(x, (Q, D)):
        return float(x)
    if isinstance(x, (list, tuple)):
        return [numeric(v) for v in x]
    return x


def exact(x):
    if isinstance(x, (Q, D)):
        return str(x)
    if isinstance(x, list):
        return [exact(v) for v in x]
    return x


def prox(v, alpha, l1, l2):
    return [(1 if z > 0 else -1) * max(abs(z)-alpha*l1, 0)/(1+alpha*l2) for z in v]


def kkt(v, z, alpha, l1, l2):
    # Independent optimality check of alpha*(l1*|x|+l2*x^2/2)+(x-z)^2/2.
    for x, u in zip(v, z):
        if x:
            assert x-u+alpha*(l2*x+(l1 if x>0 else -l1)) == 0
        else:
            assert abs(u) <= alpha*l1


def quad_path(x, diagonals, centers, order, gamma):
    initial = x[:]
    trajectory = []
    for j in order:
        x = [v-gamma*Q(a)*(v-Q(c)) for v,a,c in zip(x,diagonals[j],centers[j])]
        trajectory.append(x)
    # Independent affine map composition for every coordinate.
    for coordinate in range(len(x)):
        slope, intercept = Q(1), Q(0)
        for j in order:
            r = 1-gamma*diagonals[j][coordinate]
            slope, intercept = r*slope, r*intercept+gamma*diagonals[j][coordinate]*centers[j][coordinate]
        assert x[coordinate] == slope*initial[coordinate]+intercept
    return trajectory


def observation(step, name, value):
    return {'step':step,'name':name,'value':numeric(value)}


M = ['sequential_permuted_epoch', 'single_epoch_end_prox_with_n_scaling',
     'elastic_net_threshold_and_quadratic_shrinkage', 'epoch_specific_stepsize',
     'separate_complete_client_epochs', 'equal_device_average_then_N_over_M_prox']
OBS_PROX = {'step':'One-based completed epoch; step 1 is t=0.',
            'inner_iterates':'Rows are x_t^1 through x_t^n in supplied sample order, before any regularizer operation.',
            'iterate':'x_(t+1), after the single epoch-end proximal operation.'}
COMMON = {'objective_normalization':'P(x)=(1/n)*sum_i f_i(x)+psi(x). Component gradients are NOT divided by n.',
          'regularizer':'psi(x)=lambda1*sum_j abs(x_j)+(lambda2/2)*sum_j x_j^2.',
          'prox_convention':'prox_(alpha psi)(v)=argmin_z alpha*psi(z)+0.5*||z-v||_2^2; coordinate result is sign(v_j)*max(abs(v_j)-alpha*lambda1,0)/(1+alpha*lambda2).',
          'sample_index_base':0,'permutation_policy':'Condition on the explicitly supplied permutation for each epoch; do not generate or sort a different order.',
          'gradient_evaluation':'At the latest inner iterate; no prox or added regularizer gradient inside an epoch.',
          'observations':OBS_PROX}

A = [[1,3],[2,1],[4,2]]
C = [[3,-1],[-2,2],[1,-3]]
orders = [[2,0,1],[1,2,0],[0,1,2]]
gammas = [Q(1,8),Q(1,16),Q(1,8)]
x = [Q(2),Q(-1)]
expected, traces = [], []
for step,(g,order) in enumerate(zip(gammas,orders),1):
    path = quad_path(x,A,C,order,g)
    x = prox(path[-1],3*g,Q(1,4),Q(1,2))
    kkt(x,path[-1],3*g,Q(1,4),Q(1,2))
    expected += [observation(step,'inner_iterates',path),observation(step,'iterate',x)]
    traces.append({'epoch':step,'inner_iterates':exact(path),'iterate':exact(x)})
assert x == [Q(179411,462080),Q(-2534889,2957312)]
case1 = {'id':'proxrr_quadratic_three_epochs','purpose':'Order-sensitive convex component steps, changing epoch learning rates, and exactly one n-scaled elastic-net prox per epoch.',
    'covers':M[:4],
    'inputs':{'x0':[2,-1],'loss':'f_i(x)=0.5*sum_j diagonal_i[j]*(x_j-center_i[j])^2; gradient_j=diagonal_i[j]*(x_j-center_i[j]).',
              'diagonals':A,'centers':C,'epoch_sample_orders':orders},
    'parameters':dict(COMMON,algorithm='ProxRR',n=3,dimension=2,epochs=3,epoch_stepsizes=numeric(gammas),lambda1=0.25,lambda2=0.5),
    'derivation':'Algorithm 1 (PDF p.3, lines 4-7): x <- x-gamma_t*diag_i*(x-center_i), then alpha=3*gamma_t. Apply the elastic-net formula on PDF p.21. All entries below are exact fractions, cross-checked by affine-map composition and proximal KKT: '+json.dumps(traces),
    'expected':expected,'atol':1e-10,'rtol':1e-9}

features = [[1,2],[-2,1],[1,-1]]
labels = [1,0,1]
orders2 = [[2,0,1],[1,2,0],[0,1,2]]
gammas2 = ['0.25','0.125','0.0625']
expected, traces = [], []
with localcontext() as context:
    context.prec = 80
    x = [D('0.6'),D('-0.2')]
    xf = [0.6,-0.2]
    for step,(gs,order) in enumerate(zip(gammas2,orders2),1):
        g, gf = D(gs), float(gs)
        path = []
        for j in order:
            dot = sum(D(a)*v for a,v in zip(features[j],x))
            residual = 1/(1+(-dot).exp())-labels[j]
            x = [v-g*D(a)*residual for a,v in zip(features[j],x)]
            # Separate binary64 evaluation; check each coordinate and each step.
            residual_f = 1/(1+math.exp(-sum(a*v for a,v in zip(features[j],xf))))-labels[j]
            xf = [v-gf*a*residual_f for a,v in zip(features[j],xf)]
            assert all(abs(float(v)-w)<2e-15 for v,w in zip(x,xf))
            path.append(x[:])
        alpha = 3*g
        x = prox(x,alpha,D('0.3'),D('0.4'))
        xf = [math.copysign(max(abs(v)-3*gf*0.3,0.0),v)/(1+3*gf*0.4) for v in xf]
        assert all(abs(float(v)-w)<2e-15 for v,w in zip(x,xf))
        assert x[0] > 0 and x[1] == 0
        expected += [observation(step,'inner_iterates',path),observation(step,'iterate',x)]
        traces.append({'epoch':step,'inner_iterates':exact(path),'iterate':exact(x)})
case2 = {'id':'proxrr_logistic_elastic_net_three_epochs',
    'purpose':'Use the paper experimental logistic objective with nonzero positive and negative margins and a genuinely active soft threshold that zeros a coordinate after every epoch.',
    'covers':M[:4],
    'inputs':{'x0':[0.6,-0.2],'features':features,'labels':labels,'epoch_sample_orders':orders2,
              'loss':'f_i(x)=-b_i*log(h(a_i^T*x))-(1-b_i)*log(1-h(a_i^T*x)); h(s)=1/(1+exp(-s)); gradient=(h(a_i^T*x)-b_i)*a_i. No intercept is added.'},
    'parameters':dict(COMMON,algorithm='ProxRR',n=3,dimension=2,epochs=3,epoch_stepsizes=list(map(float,gammas2)),lambda1=0.3,lambda2=0.4),
    'derivation':'PDF p.8 Eq.(14) defines the sample loss and elastic net. Differentiate the sample loss to get (h(a_i^T*x)-b_i)*a_i; Algorithm 1 p.3 uses that gradient in the given order, then p.21 prox with alpha=3*gamma_t. Computed at 80 Decimal digits; independently checked by binary64 exp at every inner and outer iterate. Decimal trajectories: '+json.dumps(traces),
    'expected':expected,'atol':1e-10,'rtol':1e-9}

Ad = [[[2,1],[1,3]],[[1,2],[3,1],[2,4]]]
Cd = [[[3,-1],[-1,2]],[[-2,1],[2,-3],[0,2]]]
fed_orders = [[[1,0],[2,0,1]],[[0,1],[1,2,0]],[[1,0],[0,2,1]]]
x = [Q(1),Q(-2)]
g = Q(1,8)
expected, traces = [], []
for step,client_orders in enumerate(fed_orders,1):
    paths = [quad_path(x,Ad[m],Cd[m],client_orders[m],g) for m in range(2)]
    ends = [p[-1] for p in paths]
    mean = [sum(v[j] for v in ends)/2 for j in range(2)]
    weighted = [(2*ends[0][j]+3*ends[1][j])/5 for j in range(2)]
    assert mean != weighted
    alpha = g*5/2
    x = prox(mean,alpha,Q(1,10),Q(1,2))
    kkt(x,mean,alpha,Q(1,10),Q(1,2))
    # Independently check consensus prox stationarity in product space:
    # gamma*N*R(u) + 1/2*sum_m ||u-end_m||^2.
    for j in range(2):
        if x[j]:
            assert sum(x[j]-v[j] for v in ends)+g*5*(Q(1,2)*x[j]+(Q(1,10) if x[j]>0 else -Q(1,10))) == 0
        else:
            assert abs(sum(v[j] for v in ends)) <= g*5*Q(1,10)
    first = [p[0] for p in paths]
    expected += [observation(step,'local_after_first_sample',first),observation(step,'local_endpoints',ends),observation(step,'aggregate',mean),observation(step,'iterate',x)]
    traces.append({'epoch':step,'local_trajectories':exact(paths),'local_endpoints':exact(ends),'aggregate':exact(mean),'iterate':exact(x)})
case3 = {'id':'fedrr_unequal_clients_three_rounds',
    'purpose':'Exercise independent local full passes on heterogeneous clients with unequal sample counts, reset from the preceding global iterate, equal device weighting and gamma*N/M regularization.',
    'covers':['sequential_permuted_epoch','elastic_net_threshold_and_quadratic_shrinkage','separate_complete_client_epochs','equal_device_average_then_N_over_M_prox'],
    'inputs':{'x0':[1,-2],'client_sample_counts':[2,3],'client_diagonals':Ad,'client_centers':Cd,'epoch_client_sample_orders':fed_orders,
              'loss':'f_mi(x)=0.5*sum_j client_diagonals[m][i][j]*(x_j-client_centers[m][i][j])^2; gradient_j=client_diagonals[m][i][j]*(x_j-client_centers[m][i][j]).'},
    'parameters':{'algorithm':'FedRR','dimension':2,'epochs':3,'M':2,'N':5,'n':3,'stepsize':0.125,'lambda1':0.1,'lambda2':0.5,
        'objective_normalization':'P(x)=(1/N)*sum_m sum_i f_mi(x)+R(x). Each local sample gradient is unnormalized.',
        'regularizer':'R(x)=lambda1*sum_j abs(x_j)+(lambda2/2)*sum_j x_j^2.',
        'prox_convention':COMMON['prox_convention'].replace('psi','R'),
        'sample_index_base':0,'client_index_base':0,'permutation_policy':'Use the given order separately for each client and epoch. The order lists contain only real samples.',
        'local_update':'Each round begins with every client at x_t. Client m performs N_m sequential sample gradient steps with constant gamma and no regularizer. For padding to n=max_m N_m, dummy losses have zero gradient and leave the completed local state unchanged.',
        'server_update':'z_(t+1)=(1/M)*sum_m local_endpoint_m; x_(t+1)=prox_(gamma*N/M*R)(z_(t+1)). All clients participate in every round.',
        'observations':{'step':'One-based completed communication round; step 1 is t=0.',
            'local_after_first_sample':'Rows are the two clients, each after its first real sample gradient update in this round.',
            'local_endpoints':'Rows are the two clients after all their real sample updates, before aggregation.',
            'aggregate':'Equal-weight mean z_(t+1) of completed client vectors before regularization.',
            'iterate':'Global x_(t+1) after server proximal operation.'}},
    'derivation':'PDF p.7 Algorithm 3 lines 4-9 uses unnormalized sample gradients, copies each completed local state through zero padding, averages by M, and applies prox_(gamma*N/M*R). Here N=5, M=2, n=3, gamma=1/8 and alpha=5/16, so threshold=1/32 and shrinkage denominator=37/32. All numbers are exact fractions checked by affine map composition, scalar prox KKT and product-space consensus stationarity. Equal device averages differ from sample-count-weighted averages in every round. Exact trajectories: '+json.dumps(traces),
    'expected':expected,'atol':1e-10,'rtol':1e-9}

contract = {'schema_version':'optirepro.paper_algorithm_contract.v1',
    'paper':{'paper_id':'2102.06704','title':'Proximal and Federated Random Reshuffling','sha256':hashlib.sha256(PDF.read_bytes()).hexdigest()},
    'algorithm':{'name':'Proximal Random Reshuffling (ProxRR) and Federated Random Reshuffling (FedRR)',
        'citations':['PDF p.1 Eq.(1) and Assumption 1: composite finite-sum objective.',
            'PDF p.2: proximal operator definition; p.3 Algorithm 1 lines 3-7: ProxRR.',
            'PDF p.7 Eq.(13) and Algorithm 3 lines 4-9: product-space reformulation and FedRR.',
            'PDF p.8 Eq.(14): logistic regression with elastic net.',
            'PDF p.21, Proximal operator calculation: elastic-net shrinkage and soft threshold.'],
        'core_mechanisms':M,
        'assumptions':['These are synthetic deterministic algorithm experiments derived only from the original PDF, not benchmark recreation or claims about statistical convergence.',
            'All page numbers are one-based physical PDF pages. Original is arXiv:2102.06704v1 dated 12 Feb 2021.',
            'All component objectives are smooth and convex, and all regularizers are proper closed convex elastic nets. Quadratic maximum smoothness is 4; all chosen quadratic stepsizes are at most 1/4.',
            'Supplied order lists fix realizations of reshuffling randomness. Each list is a full permutation; no RNG seed convention is needed.',
            'ProxRR gamma_t is supplied explicitly and is constant within each epoch, as allowed by Algorithm 1. The test does not invoke the specific theoretical schedule in Eq.(11).',
            'The federated test follows the general unequal-sample Algorithm 3; the equal-sample restrictions of later convergence theorems are not imposed on the algorithm.',
            'Coverage focuses on Algorithms 1 and 3. Shuffle-Once, importance resampling, convergence bounds and empirical performance claims are outside this finite numeric contract.']},
    'cases':[case1,case2,case3]}
spec = importlib.util.spec_from_file_location('paper_contract_schema',SCHEMA)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.validate_contract(contract,paper_sha256=contract['paper']['sha256'])
(OUT/'contract.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

review = '''# Paper-only review: 2102.06704

Source boundary: only the specified original paper PDF, the contract schema, global AGENTS.md and the PDF skill were read. No implementation, run directory, benchmark metadata, card, existing expected values, repository documentation or external source was consulted. The synthetic inputs were chosen before any implementation inspection. The standard must remain frozen when an implementation is later evaluated.

## Paper interpretation and visual checks

The PDF is “Proximal and Federated Random Reshuffling,” arXiv:2102.06704v1 (12 February 2021), 21 pages. Physical PDF pages 1, 2, 3, 7, 8 and 21 were rendered with PyMuPDF at 1.4x and inspected using view_image. On page 3, Algorithm 1 lines 4–7 initialize the epoch, evaluate n sequential sample gradients, and apply exactly one prox with coefficient gamma_t*n. Page 7 Algorithm 3 lines 4–9 resets local models to the global state, executes each complete local data pass, averages devices with 1/M, and uses coefficient gamma*N/M on R. Thus unequal local sample counts must not silently become sample-weighted server averaging. Page 21 supplies the exact elastic-net proximal formula. Page 8 Eq.(14) specifies the logistic loss with labels in {0,1}.

## Three frozen experiments

1. **proxrr_quadratic_three_epochs**: 3 two-dimensional diagonal quadratic components, different centers/curvatures, three supplied permutations and stepsizes 1/8, 1/16, 1/8. Nonzero elastic-net regularization acts only at each epoch end. All 9 inner vectors and 3 outer iterates are required.
2. **proxrr_logistic_elastic_net_three_epochs**: the paper's logistic loss with 3 samples in 2 dimensions, three supplied permutations and decreasing supplied epoch stepsizes. lambda1=0.3 and lambda2=0.4 produce a nonzero first coordinate and a thresholded zero second coordinate after every epoch. All 9 inner vectors and 3 outer iterates are required. This exercises the nonlinear loss and a proximal branch absent from the first experiment.
3. **fedrr_unequal_clients_three_rounds**: 2 heterogeneous clients with 2 and 3 quadratic samples, three rounds and changing per-client permutations. gamma=1/8 gives alpha=5/16, threshold=1/32 and denominator=37/32. Each round records the first local update, local endpoints, the unregularized equal-weight average, and the new global model. Local vectors diverge, server regularization is nonzero, and device-weighted and sample-weighted averages differ in every round.

The public inputs specify objectives, gradient normalization, regularizers, all coefficients, explicit sample order, state naming and step indexing. Observations are algorithm states only; optimizer counters, proxy flags, convergence quantities and diagnostic packaging are not required. Tolerances (atol=1e-10, rtol=1e-9) accommodate ordinary binary64 arithmetic without accepting mechanism-scale deviations.

## Independent arithmetic verification

The quadratic and federated oracles use exact Fraction arithmetic. Each local sequence is independently checked against affine-map composition. Every rational proximal update satisfies coordinatewise KKT conditions; federated outputs also satisfy product-space consensus optimality. Logistic expected values use 80-digit Decimal exponentials and are independently checked against a separately evaluated binary64 recurrence at every inner and outer step (difference < 2e-15). The derivation text in contract.json contains the complete exact-fraction or high-precision trajectory. The schema validator is imported directly from the sole allowed schema file and validates the complete contract and the actual PDF hash.

## Scope and caveats

These tests check finite trajectories of central Algorithms 1 and 3, not convergence rates, runtime, random-permutation distribution, importance resampling or Shuffle-Once. Fixed permutations are conditioned random realizations, not a replacement sampling algorithm. The specified ProxRR stepsizes are valid inputs to Algorithm 1 and do not assert fidelity to the optional theorem schedule in Eq.(11). Unequal client sizes are explicitly allowed by Algorithm 3 even though subsequent convergence statements simplify to equal sizes. Quadratic losses are synthetic instances of the paper's general smooth convex objective; the second case additionally matches its empirical loss family. No attempt is made to infer undocumented benchmark choices.

To reproduce: run `/tmp/optirepro-paper-judge-20260915/bin/python derive_contract.py` from any directory. The builder deterministically rewrites this review, contract.json and SHA256SUMS and reads no implementation data.
'''
review += '\n## Bound hashes\n\nPDF SHA256: `'+contract['paper']['sha256']+'`\n\nCanonical contract digest: `'+module.contract_digest(contract)+'`\n'
(OUT/'PAPER_REVIEW.md').write_text(review)
files = ['contract.json','derive_contract.py','PAPER_REVIEW.md']
(OUT/'SHA256SUMS').write_text(''.join(hashlib.sha256((OUT/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in files))
print(json.dumps({'validated':True,'paper_sha256':contract['paper']['sha256'],'canonical_contract_digest':module.contract_digest(contract),'final_iterates':{c['id']:c['expected'][-1]['value'] for c in contract['cases']}},indent=2))
print((OUT/'SHA256SUMS').read_text())
