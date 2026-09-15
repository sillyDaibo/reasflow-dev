"""Assemble the project-facing explanation from reviewed paper and trajectory evidence."""
from pathlib import Path
import json
import re
import sys

HERE = Path(__file__).resolve().parent
O = HERE.parent
sys.path.insert(0, str(O))
from markdown_format import normalize_bold, shift_headings

P = O.parent
TARGET = P / 'CPU30_PROJECT_PROGRESS_AND_CAPABILITY_REPORT.md'
scores = json.loads((O / 'score_analysis.json').read_text())['summaries']
skills = {r['paper_id']: r['items'] for r in json.loads(
    (O / 'trajectory/skill_usage_audit.json').read_text()) if r['condition'] == 'B'}

# Editorial assessments: candidate uses and remaining verification, not admission certificates.
assessments = {
 '1811.03761': ('RSA', '异构场景核心现象较强；范数参数更完整',
  '核心异构现象也出现；范数协议有偏离',
  '两侧均值得保留为鲁棒聚合实验候选。优先补验同步更新与梯度缩放约定；B 还需对齐逐范数参数。不能把现有结果直接推广为所有攻击和范数下的理论保证。'),
 '1904.12017': ('Laplacian 分层模型', '四类应用已建立，房价结果接近论文',
  '四类应用已建立，部分泛化结果较好',
  '两侧有 ADMM 与图正则建模的复用价值。先澄清 Separate 基线、拆分和收敛条件，再补 Chicago；B 的旧运行误引应单独重评。较低分数不能等同于求解器不可用。'),
 '2102.06704': ('ProxRR / FedRR', '核心 prox 机制存在，部分结果使用替代指标',
  'FedRR 比较较充分，步长调度仍偏离',
  '可作为随机重排与 epoch 末 prox 的候选实现参考。复用前需对齐步长、正则处理和误差指标；B 的较高结果分并未证明全文或理论复杂度更完整复现。'),
 '2111.03820': ('DPG-RR', '有逐样本更新，部分目标下降关系成立',
  '部分结果接近，但大 batch 改变 RR 更新路径',
  '涉及随机重排机制的后续研究，宜先核对 A 的逐样本实现。B 不能直接作为原论文逐样本 RR 的等价基线；两侧还需核验共识操作与比较预算。'),
 '2201.13320': ('BEER', '短跑与对照缺失；CNN 判定错配',
  '消融覆盖更广；缩小 CNN 且核心优势不稳',
  '可以参考压缩与梯度追踪的组织方式，但两侧当前结果都不足以作为论文性能基准。优先补模型结构、基线语义和有效训练，再评估通信优势。'),
 '2207.04555': ('仿射约束去中心化优化', '主要迭代排序出现；有预算封顶',
  '主要迭代排序出现；正式停止阈值不同',
  '两侧有三类求解路线的比较参考价值。先统一停止阈值、未收敛处理和线性系统求解口径；迭代现象与跨实现的实际耗时结论要分别使用。'),
 '2212.02387': ('DREAM', '局部通信比较通过，核心整体优势不稳',
  '有正式多种子实验，仍有梯度尺度与混合递推问题',
  '先保留为失败诊断案例和实验材料。尤其 B 的核心递推需要修正和独立核验，A 也未稳定支持主优势；不宜直接作为 DREAM 性能基线用于新算法比较。'),
 '2306.04961': ('同时结构化 IRLS', '覆盖相对较广；加权子问题处理偏离',
  '范围缩减；权重与子求解尚有核心问题',
  '生成器和部分 baseline 可作为后续核查起点，IRLS 核心求解器应先独立验收。相变、二次收敛和恢复能力尚不能作为已验证资产供下游引用。'),
 '2306.05100': ('分布式 VI / ProxSkip', '多任务得到收敛，随机法部分结果较好',
  '确定性部分结果较强，随机法与预算存在差异',
  '可保留博弈算子和通信实验候选实现。先核对随机估计器缩放、步长和通信预算；量规 p/γ 错误要修，但修正评分不能替代缺失的附录实验。'),
 '2309.05204': ('PIRL1 / APIRL1 去模糊', '完整主要重复实验，迭代加速现象出现',
  '同样覆盖主要重复实验，迭代加速现象出现',
  '两侧均值得作为图像逆问题候选实验包继续验收。先对齐聚合统计、参考值与实测值、停止和噪声协议；可以讨论已观察的迭代加速，不能照搬原论文全部性能表。'),
 '2310.09804': ('Byzantine 学习与压缩', '多方法实现；部分参数项得分不能证明调参',
  '组合覆盖较广；通信单位和记账有偏差',
  '攻击生成与压缩方法可作为候选组件审查。尤其 B 的 bits 含义和刷新通信计数必须先修，才能用于下游通信效率比较；理论步长也需真实实现而非代理公式。'),
 '2501.04443': ('LocalSGD / SCAFFOLD 理论实验', '固定步长下部分趋势较强，含假阳性评分',
  '主图与扫描有产物，核心优于 MbSGD 未成立',
  '可作为可控异质性实验的候选脚手架。应先统一调参、MbSGD 有效步长及参数映射，再解释理论趋势；B 的成功绘图不等于成功验证理论优势。'),
 '2501.09516': ('Stiefel ManPQN', '部分规模与 UF 数据有结果；曲率近似有偏离',
  '少数配置有结果，核心加速没有稳定复现',
  '可保留数据接入与现有配置供诊断，核心 ManPQN 方向求解、曲率与停止条件需先核验。不能把同名实现当可信流形优化 baseline，也不能用一个目标值匹配替代加速验证。'),
 '2501.18312': ('PPS 量化', '部分高斯与 MNIST 结果，有初始化偏离',
  '关键 M=1/r=10 配置与初始化覆盖更充分',
  'PPS 采样和质量—通信折中有候选复用价值。优先核对初始化、恢复公式与独立评估；两侧均缺论文指定的 MNIST 参数组合，通信估计也不等于真实网络收益。'),
 '2503.07594': ('随机梯度 SCAFFOLD', '核心对 FedAvg 优势与规模趋势较强',
  '核心现象也较强，采样修复后重跑',
  '建议作为首批独立验收候选，两侧都值得保留。先解决正文与官方代码轮数冲突、统一尾部统计和饱和解释，再验证独立运行与组件复用；通过门槛并不等于理论全文已重证。'),
 '2504.19004': ('Setwise Coordinate Descent', '核心变体与部分趋势存在；异步任务缺失',
  '核心变体存在；部分特设趋势和异步任务未完成',
  '可参考集合内坐标选择和通信比较的候选实现，但完整异步框架尚未复现。复用前核对实例构造、Lipschitz 估计与指标定义，不能拿固定预算消息比代替收敛率。'),
}
assert set(assessments) == {s['paper_id'] for s in scores}

