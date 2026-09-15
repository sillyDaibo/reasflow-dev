# DREAM 论文独立推导

唯一算法来源为原论文 PDF（arXiv:2212.02387v4, 2024-05-14）。没有读取被测实现、既有测试、runs、官方代码或其他实验答案。PDF 的第 3、6、7 页已渲染并视觉核对。页码均指 PDF 物理页码。

## 核心算法与依据

- 第 3 页 Algorithm 1：a^(-1)=a^(0)，eta_a=1/(1+sqrt(1-lambda_2(W)^2))；a^(k+1)=(1+eta_a)Wa^(k)-eta_a a^(k-1)，返回 a^(K)。
- 第 6 页 Algorithm 2：z0=1*zbar0；g0 为本地全梯度（离线 b'=n），s0=FastMix(g0,K0)。
- 每步同时形成 x-γηu 与 Π(y+ηv)，分别 FastMix K 轮；特别注意先做逐节点投影，再通信。
- 刷新 ζ=1 时，在新 z 上重算本地全梯度；否则 g_new=g_old+ω/(bq) sum_j[grad F_j(z_new)-grad F_j(z_old)]。同一 j 必须用于差的两项。ω=0 的节点保留 g，但仍参与参数与 tracker 通信。
- s_new=FastMix(s_old+g_new-g_old,K' if ζ else K)。刷新只改变 tracker 的通信预算，x/y 仍使用 K。第 13 页 Lemma A.4 给出 mean(s)=mean(g)。
- 输出从时间 0,...,T-1 的全部 m 个本地 x 中均匀选择；不能直接取 x_T 或网络末态均值。
- 第 3-4 页 Assumptions 2.1-2.5，第 5 页 Definitions 2.4-2.5 给出条件；第 7 页 (5),(7),(8) 是收敛定理的充分参数方案，不是唯一允许的 Algorithm 2 输入。

## 明确的歧义和限制

1. Algorithm 1 的循环写作 k=0,...,K，但输出 a^(K)。以下遵循明确输出，仅需 K 次有效递推；多算而丢弃 a^(K+1) 不改变输出。若实现以循环次数而非输出下标解释 K，应单列论文歧义，不应隐藏。
2. Algorithm 2 使用 q 却未在 Input 行列出；第 8 页数值实验明确单独调 q。这里给定 q。
3. 第 5 页概述的行号与第 6 页实际伪代码行号不完全一致，以可视化核对的 Algorithm 2 为准。
4. 两个案例验证有限步代数、随机分支条件和历史抽样语义；不验证在线期望方差、随机数分布、收敛速度、通信复杂度和线性加速结论。
5. 测试目标为满足论文问题类别的光滑耦合二次鞍点；无需采用真实数据集和较大训练。所有均值局部目标的 y Hessian 为 -2 或 -3，x 二次项为正，故 primal 有下界。它们是该问题类的合法特例，但不验证非凸曲率行为。

## 算术约定

输入 W=[[9/10,1/10],[1/10,9/10]]，lambda2=4/5，所以 eta_a=5/8。把两节点状态写成均值加/减偏差，FastMix 保持均值，偏差乘 r_K；r0=1, r1=27/40, r2=101/400, r3=-749/8000。后者已出现负系数，说明一般不能以 W^K 替代。独立脚本只使用 Python 标准库 Fraction，从原始系数推导所有状态，最终才转成 JSON 浮点数。每步包含实际参数 z、估计器 g 和 tracker s，避免只测试辅助系数。

## dream_projected_refresh_and_skips

Three complete DREAM iterations with active projection, heterogeneous nodes, recursive updates, skipped node and full refresh; distinguish K from K_prime and historical output from last iterate.

### 输入与参数

```json
{
  "inputs": {
    "objective": "F_ij(x,y)=a*x^2/2+c*x*y-d*y^2/2+e*x+h*y; each coefficient tuple is [a,c,d,e,h]. Offline uniform finite sum per agent.",
    "component_coefficients": [
      [
        [
          1,
          1,
          2,
          1,
          2
        ],
        [
          3,
          1,
          2,
          1,
          2
        ]
      ],
      [
        [
          2,
          1,
          2,
          -1,
          -2
        ],
        [
          4,
          1,
          2,
          -1,
          -2
        ]
      ]
    ],
    "initial_z": [
      1,
      0.25
    ],
    "y_interval": [
      -0.5,
      0.5
    ],
    "W": [
      [
        0.9,
        0.1
      ],
      [
        0.1,
        0.9
      ]
    ],
    "refresh_draws": [
      0,
      1,
      0
    ],
    "active_draws": [
      [
        1,
        0
      ],
      null,
      [
        0,
        1
      ]
    ],
    "sample_indices": [
      [
        [
          0
        ],
        [
          1
        ]
      ],
      null,
      [
        [
          1
        ],
        [
          1
        ]
      ]
    ],
    "output_draw_index": 4
  },
  "parameters": {
    "eta": 0.25,
    "gamma": 0.5,
    "p": 0.25,
    "q": 0.5,
    "b": 1,
    "b_prime": 2,
    "K0": 1,
    "K": 1,
    "K_prime": 2,
    "T": 3,
    "fastmix_return": "a^(K), exactly K effective recurrences",
    "index_convention": "agent and sample indices zero based; output list is time-major x_0,...,x_(T-1)"
  }
}
```

### 独立推导

Condition on the explicit positive-probability Bernoulli and sample draws, not a seed or RNG implementation. W eigenvalues are 1 and 4/5, so eta_a=5/8. On the disagreement subspace FastMix has multipliers r0=1, r1=27/40, r2=101/400, r3=-749/8000. Initialize both z rows to (1,1/4). Exact local means give g0=[(13/4,5/2),(9/4,-3/2)], and s0=[(247/80,37/20),(193/80,-17/20)]. At t=0, the descent/ascent inputs are [(393/640,57/80),(447/640,3/80)]; project y to (1/2,3/80), then mix. Thus z1=[(80355/128000,5438/12800),(87645/128000,1442/12800)]. Update only agent 0 with twice the same-sample gradient difference, keep agent 1 g unchanged, and mix s0+g1-g0 using K=1. At t=1 recompute exact local full gradients at z2 and use K_prime=2 only for the tracker, retaining K=1 for z. At t=2 keep agent 0 estimator, update agent 1 from sample 1 with factor 2, then K=1 tracker mixing. All states below follow these recurrences using exact rationals. Output draw index 4 selects agent 0 at t=2 from six equally likely historical entries, excluding z3. The specified eta/gamma/K exercise Algorithm 2 and do not claim Theorem 3.1 parameter guarantees.

### 精确中间状态与输出

- step 0, `z` = `[[1, 1/4], [1, 1/4]]`
- step 0, `g` = `[[13/4, 5/2], [9/4, -3/2]]`
- step 0, `s` = `[[247/80, 37/20], [193/80, -17/20]]`
- step 1, `pre_projection` = `[[393/640, 57/80], [447/640, 3/80]]`
- step 1, `projected` = `[[393/640, 1/2], [447/640, 3/80]]`
- step 1, `z` = `[[16071/25600, 2719/6400], [17529/25600, 721/6400]]`
- step 1, `g` = `[[36547/12800, 13519/12800], [9/4, -3/2]]`
- step 1, `tracker_input` = `[[34467/12800, 5199/12800], [193/80, -17/20]]`
- step 1, `s` = `[[2710729/1024000, 206893/1024000], [2517031/1024000, -661373/1024000]]`
- step 1, `mean_z` = `[21/32, 43/160]`
- step 2, `pre_projection` = `[[2431991/8192000, 1947053/4096000], [3092249/8192000, -199933/4096000]]`
- step 2, `projected` = `[[2431991/8192000, 1947053/4096000], [3092249/8192000, -199933/4096000]]`
- step 2, `z` = `[[101571317/327680000, 63926711/163840000], [119398283/327680000, 5958089/163840000]]`
- step 2, `g` = `[[82334507/40960000, 501224473/327680000], [42431027/327680000, -559794073/327680000]]`
- step 2, `tracker_input` = `[[73813267/40960000, 221343833/327680000], [110600947/327680000, -279913433/327680000]]`
- step 2, `s` = `[[328913257289/262144000000, 13599571933/131072000000], [231972409111/262144000000, -37027411933/131072000000]]`
- step 2, `mean_z` = `[69053/204800, 21839/102400]`
- step 3, `pre_projection` = `[[321143171511/2097152000000, 218165047133/524288000000], [532176602089/2097152000000, -17961527133/524288000000]]`
- step 3, `projected` = `[[321143171511/2097152000000, 218165047133/524288000000], [532176602089/2097152000000, -17961527133/524288000000]]`
- step 3, `z` = `[[14217444159197/83886080000000, 7191779152591/20971520000000], [19915346784803/83886080000000, 816361647409/20971520000000]]`
- step 3, `g` = `[[82334507/40960000, 501224473/327680000], [-2309773635947/2621440000000, -82734065050469/41943040000000]]`
- step 3, `tracker_input` = `[[328913257289/262144000000, 13599571933/131072000000], [-329497760837/2621440000000, -22929195525029/41943040000000]]`
- step 3, `s` = `[[216088411492749/209715200000000, -6504719581857/3355443200000000], [20682373471491/209715200000000, -1479681880935663/3355443200000000]]`
- step 3, `mean_z` = `[1066649717/5242880000, 156409/819200]`
- step 3, `output_candidates` = `[1, 1, 16071/25600, 17529/25600, 101571317/327680000, 119398283/327680000]`
- step 3, `x_out` = `101571317/327680000`

## dream_two_sample_recursive_differences

Two full unprojected iterations with nonidentical sampled Hessians and mini-batch size 2, testing paired sample differences, the 1/(bq) normalization, skipped estimator, and two-round accelerated mixing.

### 输入与参数

```json
{
  "inputs": {
    "objective": "F_ij(x,y)=a*x^2/2+c*x*y-d*y^2/2+e*x+h*y; tuple [a,c,d,e,h]. Offline uniform finite sum per agent.",
    "component_coefficients": [
      [
        [
          1,
          1,
          2,
          1,
          2
        ],
        [
          3,
          2,
          2,
          1,
          2
        ],
        [
          2,
          -1,
          2,
          1,
          2
        ]
      ],
      [
        [
          2,
          -1,
          3,
          -1,
          -2
        ],
        [
          4,
          1,
          3,
          -1,
          -2
        ],
        [
          3,
          2,
          3,
          -1,
          -2
        ]
      ]
    ],
    "initial_z": [
      -0.5,
      0.75
    ],
    "y_interval": null,
    "W": [
      [
        0.9,
        0.1
      ],
      [
        0.1,
        0.9
      ]
    ],
    "refresh_draws": [
      0,
      0
    ],
    "active_draws": [
      [
        1,
        1
      ],
      [
        0,
        1
      ]
    ],
    "sample_indices": [
      [
        [
          0,
          1
        ],
        [
          1,
          2
        ]
      ],
      [
        [
          2,
          0
        ],
        [
          0,
          2
        ]
      ]
    ],
    "output_draw_index": 3
  },
  "parameters": {
    "eta": 0.125,
    "gamma": 0.25,
    "p": 0.25,
    "q": 0.5,
    "b": 2,
    "b_prime": 3,
    "K0": 2,
    "K": 2,
    "K_prime": 3,
    "T": 2,
    "fastmix_return": "a^(K), exactly K effective recurrences",
    "index_convention": "agent and sample indices zero based; output list is time-major x_0,...,x_(T-1)"
  }
}
```

### 独立推导

Use the same exact FastMix multipliers as case 1; here K0=K=2 means disagreement multiplier 101/400. The six component Hessians are nonidentical. The initial exact local gradients are g0=[(1/2,1/6),(-2,-55/12)]; s0=FastMix(g0,2). At each update form x-eta*gamma*u and y+eta*v simultaneously from the old state, then FastMix them. No y constraint means projection is the identity. At t=0 both agents update from two explicit, distinct sample indices. Because b=2 and q=1/2, the multiplier on the SUM of paired gradient differences is exactly 1; replacing the sum by a mean would be wrong. At t=1 agent 0 has omega=0, so g2(0)=g1(0) despite changing z; agent 1 again uses two paired gradient differences. Mix s+g_new-g_old for each tracker, preserving its network mean equal to mean(g). The selected uniform historical index 3 returns agent 1 at t=1, not either final x2. These are prescribed finite-step algorithm inputs, not theorem-calibrated convergence parameters.

### 精确中间状态与输出

- step 0, `z` = `[[-1/2, 3/4], [-1/2, 3/4]]`
- step 0, `g` = `[[1/2, 1/6], [-2, -55/12]]`
- step 0, `s` = `[[-139/320, -15443/9600], [-341/320, -26957/9600]]`
- step 1, `pre_projection` = `[[-4981/10240, 42157/76800], [-4779/10240, 30643/76800]]`
- step 1, `projected` = `[[-4981/10240, 42157/76800], [-4779/10240, 30643/76800]]`
- step 1, `z` = `[[-1962201/4096000, 15141457/30720000], [-1941799/4096000, 13978543/30720000]]`
- step 1, `g` = `[[-1920553/10240000, 77289299/61440000], [-55365879/20480000, -168083471/61440000]]`
- step 1, `tracker_input` = `[[-11488553/10240000, -31785901/61440000], [-36229879/20480000, -59008271/61440000]]`
- step 1, `s` = `[[-22344263927/16384000000, -3356820943/4915200000], [-25021324073/16384000000, -3906712817/4915200000]]`
- step 1, `mean_z` = `[-61/128, 91/192]`
- step 2, `pre_projection` = `[[-228817464073/524288000000, 16024244017/39321600000], [-223528947927/524288000000, 4661940741/13107200000]]`
- step 2, `projected` = `[[-228817464073/524288000000, 16024244017/39321600000], [-223528947927/524288000000, 4661940741/13107200000]]`
- step 2, `z` = `[[-90736352465373/209715200000000, 2034984516199/5242880000000], [-90202212334627/209715200000000, 5899072947403/15728640000000]]`
- step 2, `g` = `[[-1920553/10240000, 77289299/61440000], [-322577799728657/125829120000000, -1391615197180601/629145600000000]]`
- step 2, `tracker_input` = `[[-22344263927/16384000000, -3356820943/4915200000], [-174573608033297/125829120000000, -170499694716601/629145600000000]]`
- step 2, `s` = `[[-138171086228595163/100663296000000000, -266245622152967699/503316480000000000], [-46256985921843479/33554432000000000, -213892598183513101/503316480000000000]]`
- step 2, `mean_z` = `[-113086603/262144000, 93781457/245760000]`
- step 2, `output_candidates` = `[-1/2, -1/2, -1962201/4096000, -1941799/4096000]`
- step 2, `x_out` = `-1941799/4096000`

## 冻结与复核

`contract.json` 保存完整输入、条件随机抽样和数字预期；`derive_expected.py` 为独立算术来源。契约必须在接触被测代码之前冻结，不得根据实现的行为改写预期。数值容差 atol=1e-9, rtol=1e-7。
