"""Paper-only DREAM arithmetic; standard library only, no implementation imports.
Source: Algorithm 1 (PDF p.3), Algorithm 2 (PDF p.6), arXiv:2212.02387v4.
All arithmetic is exact Fraction arithmetic until JSON serialization.
"""
from fractions import Fraction as F
from pathlib import Path
import hashlib, json
OUT = Path(__file__).resolve().parent
PAPER = Path('/Users/zanehuang/work/OptiRepro/datasets/benchmarks/cpu30_v1/input/2212.02387/paper.pdf')
def frac(x): return F(str(x))
def mat(x): return [[frac(v) for v in row] for row in x]
def add(a,b): return [[x+y for x,y in zip(r,s)] for r,s in zip(a,b)]
def sub(a,b): return [[x-y for x,y in zip(r,s)] for r,s in zip(a,b)]
def mul(a,s): return [[x*s for x in r] for r in a]
def mix(a,k):
    # W has eigenvalues 1, 4/5; eta_a=1/(1+3/5)=5/8.
    last=[r[:] for r in a]
    for _ in range(k):
        wa=[[F(9,10)*a[i][j]+F(1,10)*a[1-i][j] for j in range(len(a[0]))] for i in range(2)]
        nxt=sub(mul(wa,F(13,8)),mul(last,F(5,8)))
        last,a=a,nxt
    return a

def grad(coef,z):
    a,c,d,e,h=map(frac,coef); x,y=z
    return [a*x+c*y+e,c*x-d*y+h]
def avg_grads(coefs,z,ids):
    gs=[grad(coefs[j],z) for j in ids]
    return [sum(g[k] for g in gs)/len(gs) for k in range(2)]
def num(a):
    if isinstance(a,list): return [num(x) for x in a]
    return float(a)
def exact(a):
    if isinstance(a,list): return '['+', '.join(exact(x) for x in a)+']'
    return str(a)
MECH=['two_timescale_gda','projection_before_consensus','fastmix_acceleration','recursive_sample_difference','bernoulli_agent_gating','full_gradient_refresh','recursive_gradient_tracking','branch_specific_tracker_mixing','uniform_historical_output']

def run_case(case):
    p=case['parameters']; inp=case['inputs']; coefs=inp['component_coefficients']
    z=[list(map(frac,inp['initial_z'])) for _ in range(2)]
    g=[avg_grads(coefs[i],z[i],list(range(len(coefs[i])))) for i in range(2)]
    s=mix(g,p['K0']); expected=[]; traces=[]; history=[]
    def rec(t,name,val):
        expected.append({'step':t,'name':name,'value':num(val)})
        traces.append(f'- step {t}, `{name}` = `{exact(val)}`')
    rec(0,'z',z); rec(0,'g',g); rec(0,'s',s)
    for t,zeta in enumerate(inp['refresh_draws']):
        history.append([r[0] for r in z])
        raw=[[z[i][0]-frac(p['gamma'])*frac(p['eta'])*s[i][0], z[i][1]+frac(p['eta'])*s[i][1]] for i in range(2)]
        projected=[r[:] for r in raw]
        if inp['y_interval'] is not None:
            lo,hi=map(frac,inp['y_interval'])
            for r in projected: r[1]=min(hi,max(lo,r[1]))
        zn=mix(projected,p['K'])
        if zeta:
            gn=[avg_grads(coefs[i],zn[i],list(range(len(coefs[i])))) for i in range(2)]
        else:
            gn=[r[:] for r in g]
            for i in range(2):
                # Identical sample ids must be used at old and new states.
                ids=inp['sample_indices'][t][i]
                for j in ids:
                    old,new=grad(coefs[i][j],z[i]),grad(coefs[i][j],zn[i])
                    for d in range(2): gn[i][d]+=frac(inp['active_draws'][t][i])/(frac(p['b'])*frac(p['q']))*(new[d]-old[d])
        tracker_input=add(s,sub(gn,g)); sn=mix(tracker_input,p['K_prime'] if zeta else p['K'])
        rec(t+1,'pre_projection',raw); rec(t+1,'projected',projected)
        rec(t+1,'z',zn); rec(t+1,'g',gn); rec(t+1,'tracker_input',tracker_input); rec(t+1,'s',sn)
        rec(t+1,'mean_z',[sum(zn[i][d] for i in range(2))/2 for d in range(2)])
        assert all(sum(sn[i][d] for i in range(2))==sum(gn[i][d] for i in range(2)) for d in range(2))
        z,g,s=zn,gn,sn
    flat=[x for row in history for x in row]
    rec(len(inp['refresh_draws']),'output_candidates',flat)
    rec(len(inp['refresh_draws']),'x_out',flat[inp['output_draw_index']])
    case['expected']=expected; case['atol']=1e-9; case['rtol']=1e-7
    return traces

