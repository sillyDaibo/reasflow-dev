#!/usr/bin/env python3
"""Independent paper-only arithmetic; no implementation, datasets or run artifacts read.
Primary: exact Fraction arithmetic for quadratic cases, Decimal(70) for Poisson.
Cross-check: NumPy floating point, Poisson derivative bisection, KKT identities.
"""
from pathlib import Path
from fractions import Fraction
from decimal import Decimal, localcontext
import hashlib, importlib.util, json
import numpy as np

HERE = Path(__file__).resolve().parent
PAPER = Path('/Users/zanehuang/work/OptiRepro/datasets/benchmarks/cpu30_v1/input/1904.12017/paper.pdf')
SCHEMA = Path('/Users/zanehuang/work/OptiRepro/repo_judge/src/judge/paper_contract.py')
MECHANISMS = ['local_loss_proximal_update', 'local_regularizer_proximal_update', 'regularized_laplacian_consensus', 'two_scaled_dual_updates']


def solve(a, b):
    """Gauss-Jordan solve, exact rational or high precision Decimal."""
    n = len(b)
    a = [list(row) + [b[i]] for i, row in enumerate(a)]
    for j in range(n):
        k = next(k for k in range(j, n) if a[k][j] != 0)
        a[j], a[k] = a[k], a[j]
        v = a[j][j]
        a[j] = [z / v for z in a[j]]
        for k in range(n):
            if k != j:
                v = a[k][j]
                a[k] = [z - v * w for z, w in zip(a[k], a[j])]
    return [row[-1] for row in a]


def primary(case):
    C = Decimal if case['inputs']['loss']['type'] == 'poisson' else Fraction
    def c(x): return C(str(x))
    inp, par = case['inputs'], case['parameters']
    K, n = len(inp['L']), par['parameter_dimension']
    lam, reg = c(par['lambda']), c(inp['regularizer']['coefficient'])
    L = [[c(z) for z in row] for row in inp['L']]
    A = [[L[k][h] + (c(2)/lam if k == h else c(0)) for h in range(K)] for k in range(K)]
    hat = [[c(0)]*n for _ in range(K)]
    u = [[c(0)]*n for _ in range(K)]
    ut = [[c(0)]*n for _ in range(K)]
    states = []
    for step in range(1, par['iterations']+1):
        theta, tilde = [], []
        for k in range(K):
            v = [hat[k][j] - u[k][j] for j in range(n)]
            if inp['loss']['type'] == 'quadratic':
                Q = [[c(z) for z in row] for row in inp['loss']['Q'][k]]
                b = [c(z) for z in inp['loss']['b'][k]]
                theta.append(solve([[c(int(i==j))+lam*Q[i][j] for j in range(n)] for i in range(n)], [v[i]-lam*b[i] for i in range(n)]))
            else:
                N, S = c(inp['loss']['counts'][k]), c(inp['loss']['sums'][k])
                d = v[0]-lam*N
                theta.append([(d+(d*d+c(4)*lam*S).sqrt())/c(2)])
            v = [hat[k][j] - ut[k][j] for j in range(n)]
            if inp['regularizer']['type'] == 'ridge':
                tilde.append([z/(c(1)+lam*reg) for z in v])
            else:
                tilde.append([max(z-lam*reg,c(0))-max(-z-lam*reg,c(0)) for z in v])
        newhat = [[c(0)]*n for _ in range(K)]
        for j in range(n):
            x = solve(A, [(theta[k][j]+u[k][j]+tilde[k][j]+ut[k][j])/lam for k in range(K)])
            for k in range(K): newhat[k][j] = x[k]
        u = [[u[k][j]+theta[k][j]-newhat[k][j] for j in range(n)] for k in range(K)]
        ut = [[ut[k][j]+tilde[k][j]-newhat[k][j] for j in range(n)] for k in range(K)]
        hat = newhat
        for k in range(K):
            for j in range(n):
                error = u[k][j]+ut[k][j]-lam*sum(L[k][h]*hat[h][j] for h in range(K))
                assert abs(error) < c('1e-60')
        states.append(dict(theta=theta, theta_tilde=tilde, theta_hat=hat, u=u, u_tilde=ut))
    return states


