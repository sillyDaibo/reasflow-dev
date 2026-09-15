#!/usr/bin/env python3
"""Run one formal experiment or all four paper case studies.

The command writes metrics, resolved configuration, provenance, a log-friendly
summary, and at least one figure under ``results/formal/<experiment_id>/``.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

from experiments.common import run_chicago, run_houses, run_mesothelioma, run_senate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", choices=["mesothelioma", "houses", "senate", "chicago", "all"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--maxiter", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    defaults = {"mesothelioma": 120, "houses": 180, "senate": 180, "chicago": 80}
    names = ["mesothelioma", "houses", "senate", "chicago"] if args.experiment == "all" else [args.experiment]
    for name in names:
        started = time.perf_counter()
        maxiter = args.maxiter if args.maxiter is not None else defaults[name]
        print(f"[{name}] starting seed={args.seed} maxiter={maxiter}", flush=True)
        fn = {"mesothelioma": run_mesothelioma, "houses": run_houses, "senate": run_senate, "chicago": run_chicago}[name]
        metrics = fn(seed=args.seed, maxiter=maxiter, verbose=args.verbose)
        elapsed = time.perf_counter() - started
        metrics["wall_time_seconds"] = elapsed
        metrics["resource"] = {
            "cpu_count_visible": os.cpu_count(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        }
        result_id = {"mesothelioma": "exp_001_mesothelioma", "houses": "exp_002_houses", "senate": "exp_003_senate", "chicago": "exp_004_chicago"}[name]
        path = Path("results/formal") / result_id / "metrics.json"
        path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"experiment": name, "metrics": metrics}, sort_keys=True, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
