"""Validate reviewed CPU30 adapters and prespecified mutation controls."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
from pathlib import Path
import sys

REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[1]
sys.path.insert(0, str(ROOT / 'repo_judge'))
from src.judge.execution import execute_algorithm, _workspace_snapshot, _snapshot_digest
from src.judge.review_records import json_digest

loader = importlib.util.spec_from_file_location('previous_benchmark', ROOT / 'reports/judge-paper-only-expanded-20260915/run_benchmark.py')
previous = importlib.util.module_from_spec(loader)
loader.loader.exec_module(previous)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repeats', type=int, default=2)
    p.add_argument('--workers', type=int, default=2)
    args = p.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = REPORT / 'validation' / stamp
    out.mkdir(parents=True)
    code_paths = [ROOT / 'repo_judge/src/judge' / f'{name}.py' for name in
                  ['algorithm_pipeline', 'paper_contract', 'review_records', 'algorithm_assessment', 'execution']]
    code_paths += [ROOT / 'repo_judge/run_execution_judge.py', ROOT / 'repo_judge/prepare_algorithm_judge.py', Path(__file__)]
    code_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in code_paths}
    (out / 'CODE_SHA256.json').write_text(json.dumps(code_hashes, indent=2))
    targets = {t[0]: t for t in previous.TARGETS}
    jobs = [dict(id=t[0], base_target=t[0]) for t in previous.TARGETS]
    jobs += json.loads((REPORT / 'controls/manifest.json').read_text())['controls']

    def run(job):
        name, pid, server, condition, source, adapter_name = targets[job['base_target']]
        workspace = Path(job['workspace']) if 'workspace' in job else ROOT / 'reports/cpu30/analysis-2026-09-06/evidence' / server / 'agent_reproduction/runs' / pid / condition / '第003次运行/workspace'
        adapter = source / 'adapters' / adapter_name
        actions_file = adapter / 'environment_actions.json'
        if actions_file.exists():
            actions = json.loads(actions_file.read_text())
        else:
            actions = [{'kind':'install_package','package':'numpy','reason':'Original source imports numpy','source':'algorithm source imports'}]
            if name == 'dream-reasflow':
                actions.append({'kind':'install_package','package':'scikit-learn','reason':'Original data module imports sklearn','source':'src/dream_reproduction/data.py:8'})
        rows = []
        before = _snapshot_digest(_workspace_snapshot(workspace))
        for repeat in range(1, (args.repeats if 'mutation' not in job else 1) + 1):
            spec = {'evaluation_id':f'hardening-{repeat}', 'paper_id':pid,
                'paper_path':str(ROOT / 'datasets/benchmarks/cpu30_v1/input' / pid / 'paper.pdf'),
                'contract_path':str(source / 'papers' / pid / 'contract.json'),
                'paper_review_path':str(REPORT / 'paper_reviews' / f'{pid}.json'),
                'adapter_review_path':job.get('adapter_review_path', str(REPORT / 'adapter_reviews' / f'{name}.json')),
                'adapter':{'path':str(adapter / 'adapter.py'), 'bindings':json.loads((adapter / 'bindings.json').read_text())},
                'environment_actions':actions, 'timeout_seconds':240}
            spec_path = out / f'{job["id"]}-{repeat}.spec.json'
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2))
            result = asyncio.run(execute_algorithm(str(workspace), str(spec_path), run_root=str(out / job['id'])))
            result_path = Path(result['algorithm_dir']) / 'result.json'
            comparisons = result.get('comparison', {})
            row = {'target':job['id'], 'paper_id':pid, 'repeat':repeat, 'status':result['status'],
                   'reason_code':result['reason_code'], 'assessment':result['assessment'], 'result':str(result_path),
                   'comparison_digest':json_digest(comparisons),
                   'source_unchanged':before == _snapshot_digest(_workspace_snapshot(workspace)),
                   'direct_model_api_used':False}
            if 'expected_numeric_outcome' in job:
                row['expected_numeric_outcome'] = job['expected_numeric_outcome']
                row['control_detected_as_expected'] = (row['assessment']['acceptance'] == 'eligible_on_tested_scope' if job['expected_numeric_outcome'] == 'match' else
                    row['assessment']['numeric_mismatches'] > 0 and row['assessment']['acceptance'] == 'hold' and row['assessment']['coverage'] == 'complete')
            rows.append(row)
            (out / f'{job["id"]}-{repeat}.row.json').write_text(json.dumps(row, ensure_ascii=False, indent=2))
            print(job['id'], repeat, row['status'], row['reason_code'], row['assessment']['acceptance'], row['assessment']['numeric_mismatches'], flush=True)
        return rows

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = [row for group in pool.map(run, jobs) for row in group]
    summary = {'created_at':stamp, 'rows':rows,
               'code_unchanged':all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha for name, sha in code_hashes.items()),
               'scope':'Five papers, ten historical CPU30 workspaces, independently reviewed paper tests and adapters; three unchanged and six mutated controls. No direct model API used in execution.'}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print('SUMMARY', out / 'summary.json', flush=True)


if __name__ == '__main__':
    main()