case1={
'id':'dream_projected_refresh_and_skips','purpose':'Three complete DREAM iterations with active projection, heterogeneous nodes, recursive updates, skipped node and full refresh; distinguish K from K_prime and historical output from last iterate.',
'covers':MECH,
'inputs':{'objective':'F_ij(x,y)=a*x^2/2+c*x*y-d*y^2/2+e*x+h*y; each coefficient tuple is [a,c,d,e,h]. Offline uniform finite sum per agent.','component_coefficients':[[[1,1,2,1,2],[3,1,2,1,2]],[[2,1,2,-1,-2],[4,1,2,-1,-2]]], 'initial_z':[1,0.25],'y_interval':[-0.5,0.5],'W':[[0.9,0.1],[0.1,0.9]],'refresh_draws':[0,1,0],'active_draws':[[1,0],None,[0,1]],'sample_indices':[[[0],[1]],None,[[1],[1]]],'output_draw_index':4},
'parameters':{'eta':0.25,'gamma':0.5,'p':0.25,'q':0.5,'b':1,'b_prime':2,'K0':1,'K':1,'K_prime':2,'T':3,'fastmix_return':'a^(K), exactly K effective recurrences','index_convention':'agent and sample indices zero based; output list is time-major x_0,...,x_(T-1)'},
'derivation':'Condition on the explicit positive-probability Bernoulli and sample draws, not a seed or RNG implementation. W eigenvalues are 1 and 4/5, so eta_a=5/8. On the disagreement subspace FastMix has multipliers r0=1, r1=27/40, r2=101/400, r3=-749/8000. Initialize both z rows to (1,1/4). Exact local means give g0=[(13/4,5/2),(9/4,-3/2)], and s0=[(247/80,37/20),(193/80,-17/20)]. At t=0, the descent/ascent inputs are [(393/640,57/80),(447/640,3/80)]; project y to (1/2,3/80), then mix. Thus z1=[(80355/128000,5438/12800),(87645/128000,1442/12800)]. Update only agent 0 with twice the same-sample gradient difference, keep agent 1 g unchanged, and mix s0+g1-g0 using K=1. At t=1 recompute exact local full gradients at z2 and use K_prime=2 only for the tracker, retaining K=1 for z. At t=2 keep agent 0 estimator, update agent 1 from sample 1 with factor 2, then K=1 tracker mixing. All states below follow these recurrences using exact rationals. Output draw index 4 selects agent 0 at t=2 from six equally likely historical entries, excluding z3. The specified eta/gamma/K exercise Algorithm 2 and do not claim Theorem 3.1 parameter guarantees.'}
case2={
'id':'dream_two_sample_recursive_differences','purpose':'Two full unprojected iterations with nonidentical sampled Hessians and mini-batch size 2, testing paired sample differences, the 1/(bq) normalization, skipped estimator, and two-round accelerated mixing.',
'covers':['two_timescale_gda','fastmix_acceleration','recursive_sample_difference','bernoulli_agent_gating','recursive_gradient_tracking','uniform_historical_output'],
'inputs':{'objective':'F_ij(x,y)=a*x^2/2+c*x*y-d*y^2/2+e*x+h*y; tuple [a,c,d,e,h]. Offline uniform finite sum per agent.','component_coefficients':[[[1,1,2,1,2],[3,2,2,1,2],[2,-1,2,1,2]],[[2,-1,3,-1,-2],[4,1,3,-1,-2],[3,2,3,-1,-2]]], 'initial_z':[-0.5,0.75],'y_interval':None,'W':[[0.9,0.1],[0.1,0.9]],'refresh_draws':[0,0],'active_draws':[[1,1],[0,1]],'sample_indices':[[[0,1],[1,2]],[[2,0],[0,2]]],'output_draw_index':3},
'parameters':{'eta':0.125,'gamma':0.25,'p':0.25,'q':0.5,'b':2,'b_prime':3,'K0':2,'K':2,'K_prime':3,'T':2,'fastmix_return':'a^(K), exactly K effective recurrences','index_convention':'agent and sample indices zero based; output list is time-major x_0,...,x_(T-1)'},
'derivation':'Use the same exact FastMix multipliers as case 1; here K0=K=2 means disagreement multiplier 101/400. The six component Hessians are nonidentical. The initial exact local gradients are g0=[(1/2,1/6),(-2,-55/12)]; s0=FastMix(g0,2). At each update form x-eta*gamma*u and y+eta*v simultaneously from the old state, then FastMix them. No y constraint means projection is the identity. At t=0 both agents update from two explicit, distinct sample indices. Because b=2 and q=1/2, the multiplier on the SUM of paired gradient differences is exactly 1; replacing the sum by a mean would be wrong. At t=1 agent 0 has omega=0, so g2(0)=g1(0) despite changing z; agent 1 again uses two paired gradient differences. Mix s+g_new-g_old for each tracker, preserving its network mean equal to mean(g). The selected uniform historical index 3 returns agent 1 at t=1, not either final x2. These are prescribed finite-step algorithm inputs, not theorem-calibrated convergence parameters.'}
traces=[run_case(c) for c in [case1,case2]]
contract={'schema_version':'optirepro.paper_algorithm_contract.v1','paper':{'paper_id':'2212.02387','title':'An Efficient Stochastic Algorithm for Decentralized Nonconvex-Strongly-Concave Minimax Optimization','sha256':hashlib.sha256(PAPER.read_bytes()).hexdigest()},'algorithm':{'name':'DREAM (Decentralized Recursive-gradient dEscent Ascent Method)','citations':['PDF p.3, Algorithm 1: accelerated FastMix recurrence and output a^(K).','PDF pp.3-4, Assumptions 2.1-2.5: lower bounded primal, average smoothness, local strong concavity, oracle conditions, symmetric PSD doubly stochastic W.','PDF p.5, Definitions 2.4-2.5: rowwise projection onto the closed convex Y.','PDF p.6, Algorithm 2 lines 3-8: consensus initialization and mixed initial full-gradient tracker.','PDF p.6, Algorithm 2 lines 10-23: state update, Bernoulli refresh, omega/(bq) paired stochastic gradient differences and branch-specific tracker FastMix.','PDF p.6, Algorithm 2 line 25: uniform output over all local x at times 0 through T-1.','PDF p.7, Equations (5), (7), (8): sufficient theorem parameters, distinguished here from freely supplied Algorithm 2 inputs.','PDF p.13, Lemma A.4: mean(s_t)=mean(g_t).'],'core_mechanisms':MECH,'assumptions':['All tests are offline finite-sum problems; b_prime=n, uniform components. All local mean objectives are smooth and strongly concave in y; primal is lower bounded.','Two agents, one x coordinate and one y coordinate, row-major state [x,y]. W has eigenvalues 1 and 0.8 and meets symmetry, irreducibility, double stochasticity and PSD assumptions.','Randomness is conditioned on explicitly supplied realizations; output_draw_index is an explicit uniform-index realization, not an assertion about a particular RNG seed.','FastMix indexing ambiguity: PDF Algorithm 1 loops k=0,...,K but explicitly returns a^(K). Contract follows the returned-state expression, hence K effective recurrences; any discarded extra a^(K+1) does not affect output. A differing loop-count convention should be reported as ambiguous rather than silently counted as a mathematical failure.','Algorithm 2 omits q from its input list but uses it at lines 18 and 20; the experiments on p.8 tune q independently, and this contract explicitly supplies q in (0,1].','The short traces test equations, not Theorem 3.1 convergence, optimal complexity, online stochastic variance, or linear speed-up. eta/gamma/K are algorithm-valid but are not calibrated to the theorem.','The paper gives random historical output; final x_T and network mean(x_T) are not interchangeable with it.']},'cases':[case1,case2]}
(OUT/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
review='''# DREAM 论文独立推导\n\n唯一算法来源为原论文 PDF（arXiv:2212.02387v4, 2024-05-14）。没有读取被测实现、既有测试、runs、官方代码或其他实验答案。PDF 的第 3、6、7 页已渲染并视觉核对。页码均指 PDF 物理页码。\n\n## 核心算法与依据\n\n- 第 3 页 Algorithm 1：a^(-1)=a^(0)，eta_a=1/(1+sqrt(1-lambda_2(W)^2))；a^(k+1)=(1+eta_a)Wa^(k)-eta_a a^(k-1)，返回 a^(K)。\n- 第 6 页 Algorithm 2：z0=1*zbar0；g0 为本地全梯度（离线 b'=n），s0=FastMix(g0,K0)。\n- 每步同时形成 x-γηu 与 Π(y+ηv)，分别 FastMix K 轮；特别注意先做逐节点投影，再通信。\n- 刷新 ζ=1 时，在新 z 上重算本地全梯度；否则 g_new=g_old+ω/(bq) sum_j[grad F_j(z_new)-grad F_j(z_old)]。同一 j 必须用于差的两项。ω=0 的节点保留 g，但仍参与参数与 tracker 通信。\n- s_new=FastMix(s_old+g_new-g_old,K' if ζ else K)。刷新只改变 tracker 的通信预算，x/y 仍使用 K。第 13 页 Lemma A.4 给出 mean(s)=mean(g)。\n- 输出从时间 0,...,T-1 的全部 m 个本地 x 中均匀选择；不能直接取 x_T 或网络末态均值。\n- 第 3-4 页 Assumptions 2.1-2.5，第 5 页 Definitions 2.4-2.5 给出条件；第 7 页 (5),(7),(8) 是收敛定理的充分参数方案，不是唯一允许的 Algorithm 2 输入。\n\n## 明确的歧义和限制\n\n1. Algorithm 1 的循环写作 k=0,...,K，但输出 a^(K)。以下遵循明确输出，仅需 K 次有效递推；多算而丢弃 a^(K+1) 不改变输出。若实现以循环次数而非输出下标解释 K，应单列论文歧义，不应隐藏。\n2. Algorithm 2 使用 q 却未在 Input 行列出；第 8 页数值实验明确单独调 q。这里给定 q。\n3. 第 5 页概述的行号与第 6 页实际伪代码行号不完全一致，以可视化核对的 Algorithm 2 为准。\n4. 两个案例验证有限步代数、随机分支条件和历史抽样语义；不验证在线期望方差、随机数分布、收敛速度、通信复杂度和线性加速结论。\n5. 测试目标为满足论文问题类别的光滑耦合二次鞍点；无需采用真实数据集和较大训练。所有均值局部目标的 y Hessian 为 -2 或 -3，x 二次项为正，故 primal 有下界。它们是该问题类的合法特例，但不验证非凸曲率行为。\n\n## 算术约定\n\n输入 W=[[9/10,1/10],[1/10,9/10]]，lambda2=4/5，所以 eta_a=5/8。把两节点状态写成均值加/减偏差，FastMix 保持均值，偏差乘 r_K；r0=1, r1=27/40, r2=101/400, r3=-749/8000。后者已出现负系数，说明一般不能以 W^K 替代。独立脚本只使用 Python 标准库 Fraction，从原始系数推导所有状态，最终才转成 JSON 浮点数。每步包含实际参数 z、估计器 g 和 tracker s，避免只测试辅助系数。\n'''
for case,trace in zip([case1,case2],traces):
    review+='\n## '+case['id']+'\n\n'+case['purpose']+'\n\n### 输入与参数\n\n```json\n'+json.dumps({'inputs':case['inputs'],'parameters':case['parameters']},ensure_ascii=False,indent=2)+'\n```\n\n### 独立推导\n\n'+case['derivation']+'\n\n### 精确中间状态与输出\n\n'+'\n'.join(trace)+'\n'
review+='\n## 冻结与复核\n\n`contract.json` 保存完整输入、条件随机抽样和数字预期；`derive_expected.py` 为独立算术来源。契约必须在接触被测代码之前冻结，不得根据实现的行为改写预期。数值容差 atol=1e-9, rtol=1e-7。\n'
(OUT/'PAPER_REVIEW.md').write_text(review)
for c in contract['cases']:
 print(c['id'])
 for e in c['expected']:
  if e['name'] in ['z','g','s','x_out']: print(e)
for name in ['contract.json','derive_expected.py','PAPER_REVIEW.md']:
 print(name,hashlib.sha256((OUT/name).read_bytes()).hexdigest())