def crosscheck(case, exact):
    """Separate floating-point trajectory. Scalar Poisson minimizers use bisection,
    not the primary closed form. Check first-order/subgradient and consensus KKT.
    """
    inp, par = case['inputs'], case['parameters']
    L = np.array(inp['L'], dtype=float)
    K, n = len(L), par['parameter_dimension']
    lam, reg = par['lambda'], inp['regularizer']['coefficient']
    H = np.zeros((K,n)); U = H.copy(); V = H.copy()
    worst = 0.
    for step in range(par['iterations']):
        X = np.zeros_like(H)
        if inp['loss']['type'] == 'quadratic':
            for k, (q,b) in enumerate(zip(inp['loss']['Q'], inp['loss']['b'])):
                q, b = np.array(q,float), np.array(b,float)
                assert np.linalg.eigvalsh(q).min() >= -1e-12
                X[k] = np.linalg.solve(q+np.eye(n)/lam, (H[k]-U[k])/lam-b)
                assert np.max(np.abs(q@X[k]+b+(X[k]-H[k]+U[k])/lam)) < 1e-12
        else:
            for k,(N,S) in enumerate(zip(inp['loss']['counts'],inp['loss']['sums'])):
                v = float((H-U)[k,0]); lo=1e-14; hi=max(1.,v+lam*S+1.)
                def grad(x): return N-S/x+(x-v)/lam
                while grad(hi)<0: hi*=2
                for _ in range(160):
                    mid=(lo+hi)/2
                    if grad(mid)>0: hi=mid
                    else: lo=mid
                X[k,0]=(lo+hi)/2
                assert abs(grad(X[k,0]))<1e-12
        center = H-V
        if inp['regularizer']['type']=='ridge':
            T=center/(1+lam*reg)
            assert np.max(abs(reg*T+(T-center)/lam))<1e-12
        else:
            T=np.sign(center)*np.maximum(abs(center)-lam*reg,0)
            sub=(center-T)/lam
            assert np.all(abs(sub[T==0]) <= reg+1e-12)
            assert np.max(abs(sub[T!=0]-reg*np.sign(T[T!=0])),initial=0)<1e-12
        H=np.linalg.solve(lam*L+2*np.eye(K), X+U+T+V)
        U=U+X-H; V=V+T-H
        assert np.max(abs(U+V-lam*L@H))<1e-12
        for name,actual in dict(theta=X,theta_tilde=T,theta_hat=H,u=U,u_tilde=V).items():
            want=np.array([[float(z) for z in row] for row in exact[step][name]])
            worst=max(worst,float(np.max(abs(want-actual))))
            assert np.allclose(want,actual,atol=2e-13,rtol=2e-13)
    return worst


def case(id, purpose, L, loss, regularizer, lam, n):
    return dict(id=id,purpose=purpose,covers=MECHANISMS.copy(),inputs=dict(L=L,loss=loss,regularizer=regularizer),parameters=dict(**{'lambda':lam},parameter_dimension=n,iterations=4,initialization='all five K by n state arrays are zero',penalty_adaptation=False,early_stopping=False,linear_solve='Solve Eq. (5) to numerical accuracy; solver choice is unrestricted.',observations='At end of complete iteration s, theta is loss proximal state, theta_tilde regularizer proximal state, theta_hat graph consensus, u and u_tilde the newly updated scaled dual states. Shapes are K by n, including n=1.'),atol=1e-9,rtol=1e-8)


