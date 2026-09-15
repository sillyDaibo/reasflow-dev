from pathlib import Path
import json
P=Path('/Users/zanehuang/work/OptiRepro/reports/judge-hardening-cpu30-20260915/paper_reviews')
a=json.loads((P/'independent_arithmetic_rsa_dream.json').read_text())
common=[
 '唯一算法依据为指定原始 paper.pdf；只额外读取冻结 contract.json、原推导脚本和契约 schema。未读取被测实现、适配器、生成工作区、先前运行结果或先前审核报告。原推导脚本仅阅读，未导入或执行；复算独立编写。',
 '已核对原始 PDF 字节 SHA256 与契约绑定；contract_digest 使用 repo_judge/src/judge/paper_contract.py 的 contract_digest 计算，包含隐藏期望和推导。',
 '批准仅表示给定输入、明确约定和有限步观察的数学有效性；不能推断实现普遍正确、任意输入正确或理论收敛/复杂度结论已验证。',
 'atol=1e-9、rtol=1e-7 足以容纳本次 65 位 Decimal 复算与 JSON 浮点的舍入差。该精度要求适合双精度计算；未验证低精度实现的累计舍入，近零观察尤其不能只按相对误差判断。'
]
rsa={
 'schema_version':'optirepro.paper_review.v1','contract_digest':a['1811.03761']['contract_digest'],'reviewer_id':'paper_review_rsa_dream','basis':'original_paper_only','decision':'approved',
 'summary':'三例均与原论文 RSA 同步模型聚合及范数次梯度一致。独立 65 位 Decimal 复算 158 个数值叶全部在容差内，最大绝对差约 2.11e-16；不存在影响这些输入的多值次梯度歧义。',
 'cases':[
 {'case_id':'rsa_l1_sign_crossing_byzantine','decision':'approved','reason':'Eqs.(7)-(8) 使用旧本地/主节点状态，主节点求和而非平均；异质二次梯度、活跃非零符号、首步之后符号反转和 Byzantine 有界符号项均被实际激活。66 个数值叶独立重算一致。第一步 master=(0.875,-0.625)，最终=(0.5828125,-0.5984375)。输入未触及 sign(0) 的多值定义。','citations':['1811.03761 original PDF p.3, Eqs.(5)-(8) and definition of sign','1811.03761 original PDF p.4, Algorithm 2']},
 {'case_id':'rsa_l2_vector_normalization','decision':'approved','reason':'Proposition 1 对非零欧氏向量唯一给出 v/||v||2；初始 (3,4)、(-4,3)、(-6,8) 得单位范数方向，第二步重新依改变后的完整向量计算。46 个数值叶一致，最终 master=(0.7716441285803302,-0.6358993493044744)。能区分逐元素符号、平方范数梯度与聚合平均；不能宣称排除所有单位范数 clipping 变体。','citations':['1811.03761 original PDF p.4, Eqs.(9)-(11), Proposition 1 and Algorithm 2']},
 {'case_id':'rsa_linf_unique_maximum','decision':'approved','reason':'p=infinity 的对偶范数为 l1，唯一最大绝对坐标使次梯度为该坐标的带符号基向量；两个更新步均无并列最大。46 个数值叶一致，最终 master=(1,-0.58)。每个向量至少有一项零次梯度，可区分逐元素 sign。','citations':['1811.03761 original PDF p.4, Eqs.(9)-(11) and Proposition 1','1811.03761 original PDF p.5, Remark 2 explicitly discusses the infinity-norm variant']}
 ],
 'scope_notes':common+[
 '视觉检查 PDF p.3 的 Eqs.(5)-(8)，p.4 的 Eqs.(9)-(11)、Proposition 1 和 Algorithm 2；阅读 p.5 的 Assumption 3、Theorems 1-3 和 Remark 2。',
 '独立复算使用 Decimal 标量更新与 65 位平方根；所有梯度均从输入二次中心算出，未使用期望值作为下一步状态。L1/Linfinity 无零差或并列；L2 无零向量。',
 '各目标 Hessian=I，满足强凸和 Lipschitz 梯度条件；确定性 oracle 是零方差合法特例。仅测试两名正常节点、一名 Byzantine 节点、二维短轨迹，不验证随机噪声或规模效应。',
 'lambda=0.5 和给定短步长用于算法方程；不据此声称满足 Theorem 1 的共识阈值、Theorems 2-3 的调参或长期抗攻击保证。',
 '主节点使用收到的模型消息与 f0 梯度，不除以总节点数。正常节点梯度在各自旧状态上评估；不同初始状态是 Algorithm 2 明确接受的输入。',
 'L1 攻击符号和观察值验证了这些消息上的有界作用，未验证所有攻击方向或概率模型。L2 所有输入差向量长度大于 1，因此该例无法排除与单位范数归一化在此区域相同的 clip(v,max_norm=1)。Linfinity 最大坐标未切换，未覆盖并列最大或跨步重选坐标的所有情形。',
 '原文未指定软件 API、通用停止条件或独立返回结构；最终 master 是合理的显式观察约定，不能把接口差异直接等同于算法错误。'
 ]}
