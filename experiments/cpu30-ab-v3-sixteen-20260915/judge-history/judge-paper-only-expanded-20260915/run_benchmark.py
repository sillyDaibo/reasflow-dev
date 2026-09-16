"""Replay independently prepared paper tests against existing CPU30 workspaces."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
OLD = ROOT / 'reports/judge-paper-only-20260915'
sys.path.insert(0, str(ROOT / 'repo_judge'))
from src.judge.execution import execute_algorithm, _workspace_snapshot, _snapshot_diff
from src.judge.paper_contract import validate_contract, contract_digest

TARGETS = [
    ('rsa-codex', '1811.03761', 'OptiRepro_cpu', 'Codex原生-完整复现-Goal', OLD, 'rsa/codex'),
    ('rsa-reasflow', '1811.03761', 'OptiRepro_cpu', 'ReasFlow实验Agent-完整复现-Goal', OLD, 'rsa/reasflow'),
    ('dream-codex', '2212.02387', 'OptiRepro_cpu_2', 'Codex原生-完整复现-Goal', OLD, 'dream/native'),
    ('dream-reasflow', '2212.02387', 'OptiRepro_cpu_2', 'ReasFlow实验Agent-完整复现-Goal', OLD, 'dream/reasflow'),
]
for short, pid in [('stratified', '1904.12017'), ('proxrr', '2102.06704'), ('beer', '2201.13320')]:
    for condition, label in [('Codex原生-完整复现-Goal', 'codex'), ('ReasFlow实验Agent-完整复现-Goal', 'reasflow')]:
        TARGETS.append((f'{short}-{label}', pid, 'OptiRepro_cpu_2', condition, REPORT, f'{short}/{label}'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_sha(path):
    if not path.is_file():
        return None
    return hashlib.sha256(json.dumps(json.loads(path.read_text()), sort_keys=True,
                                    separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--targets', nargs='+', choices=[t[0] for t in TARGETS])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    chosen = [t for t in TARGETS if not args.targets or t[0] in args.targets]
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = REPORT / 'validation' / stamp
    out.mkdir(parents=True)

    def run_target(target):
        name, pid, server, condition, source, adapter_name = target
        workspace = ROOT / 'reports/cpu30/analysis-2026-09-06/evidence' / server / 'agent_reproduction/runs' / pid / condition / '第003次运行/workspace'
        adapter = source / 'adapters' / adapter_name
        paper = ROOT / 'datasets/benchmarks/cpu30_v1/input' / pid / 'paper.pdf'
        standard = source / 'papers' / pid / 'contract.json'
        validated = validate_contract(json.loads(standard.read_text()), sha(paper))
        frozen_digest = contract_digest(validated)
        before = _workspace_snapshot(workspace)
        rows = []
        actions_file = adapter / 'environment_actions.json'
        if actions_file.exists():
            actions = json.loads(actions_file.read_text())
        else:
            assert source == OLD, f'Missing dependency evidence: {actions_file}'
            actions = [{'kind': 'install_package', 'package': 'numpy', 'reason': 'Original source imports numpy', 'source': 'algorithm source imports'}]
            if name == 'dream-reasflow':
                actions.append({'kind': 'install_package', 'package': 'scikit-learn', 'reason': 'Original data module imports sklearn', 'source': 'src/dream_reproduction/data.py:8'})
        for repeat in range(1, args.repeats + 1):
            spec = {
                'evaluation_id': f'paper-expanded-{stamp}-{repeat}', 'paper_id': pid,
                'paper_path': str(paper), 'contract_path': str(standard),
                'adapter': {'path': str(adapter / 'adapter.py'),
                            'bindings': json.loads((adapter / 'bindings.json').read_text()),
                            'reason': 'Independent adapter preparation from public inputs and original workspace only; see ADAPTER_REVIEW.md.'},
                'environment_actions': actions, 'timeout_seconds': 240,
            }
            spec_path = out / f'{name}-{repeat}.spec.json'
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2))
            start = datetime.now(timezone.utc)
            result = asyncio.run(execute_algorithm(str(workspace), str(spec_path), run_root=str(workspace.parent)))
            algorithm_dir = Path(result['algorithm_dir'])
            checks = result.get('comparison', {}).get('checks', [])
            row = {
                'target': name, 'paper_id': pid, 'repeat': repeat,
                'status': result['status'], 'reason_code': result['reason_code'], 'reason': result['reason'],
                'elapsed_seconds': (datetime.now(timezone.utc) - start).total_seconds(),
                'workspace': str(workspace), 'result': str(algorithm_dir / 'result.json'),
                'contract_digest': result.get('contract_digest'), 'contract_unchanged': contract_digest(json.loads(standard.read_text())) == frozen_digest,
                'adapter_sha256': sha(adapter / 'adapter.py'),
                'checks': len(checks), 'failed_checks': sum(not c.get('passed') for c in checks),
                'numerical_mismatches': sum(not c.get('passed') and c.get('reason_code') == 'VALUE_MISMATCH' for c in checks),
                'integrity_ok': result.get('source_integrity', {}).get('integrity_ok'),
                'observations_sha256': json_sha(algorithm_dir / 'comparison/observations.json'),
                'comparisons_sha256': json_sha(algorithm_dir / 'comparison/checks.json'),
                'direct_model_api_used': False,
            }
            rows.append(row)
            (out / f'{name}-{repeat}.row.json').write_text(json.dumps(row, ensure_ascii=False, indent=2))
            print(json.dumps(row, ensure_ascii=False), flush=True)
        (out / f'{name}.integrity.json').write_text(json.dumps(_snapshot_diff(before, _workspace_snapshot(workspace)), indent=2))
        return rows

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = [r for group in pool.map(run_target, chosen) for r in group]
    summary = {'created_at': stamp, 'rows': rows, 'repeats': args.repeats,
               'scope': 'Real existing CPU30 workspaces, frozen paper-only Agent standards, independent adapters; no model API call during replay.'}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print('SUMMARY', out / 'summary.json', flush=True)


if __name__ == '__main__':
    main()