trajectories = {}
for line in (O / 'trajectory/trajectory_analysis.md').read_text().splitlines():
    cells = line.split('|')
    if len(cells) == 7 and re.fullmatch(r'\d{4}\.\d{5}', cells[1]):
        trajectories[cells[1]] = cells[5].strip()
assert set(trajectories) == set(assessments)
# The targeted Skill audit supports script attempts separately from generic plotting messages.
trajectories['2102.06704'] = trajectories['2102.06704'].replace('并生成 smart-plot', '并整理图表')
trajectories['2212.02387'] = trajectories['2212.02387'].replace('；耗时大部分为等待完整梯度/数据任务', '')

def link(path, label, line=None):
    return f'[{label}]({path.resolve()}{":" + str(line) if line else ""})'

def skill_evidence(pid, item):
    file = O / 'trajectory' / f'{pid}-B.observable.md'
    pattern = f'### L{item["line"]} · '
    number = next(i for i, line in enumerate(file.read_text().splitlines(), 1) if line.startswith(pattern))
    label = '指令访问证据' if item['kind'] == 'read_skill' else '脚本尝试证据'
    return link(file, label, number)

parts = [(HERE / 'overview.md').read_text(), (HERE / 'skills_and_process.md').read_text()]
parts += ['## 6. 已完成论文的能力与产物总览', '',
 '下表是用途判断的摘要，不是新增评分。两侧多数产物同时包含可保留部分和待修问题；完整依据在下一节。', '',
 '| 论文 | A 的实际表现 | B 的实际表现 |', '| --- | --- | --- |']
for score in scores:
    pid = score['paper_id']; name, a, b, use = assessments[pid]
    parts.append(f'| {pid}：{name} | {a} | {b} |')
parts += ['', '## 7. 逐篇理解：论文主张、复现情况、执行过程与复用边界', '',
 '每篇依次给出项目用途判断、原始评分、论文主张、实验口径、实际结果、具体评分问题，以及 A/B 执行过程和 B 的技能使用。分数相同不代表实现等价，分数不同也不自动解释差距来源。', '']
for index, score in enumerate(scores, 1):
    pid = score['paper_id']; name, a, b, use = assessments[pid]
    source = (O / 'papers' / f'{pid}.md').read_text()
    title, body = source.split('\n', 1)
    parts += [f'### 7.{index} {title.lstrip("# ")}', '', '**当前用途判断：** ' + use, '',
              shift_headings(body, 2).strip(), '', '#### 关键 Trace / Trajectory', '', trajectories[pid], '',
              '#### B 的实际 Skill 使用', '']
    items = skills[pid]
    for kind, label in [('read_skill', '明确读取指令'), ('script_execution_attempt', '打包脚本执行尝试')]:
        selected = [item for item in items if item['kind'] == kind]
        names = sorted({item['skill'] for item in selected})
        value = '、'.join('`' + s + '`' for s in names) if names else '未观察到独立命令记录'
        evidence = ' ' + skill_evidence(pid, selected[0]) if selected else ''
        parts += [f'- **{label}：** {value}。{evidence}']
    parts += ['', '该篇技能清单按可观察命令列出，脚本成功与作用不能由尝试记录推定。', '',
              link(O / 'ledgers' / f'{pid}.md', '全部逐项评分：检查内容、权重、A/B 判定与原始理由'), '']
parts += [(HERE / 'next_steps.md').read_text()]
text = normalize_bold('\n'.join(parts)).rstrip() + '\n'
assert not any(term in text for term in ['SHA256', '哈希', '工具事件更多', 'trace首末时间'])
TARGET.write_text(text)
print(TARGET)
print('Bytes:', TARGET.stat().st_size, 'Papers:', len(scores))
