"""Paper-only reference arithmetic. Reads no implementation or other repo files."""
from decimal import Decimal as D, localcontext
import json
from pathlib import Path

MECH = ['ordered_without_replacement_inner_gradients', 'post_epoch_consensus', 'one_prox_per_epoch']

def numeric(x):
    return [numeric(v) for v in x] if isinstance(x, list) else float(x)

def make_case(cid, start, lam):
    x = [D(v) for v in start]
    a = [[D(1), D(-2)], [D(2), D(-1)]]
    gamma, strength = D('.05'), D(lam)
    mixing = [[[D('.75'),D('.25')],[D('.25'),D('.75')]],
              [[D('.625'),D('.375')],[D('.375'),D('.625')]],
              [[D('.5625'),D('.4375')],[D('.4375'),D('.5625')]]]
    perms = [[0,1],[1,0],[0,1]]
    entries = []
    def emit(t,n,v): entries.append(dict(step=t,name=n,value=numeric(v)))
    for t in range(3):
        inner = [x[:]]
        grads = []
        for s in perms[t]:
            g = [-a[j][s]/(1+(a[j][s]*x[j]).exp()) for j in range(2)]
            grads.append(g)
            x = [x[j]-gamma*g[j] for j in range(2)]
            inner.append(x[:])
        v = [sum(mixing[t][j][k]*x[k] for k in range(2)) for j in range(2)]
        x = [(D(1) if z>0 else D(-1))*max(abs(z)-gamma*strength,D(0)) for z in v]
        emit(t+1,'inner_x',inner);emit(t+1,'inner_gradient',grads)
        emit(t+1,'consensus_v',v);emit(t+1,'x_next',x)
    return dict(id=cid,purpose='Three DPG-RR epochs with changing sample order, nontrivial mixing, and L1 shrinkage.',covers=MECH,
      inputs=dict(dimension=1,agents=2,samples_per_agent=2,x_initial=[float(z) for z in start],
          signed_features=[[1,-2],[2,-1]],sample_objective='f[j,i](x)=log(1+exp(-signed_features[j][i]*x)); labels absorbed into signed_features; gradient=-a/(1+exp(a*x))',
          regularizer='phi(x)=regularizer_strength*abs(x)',network='Two connected agents; same constant doubly stochastic A=[[.75,.25],[.25,.75]].',
          mixing_matrices=numeric(mixing),permutations=perms,
          randomness='Condition on the listed shared zero-based sample permutations; no replacement within an epoch; no other random draws.'),
      parameters=dict(gamma=.05,regularizer_strength=float(strength),epochs=3,
          consensus_convention='Use explicitly supplied Lambda[t] in Eq.(8), equal to A^(t+1). Eq.(9) writes t+1 factors although nearby prose says t communications; this contract tests the supplied Eq.(8) mapping, not the ambiguous schedule.',
          observation_timing='step=t+1 after epoch t. inner_x rows are before gradients, after first, after second; columns agent. inner_gradient rows are evaluated before each update. consensus_v is before prox; x_next is after the single prox.'),
      atol=1e-11,rtol=1e-11,expected=entries,
      derivation='Substitute logistic gradients into Eq.(7) in supplied permutation order, multiply by the explicitly supplied Eq.(8) Lambda, then Eq.(10) soft threshold sign(v)*max(abs(v)-gamma*strength,0), once per epoch. All exp and arithmetic use 70 decimal digits before float serialization. Negative, zero, and positive shrinkage are covered across cases. No convergence rate or off-by-one communication scheduler claim.')

def build():
    with localcontext() as c:
        c.prec=70
        cases=[make_case('logistic_mixed_sign',['1.2','-.8'],'.4'),make_case('logistic_threshold',['.4','-.1'],'.8')]
    return dict(schema_version='optirepro.paper_algorithm_contract.v1',
      paper=dict(paper_id='2111.03820',title='Distributed stochastic proximal algorithm with random reshuffling for non-smooth finite-sum optimization',sha256='3ce09777be924669f8649b920477e4df968f8adce511e8b980d6883e1604b761'),
      algorithm=dict(name='DPG-RR, Algorithm 1',citations=['PDF p.4 Algorithm 1 and Eqs.(7)-(10)','PDF p.3 Eq.(5), Assumption III.1; p.4 logistic Example 1 and Assumption III.2'],core_mechanisms=MECH,
       assumptions=['Convex logistic sample losses with bounded gradients and Lipschitz gradients; convex L1 regularizer with bounded subgradients.','Fixed connected undirected two-node network with positive diagonal and doubly stochastic weights.','Explicit Lambda mappings avoid the paper communication-count indexing inconsistency; only numerical Eq.(8) is tested.']),cases=cases)

if __name__=='__main__':
    Path(__file__).with_name('contract.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