dream={
 'schema_version':'optirepro.paper_review.v1','contract_digest':a['2212.02387']['contract_digest'],'reviewer_id':'paper_review_rsa_dream','basis':'original_paper_only','decision':'approved',
 'summary':'两例遵循原论文 Algorithm 2 的初始化、投影后通信、条件递归估计、刷新、梯度跟踪与历史输出。用谱分解通信及二次 Hessian 差分独立重算 166 个数值叶全部一致，最大绝对差约 3.34e-16。Algorithm 1 明确返回 a^(K)，多列一次循环不改变该返回值。',
 'cases':[
 {'case_id':'dream_projected_refresh_and_skips','decision':'approved','reason':'三步实际触发 y 上界投影、q=1/2 的二倍样本差、不同节点跳过、全梯度刷新及 K 与 K_prime 不同的 tracker 混合。97 个数值叶一致；初始 g=((3.25,2.5),(2.25,-1.5))，首步 z=((0.6277734375,0.42484375),(0.6847265625,0.11265625))。历史索引 4 返回时间 2 节点 0 的 x=0.30997106018066406，正确排除最终时间 3。','citations':['2212.02387 original PDF p.3, Algorithm 1 lines 1-6','2212.02387 original PDF p.5, Definition 2.4','2212.02387 original PDF p.6, Algorithm 2 lines 3-8, 10-23 and 25','2212.02387 original PDF p.13, Lemma A.4']},
 {'case_id':'dream_two_sample_recursive_differences','decision':'approved','reason':'两个未投影更新使用非同质样本 Hessian；同一抽样索引对新旧状态求差，b=2、q=1/2 给出作用于差之和的系数 1。第二步节点 0 的估计器保持不变但继续参与状态与 tracker 通信；69 个数值叶一致。历史索引 3 返回时间 1 节点 1 的 x=-0.474072021484375。此例不独立测试刷新或活跃投影，联合覆盖由第一例提供。','citations':['2212.02387 original PDF p.1, Eq.(3)','2212.02387 original PDF p.3, Algorithm 1','2212.02387 original PDF p.6, Algorithm 2 lines 18-20, 23 and 25']}
 ],
 'scope_notes':common+[
 '视觉检查 PDF p.3 的 Algorithm 1 与 p.6 的 Algorithm 2 完整页；阅读 p.1 有限和归一化、p.3-4 Assumptions 2.1-2.5、p.5 Definition 2.4/Proposition 2.3、p.7 定理参数、p.8 独立调 q 的实验说明、p.13 Lemma A.4。',
 '独立算术不复用原脚本的矩阵递推或两次梯度求差：FastMix 用均值/分歧特征子空间闭式乘子 r0=1,r1=27/40,r2=101/400,r3=-749/8000；递归梯度先求抽样 Hessian 之和，再乘状态差；全梯度先平均系数，再微分。计算精度为 65 位 Decimal。',
 'FastMix Algorithm 1 line 3 写 k=0,...,K，line 6 明确输出 a^(K)。严格执行可多算并丢弃 a^(K+1)，被测返回值仍为唯一的 a^(K)，Proposition 2.3 也以 a^(K) 为结论。这里批准返回态算术，不审计实际多余通信次数。返回 a^(K+1) 是另一改写约定，不能把它悄悄当成当前输入中的 a^(K)。',
 'q 未列于 Algorithm 2 Input 行，但 lines 18/20 明确使用 q，p.8 明确单独调 q。契约显式 q=0.5，且 p=0.25、gamma∈(0,1]、eta>0 都是算法输入允许值；不声称满足 Theorem 3.1 的充分调参。',
 'W=[[0.9,0.1],[0.1,0.9]] 对称、不可约、双随机和半正定，特征值为 1、0.8。全梯度是每节点样本均值，不另除 m；最终网络均值观察应除以两节点。',
 '所有局部 y 曲率为 -2 或 -3，光滑有限和目标的 primal 有下界，区间或全实线 Y 均闭凸；convex-in-x 特例属于论文容许的问题类，但不能证明一般非凸曲率行为。不同样本 Hessian 的全域随机梯度方差可随 x/y 增长；论文 p.3 明确仅在线情况要求有界方差，因此不影响这些离线例子的合法性。',
 '固定 Bernoulli、样本和输出索引都是正概率事件；验证条件轨迹，不验证 RNG、独立性或均匀抽样的经验分布。零门控节点提供的样本不会影响估计器。',
 '投影先于通信；本例 FastMix K=1 在节点间等效正权混合，保持区间可行，未验证任意 K/网络的投影可行性。历史候选值含重复初值，均匀抽样按时间和节点位置计数，不能对数值去重。',
 '测试只有两个节点、每个 x/y 一维和两至三步；不验证在线噪声、长期收敛、SFO/通信复杂度、线性加速或缺失分支。'
 ]}
for id,obj in [('1811.03761',rsa),('2212.02387',dream)]:
 (P/f'{id}.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
 lines=[f'# {id} 原论文独立审核', '',f'结论：**{obj["decision"]}**。{obj["summary"]}', '',f'- 审核者：`{obj["reviewer_id"]}`',f'- 契约摘要：`{obj["contract_digest"]}`',f'- 原 PDF SHA256：`{a[id]["paper_sha256"]}`','', '## 逐例判断','']
 for c in obj['cases']:
  e=a[id]['cases'][c['case_id']]
  lines += [f'### {c["case_id"]}: {c["decision"]}', '',c['reason'],'', '依据：'+'；'.join(c['citations'])+'。','',f'独立复算 {e["numeric_leaves"]} 个数值叶；最大绝对差 `{e["maximum_absolute_error"]}`；不匹配数 `{len(e["mismatches"])}`。','']
 lines += ['## 审核范围与限制','']+[f'{j+1}. {s}' for j,s in enumerate(obj['scope_notes'])]
 lines += ['', '## 可复查证据', '', '`recompute_rsa_dream.py` 为此次独立算术脚本，`independent_arithmetic_rsa_dream.json` 为完整计数及误差报告。审核未修改原始 PDF、契约或原推导脚本。','']
 (P/f'{id}.md').write_text('\n'.join(lines))
print('Written independent reviews: 1811.03761 approved; 2212.02387 approved')