def build():
    cases=[
        case('correlated_quadratic_ridge','Exercise non-diagonal local Hessians, unequal graph weights, both parameter columns, ridge shrinkage and scaled dual feedback for four full ADMM iterations.',[[1.5,-1,-.5],[-1,3,-2],[-.5,-2,2.5]],dict(type='quadratic',Q=[[[2,1],[1,3]],[[1,-.5],[-.5,2]],[[3,.5],[.5,1]]],b=[[-3,1],[1,-2],[-1,-4]]),dict(type='ridge',coefficient=.75),.5,2),
        case('empty_node_l1_path','Exercise a no-data middle stratum, propagation across unequal edges, positive and negative soft-threshold branches, zero coordinates and dual feedback for four full iterations.',[[1,-1,0],[-1,3,-2],[0,-2,2]],dict(type='quadratic',Q=[[[2,0],[0,1]],[[0,0],[0,0]],[[1,0],[0,3]]],b=[[-4,1],[0,0],[2,-3]]),dict(type='l1',coefficient=.2),1.,2),
        case('poisson_ridge_graph','Exercise strictly positive nonlinear Poisson proximal minimizers with unequal sample counts, a coupled three-node graph, ridge shrinkage and dual feedback for four full iterations.',[[2,-1.5,-.5],[-1.5,2.5,-1],[-.5,-1,1.5]],dict(type='poisson',counts=[2,1,3],sums=[4,3,2]),dict(type='ridge',coefficient=.5),2.,1),
    ]
    derivations=[
        'Use Appendix A p.37 general quadratic formula: theta_k=(I+lambda*Q_k)^(-1)(theta_hat_old_k-u_old_k-lambda*b_k). Q matrices are symmetric positive definite. Appendix A p.36 gives theta_tilde=(theta_hat_old-u_tilde_old)/(1+lambda*0.75). For each of 2 columns solve (L+4I)theta_hat=2*(theta+u_old+theta_tilde+u_tilde_old); update both duals by Algorithm 4.1. Repeat four times from zero using exact rational arithmetic.',
        'Use the general quadratic proximal formula, with Q_2=0 and b_2=0 giving identity loss proximal at the no-data node. Apply elementwise soft-threshold to theta_hat_old-u_tilde_old at threshold 0.2. For each column solve (L+2I)theta_hat=theta+u_old+theta_tilde+u_tilde_old; update each scaled dual by its own proximal-minus-consensus residual. Repeat four times using exact rational arithmetic; the node with no data is updated by graph coupling.',
        'For each node v=theta_hat_old-u_old, Appendix A p.37 gives theta=(v-lambda*N+sqrt((v-lambda*N)^2+4*lambda*S))/2. All N and S are positive; for example underlying records may be [1,3], [3], and [0,1,1]. Ridge prox divides theta_hat_old-u_tilde_old by 2. Solve (L+I)theta_hat=(theta+u_old+theta_tilde+u_tilde_old)/2; update both scaled duals. Repeat four times in Decimal precision 70. Independently solve each Poisson proximal first-order equation N-S/theta+(theta-v)/lambda=0 by bisection and the graph system with NumPy.'
    ]
    errors=[]
    for c,derivation in zip(cases,derivations):
        with localcontext() as ctx:
            ctx.prec=70
            states=primary(c)
        errors.append(crosscheck(c,states))
        c['derivation']=derivation+' All five states at iterations 1, 2 and 4 are recorded; iteration 4 is the final fixed-budget iterate, not a converged optimum. Independent floating-point KKT checks agree within 2e-13 absolute/relative tolerance. See derive_contract.py for complete independent arithmetic.'
        c['expected']=[dict(step=s,name=name,value=[[float(x) for x in row] for row in states[s-1][name]]) for s in [1,2,4] for name in ['theta','theta_tilde','theta_hat','u','u_tilde']]
    contract=dict(schema_version='optirepro.paper_algorithm_contract.v1',paper=dict(paper_id='1904.12017',title='A Distributed Method for Fitting Laplacian Regularized Stratified Models',sha256=hashlib.sha256(PAPER.read_bytes()).hexdigest()),algorithm=dict(name='Algorithm 4.1: Distributed ADMM for Laplacian regularized stratified models',citations=['PDF p.16, Algorithm 4.1, steps 1-4 and zero initialization','PDF p.16, Eq. (5), regularized Laplacian systems','PDF p.15, Eq. (4) and proximal splitting','PDF p.36, Appendix A: proximal definition, sum of squares, l1 norm','PDF p.37, Appendix A: general Quadratic formula and Poisson negative log likelihood','PDF p.7, graph Laplacian definition'],core_mechanisms=MECHANISMS,assumptions=[
        'All tests are synthetic paper-grounded finite convex problems; graph Laplacians are supplied directly. L is K by K, symmetric positive semidefinite, with zero row sums and nonpositive off-diagonal entries; do not rescale L.',
        'Arrays use node-major K by n layout; rows correspond to the given L order. Apply Eq. (5) independently to each of n columns. No Kronecker flattening convention is needed.',
        'A quadratic loss input means ell_k(x)=0.5*x^T*Q[k]*x+b[k]^T*x, with constants omitted; Q[k] is n by n and b[k] has n entries. Do not negate b or interpret it as regression targets. The zero Q,b stratum has no local loss.',
        'Poisson counts[k] is the number N_k of nonnegative integer observations, sums[k] is their sum S_k, and ell_k(x)=N_k*x-S_k*log(x) for scalar x>0. These are sufficient statistics of the explicitly feasible observations in this contract.',
        'The same local regularizer is used at every node on all n coordinates. ridge means r(x)=coefficient*||x||_2^2/2. l1 means r(x)=coefficient*||x||_1. No unpenalized intercept, normalization by sample count, or extra constraints are added.',
        'Use the positive lambda as the proximal scale in Algorithm 4.1, equivalently augmented-Lagrangian coefficient 1/(2*lambda); it is the reciprocal of an ADMM rho convention. Start theta, theta_tilde, theta_hat, u and u_tilde at zero and perform exactly four complete iterations. Disable optional penalty adaptation and early stopping.',
        'Algorithm 4.1 and Eq. (5) are authoritative: use newly computed theta and theta_tilde with old duals on the Eq. (5) RHS, then update each dual. The p.15 unsimplified consensus argmin has stale i superscripts; Eq. (5) resolves the update timing.',
        'Graph scaling follows the explicit Eq. (5) matrix L+2/lambda*I. The p.7 double-sum Eq. (2) and its following half-quadratic expression have a factor-of-two inconsistency; this contract tests Algorithm 4.1 using its supplied L and does not infer L from Eq. (2).',
        'Quadratic proximal computations follow the first general quadratic formula on p.37. Its subsequent least-squares example has a sign inconsistency; that example is not used. The general formula also follows directly from the p.36 proximal minimization definition.',
        'Observe each requested state at the end of the numbered full iteration. The final requested step is a fixed-budget process result, not a claim of asymptotic convergence. Exact or sufficiently accurate proximal and linear-system solves are allowed; CG implementation details are not tested.'
    ]),cases=cases)
    spec=importlib.util.spec_from_file_location('paper_contract_schema_only',SCHEMA)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    mod.validate_contract(contract,paper_sha256=contract['paper']['sha256'])
    (HERE/'contract.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(dict(validation='passed',crosscheck_max_abs_error=errors,canonical_contract_digest=mod.contract_digest(contract),paper_sha256=contract['paper']['sha256']),indent=2))

if __name__=='__main__': build()
