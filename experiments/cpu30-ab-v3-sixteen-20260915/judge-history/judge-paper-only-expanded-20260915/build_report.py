"""Aggregate explicitly selected complete benchmark batches without hiding failures."""
import argparse
import hashlib
import json
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[1]
OLD = ROOT / 'reports/judge-paper-only-20260915'
LABELS = {'rsa': 'RSA', 'dream': 'DREAM', 'stratified': '分层模型 ADMM', 'proxrr': 'ProxRR / FedRR', 'beer': 'BEER'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('summaries', nargs='+', type=Path)
    args = parser.parse_args()
    rows = [r for path in args.summaries for r in json.loads(path.read_text())['rows']]
    targets = sorted({r['target'] for r in rows})
    assert len(targets) == 10 and len(rows) == 30
    assert len({r['paper_id'] for r in rows}) == 5
    stability = {}
    cases = {}
    for target in targets:
        group = [r for r in rows if r['target'] == target]
        assert sorted(r['repeat'] for r in group) == [1, 2, 3]
        stability[target] = {
            'status_equal': len({(r['status'], r['reason_code']) for r in group}) == 1,
            'observations_available': all(r['observations_sha256'] is not None for r in group),
            'observations_equal': len({r['observations_sha256'] for r in group}) == 1,
            'comparisons_equal': len({r['comparisons_sha256'] for r in group}) == 1,
            'workspace_unchanged': all(r['integrity_ok'] for r in group),
            'contract_unchanged': all(r['contract_unchanged'] for r in group),
        }
        result = json.loads(Path(group[0]['result']).read_text())
        checks = result.get('comparison', {}).get('checks', [])
        cases[target] = {}
        for case_id in dict.fromkeys(c.get('case_id') for c in checks):
            subset = [c for c in checks if c.get('case_id') == case_id]
            cases[target][case_id] = {'checks': len(subset), 'failed_checks': sum(not c['passed'] for c in subset),
                                     'numerical_mismatches': sum(not c['passed'] and c.get('reason_code') == 'VALUE_MISMATCH' for c in subset)}
    summary = {'papers': 5, 'workspaces': 10, 'repeats_each': 3, 'runs': 30,
               'selected_batches': [str(p.resolve()) for p in args.summaries], 'rows': rows,
               'stability': stability, 'case_comparisons': cases,
               'scope': 'Frozen paper-only standards replayed against historical CPU30 repositories; does not measure independent model generation repeatability.'}
    (REPORT / 'FINAL_SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    paper_stats = []
    for pid in ['1811.03761', '2212.02387', '1904.12017', '2102.06704', '2201.13320']:
        source = OLD if pid in ['1811.03761', '2212.02387'] else REPORT
        p = source / 'papers' / pid / 'contract.json'
        c = json.loads(p.read_text())
        paper_stats.append({'paper_id': pid, 'title': c['paper']['title'], 'cases': len(c['cases']),
                            'observations': sum(len(x['expected']) for x in c['cases']),
                            'contract': str(p), 'raw_sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    (REPORT / 'PAPER_STANDARDS.json').write_text(json.dumps(paper_stats, ensure_ascii=False, indent=2) + '\n')
    lines = ['# 五篇论文算法 Judge 扩大实测', '',
             '日期：2026-09-15（Asia/Shanghai）。本轮重新运行 5 篇论文、10 个已有复现仓库，每个重复 3 次，共 30 次。不是把前一轮的 12 次记录直接合并计数。', '',
             '## 方法与范围', '',
             '保留原有静态 Judge。新增算法检查先从原论文提取核心算法，设计输入并推演每一步状态，冻结答案后才准备仓库调用脚本。脚本只拿到公开输入和状态名称，不拿预期数值；最终由程序逐值比较。', '',
             '新增 ADMM、ProxRR/FedRR、BEER 三篇，各由一个论文 Agent 直接读取原 PDF 并视觉核对公式，使用独立算术脚本交叉计算。随后轮换到未读该论文答案的 Agent 编写适配器。原 RSA/DREAM 使用上一轮已经冻结的标准与经过审查的适配器，本轮重新实际执行。', '',
             f'五篇合计 {sum(x["cases"] for x in paper_stats)} 个实验、{sum(x["observations"] for x in paper_stats)} 项状态观察（数组观察含多个数值）。每份同论文标准用于两种配置，且三次复测保持完全相同。', '',
             '输入来自独立设计的小实验；调用的是 CPU30 第 003 次历史 runs 的已有 workspace 本地镜像。检查原算法有限步行为，不是完整训练、全库接口或全部 30 篇验收。适配时的输入函数、初始化与随机序列注入不代表仓库原有命令行已经支持这些输入。', '',
             '## 最终结果', '',
             '| 论文 / 配置 | 结果状态 | 数值差异数 | 重复结果和观察一致 | 证据 |',
             '|---|---|---:|---|---|']
    meanings = {'PROBE_PASS': '所选实验通过', 'INCONSISTENT': '数值不一致', 'INCONCLUSIVE': '无法完整判定',
                'RUN_FAILED': '执行或观测失败', 'ENVIRONMENT_FAILED': '环境准备失败'}
    for target in targets:
        r = next(r for r in rows if r['target'] == target)
        short, variant = target.split('-')
        consistent = all(stability[target].values())
        lines.append(f'| {LABELS[short]} / {"Codex 原生" if variant == "codex" else "ReasFlow"} | {meanings[r["status"]]} | {r["numerical_mismatches"]} | {"3/3" if consistent else "需查看明细"} | [结果]({r["result"]}) |')
    lines += ['', '数值差异数逐个标量计数，包含一个早期错误的后续影响，不等于独立缺陷数。“无法完整判定”可以同时有已经确认的局部数值差异，完整实验不授予通过。', '',
              '## 重复性与完整性', '',
              f'{sum(all(s.values()) for s in stability.values())}/10 个目标的三次状态、实际观察 JSON 和比较 JSON 一致，且有实际观察；{sum(bool(r["integrity_ok"]) for r in rows)}/30 次 workspace 内容未改变；{sum(bool(r["contract_unchanged"]) for r in rows)}/30 次原论文标准未改变。完整逐例结果在 FINAL_SUMMARY.json。', '',
              '这里测量的是同一标准和适配器下的执行重复性。模型重新识别算法、设计不同实验、生成不同适配器的稳定性未被这个数字覆盖。', '']
    audit = REPORT / 'EVIDENCE_REVIEW.md'
    if audit.exists():
        lines += ['## 数值证据与适配器复核', '', audit.read_text(), '']
    lines += ['## API 使用说明', '',
              '- 上一轮直接 API 的地址为 `https://llmmelon.cloud/v1`，接口为 OpenAI-compatible `chat.completions`。',
              '- Key 从 `/Users/zanehuang/.config/optirepro/judge_api_key` 读取；未在报告中记录明文。当前文件内容 SHA256 前 12 位见 PLAN_AND_API_USAGE.json，用于区分配置，不能反推出密钥。',
              '- 主模型为 `gpt-5.6-sol`，两次生成分别遇到 503 服务过载与超时；`gpt-4.1-mini` 的备用尝试连接失败，没有接受任何 API 生成标准。',
              '- 本轮新增标准及适配器由应用内协作 Agent 完成，未显式覆盖 Agent 模型。不能把外部 API 模型名当作这些应用内 Agent 的实际运行模型。30 次执行复测使用已有标准和适配器，没有调用模型 API。',
              '- 外部 API 自动出题到自动适配的完整成功路径仍未通过验收。', '',
              '## 重跑与产物', '',
              '执行 `run_benchmark.py` 可重跑全部 10 个目标，也可以用 `--targets` 选择目标、`--repeats` 指定次数。使用具备 Judge 依赖的 Python 环境运行，现有测试环境为 `/tmp/optirepro-paper-judge-20260915/bin/python`。每次新建独立环境与评测目录，不覆盖既有证据。', '',
              '论文标准及推演：papers/；公开输入：public/；独立调用脚本、依赖与审查：adapters/；准备来源：PREPARATION_PROVENANCE.json；全部结果：FINAL_SUMMARY.json。', '',
              '本轮没有切换正式批量调度、重新进行静态模型评分，也没有修复被测仓库里的算法。本轮执行层、比较层及静态归档路径的 65 项工程测试通过；新增测试验证完整类方法名可识别，另一类的同名方法不能冒充目标方法。扩大后的真实仓库运行另行记录。', '']
    (REPORT / 'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps({'report': str(REPORT / 'REPORT.md'), 'targets': len(targets), 'runs': len(rows), 'stable_targets': sum(all(s.values()) for s in stability.values())}, ensure_ascii=False))


if __name__ == '__main__':
    main()
