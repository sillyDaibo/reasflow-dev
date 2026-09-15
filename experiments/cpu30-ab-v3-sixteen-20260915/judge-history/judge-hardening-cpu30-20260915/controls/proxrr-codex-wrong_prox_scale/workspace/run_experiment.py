#!/usr/bin/env python3
"""Run the paper-scale Figure 1 or Figure 2 experiment and save all evidence."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import platform
import shlex
import sys
import time
from pathlib import Path

import numpy as np

from rr_prox_fed.algorithms import ProxRR, ProxSGD, run_reference_solver
from rr_prox_fed.data import load_libsvm, partition_clients
from rr_prox_fed.federated import FedRR, LocalSGD
from rr_prox_fed.objectives import ElasticNetLogistic


def _jsonable(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=_jsonable) + "\n", encoding="utf-8")


def _write_history(path, traces, f_star):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method", "seed", "iteration", "epoch_or_pass", "prox_evaluations", "objective", "objective_gap"])
        for trace in traces:
            for row in zip(trace.iterations, trace.epochs, trace.prox_evaluations, trace.objective):
                writer.writerow([trace.method, trace.seed, row[0], row[1], row[2], row[3], max(0.0, row[3] - f_star)])


def _plot_figure1(path, traces, f_star):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for trace in traces:
        gap = np.maximum(np.asarray(trace.objective) - f_star, 1e-16)
        axes[0].plot(trace.iterations, gap, label=trace.method)
        axes[1].plot(trace.prox_evaluations, gap, label=trace.method)
    axes[0].set_xlabel("stochastic iterations"); axes[0].set_ylabel("objective gap"); axes[0].set_yscale("log")
    axes[1].set_xlabel("proximal evaluations"); axes[1].set_ylabel("objective gap"); axes[1].set_yscale("log")
    axes[0].legend(); axes[1].legend(); fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def _plot_importance(path, traces, f_star):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 5.3))
    for trace in traces:
        ax.plot(trace.epochs, np.maximum(np.asarray(trace.objective) - f_star, 1e-16), label=trace.method)
    ax.set_xlabel("data passes"); ax.set_ylabel("objective gap"); ax.set_yscale("log"); ax.legend(); fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def _plot_figure2(path_rounds, path_passes, traces, f_star):
    import matplotlib.pyplot as plt
    for x_index, path, xlabel in [(2, path_rounds, "communication rounds"), (3, path_passes, "data passes")]:
        fig, ax = plt.subplots(figsize=(7.5, 5.3))
        for trace in traces:
            gap = np.maximum(np.asarray(trace.objective) - f_star, 1e-16)
            ax.plot(np.asarray(trace.epochs), gap, label=trace.method)
        ax.set_xlabel(xlabel); ax.set_ylabel("objective gap"); ax.set_yscale("log"); ax.legend(); fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def run_figure1(args, out):
    A, b, provenance = load_libsvm("a1a", args.data_dir)
    base = ElasticNetLogistic(A, b, l1=0.0, l2=0.0)
    L = base.smoothness
    l1, l2 = 1e-3, L / A.shape[0]
    objective = ElasticNetLogistic(A, b, l1=l1, l2=l2, l2_in_prox=True)
    epochs, batch_size = args.epochs, 1
    x0 = np.zeros(A.shape[1])
    ref_x, f_star = run_reference_solver(objective, x0=x0, iterations=args.reference_iterations)
    step = 1.0 / objective.batch_smoothness(batch_size)
    # Supplementary implementation detail: decay is O(1/t), with the
    # coefficient recommended for the proximal stochastic methods.
    rr_decay, sgd_decay = l2 / 7.0, l2 / 2.0
    traces = []
    for method in (ProxSGD(objective, epochs * A.shape[0], step, args.seed, batch_size, decay_coefficient=sgd_decay),
                   ProxRR(objective, epochs, step, args.seed, batch_size, reshuffle=True, decay_coefficient=rr_decay),
                   ProxRR(objective, epochs, step, args.seed, batch_size, reshuffle=True, prox_every_iteration=True, decay_coefficient=rr_decay)):
        _, trace = method.run(x0)
        traces.append(trace)
    config = {"experiment": "figure1", "dataset": provenance, "seed": args.seed, "epochs": epochs,
              "batch_size": batch_size, "l1": l1, "l2": l2, "logistic_smoothness": L,
              "step_size": step, "reference_iterations": args.reference_iterations,
              "decay_coefficients": {"ProxSGD": sgd_decay, "ProxRR": rr_decay, "RR_heuristic": rr_decay},
              "reference_objective": f_star, "reference_solution_norm": float(np.linalg.norm(ref_x)),
              "methods": [trace.method for trace in traces], "command": " ".join(shlex.quote(x) for x in sys.argv)}
    _write_json(out / "config.json", config); _write_json(out / "metrics.json", {"experiment": "figure1", "f_star": f_star,
        "final_objective": {trace.method: trace.objective[-1] for trace in traces},
        "final_gap": {trace.method: max(0.0, trace.objective[-1] - f_star) for trace in traces},
        "prox_evaluations": {trace.method: trace.prox_evaluations[-1] for trace in traces},
        "elapsed_seconds": {trace.method: trace.elapsed_seconds for trace in traces}, "provenance": provenance})
    _write_history(out / "history.csv", traces, f_star); _plot_figure1(out / "figure1.png", traces, f_star)
    return config


def run_figure2(args, out):
    A, b, provenance = load_libsvm("mushrooms", args.data_dir)
    clients, usable = partition_clients(A, b, args.clients)
    base = ElasticNetLogistic(A, b, l1=0.0, l2=0.0, l2_in_prox=False)
    L = base.smoothness; l2 = L / usable
    objective = ElasticNetLogistic(A[:usable], b[:usable], l1=0.0, l2=l2, l2_in_prox=False)
    _, f_star = run_reference_solver(objective, iterations=args.reference_iterations)
    local_batch_size = 8
    step_rr = 1.0 / max(1e-12, objective.batch_smoothness(local_batch_size))
    rr_decay, local_decay = l2 / 7.0, l2 / 2.0
    client_n = clients[0][0].shape[0]; rounds = args.rounds
    # The Local-SGD theorem uses O(1/(L H)); the paper reports both H and H/5.
    full = LocalSGD(clients, rounds, client_n, step_rr / client_n, args.seed, l2=l2, l2_in_prox=False, local_batch_size=local_batch_size, decay_coefficient=local_decay)
    partial = LocalSGD(clients, rounds, max(1, client_n // 5), step_rr / client_n, args.seed, l2=l2, l2_in_prox=False, local_batch_size=local_batch_size, decay_coefficient=local_decay)
    fed = FedRR(clients, rounds, step_rr, args.seed, l2=l2, l2_in_prox=False, reshuffle=True, local_batch_size=local_batch_size, decay_coefficient=rr_decay)
    full_trace = full.run()[1]; full_trace.method = "LocalSGD_full_pass"
    partial_trace = partial.run()[1]; partial_trace.method = "LocalSGD_partial_pass"
    fed_trace = fed.run()[1]
    traces = [full_trace, partial_trace, fed_trace]
    config = {"experiment": "figure2", "dataset": provenance, "seed": args.seed, "clients": args.clients,
              "usable_rows": usable, "client_rows": client_n, "rounds": rounds, "l2": l2,
              "logistic_smoothness": L, "local_batch_size": local_batch_size, "fedrr_step_size": step_rr,
              "decay_coefficients": {"FedRR": rr_decay, "LocalSGD": local_decay}, "local_full_steps": client_n,
              "local_partial_steps": max(1, client_n // 5), "reference_iterations": args.reference_iterations,
              "reference_objective": f_star, "methods": [trace.method for trace in traces],
              "command": " ".join(shlex.quote(x) for x in sys.argv)}
    _write_json(out / "config.json", config); _write_json(out / "metrics.json", {"experiment": "figure2", "f_star": f_star,
        "final_objective": {trace.method: trace.objective[-1] for trace in traces},
        "final_gap": {trace.method: max(0.0, trace.objective[-1] - f_star) for trace in traces},
        "elapsed_seconds": {trace.method: trace.elapsed_seconds for trace in traces}, "provenance": provenance})
    _write_history(out / "history.csv", traces, f_star)
    _plot_figure2(out / "communication_rounds.png", out / "data_passes.png", traces, f_star)
    return config


def run_importance(args, out):
    A, b, provenance = load_libsvm("a1a", args.data_dir)
    base = ElasticNetLogistic(A, b, l1=0.0, l2=0.0)
    L = base.smoothness; l1, l2 = 1e-3, L / A.shape[0]
    objective = ElasticNetLogistic(A, b, l1=l1, l2=l2, l2_in_prox=True)
    reference_path = Path("results/formal/figure1_a1a/metrics.json")
    if reference_path.is_file():
        f_star = float(json.loads(reference_path.read_text(encoding="utf-8"))["f_star"])
        reference_source = str(reference_path)
    else:
        _, f_star = run_reference_solver(objective, iterations=args.reference_iterations)
        reference_source = "computed"
    step = 1.0 / objective.batch_smoothness(1); decay = l2 / 7.0
    standard = ProxRR(objective, args.epochs, step, args.seed, 1, reshuffle=True, decay_coefficient=decay, record_every=20)
    importance = ProxRR(objective, args.epochs, step, args.seed, 1, reshuffle=True, importance_sampling=True, decay_coefficient=decay, record_every=20)
    _, standard_trace = standard.run(); _, importance_trace = importance.run()
    traces = [standard_trace, importance_trace]; importance_trace.method = "ProxRR_importance"
    config = {"experiment": "importance", "dataset": provenance, "seed": args.seed, "epochs": args.epochs,
              "l1": l1, "l2": l2, "logistic_smoothness": L, "step_size": step,
              "decay_coefficient": decay, "reference_iterations": args.reference_iterations,
              "reference_objective": f_star, "reference_source": reference_source, "methods": [t.method for t in traces],
              "command": " ".join(shlex.quote(x) for x in sys.argv)}
    _write_json(out / "config.json", config); _write_json(out / "metrics.json", {"experiment": "importance", "f_star": f_star,
        "final_objective": {t.method: t.objective[-1] for t in traces}, "final_gap": {t.method: max(0.0, t.objective[-1] - f_star) for t in traces},
        "prox_evaluations": {t.method: t.prox_evaluations[-1] for t in traces}, "elapsed_seconds": {t.method: t.elapsed_seconds for t in traces}, "provenance": provenance})
    _write_history(out / "history.csv", traces, f_star); _plot_importance(out / "importance.png", traces, f_star)
    return config


def run_smoke(args, out):
    from scipy.sparse import csr_matrix
    rng = np.random.default_rng(args.seed); X = rng.normal(size=(40, 8)); y = (rng.random(40) > .5).astype(float)
    objective = ElasticNetLogistic(csr_matrix(X), y, l1=.01, l2=.01)
    _, trace = ProxRR(objective, epochs=3, step_size=1.0 / objective.batch_smoothness(), seed=args.seed).run()
    config = {"experiment": "smoke", "seed": args.seed, "rows": 40, "features": 8, "methods": [trace.method]}
    _write_json(out / "config.json", config); _write_json(out / "metrics.json", {"experiment": "smoke", "final_objective": trace.objective[-1]})
    _write_history(out / "history.csv", [trace], min(trace.objective)); _plot_figure1(out / "figure1.png", [trace], min(trace.objective))
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=["smoke", "figure1", "figure2", "importance"], required=True)
    parser.add_argument("--data-dir", type=Path, default=Path(".run-data/datasets"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=140)
    parser.add_argument("--clients", type=int, default=8)
    parser.add_argument("--reference-iterations", type=int, default=4000)
    args = parser.parse_args(); out = args.output_dir; out.mkdir(parents=True, exist_ok=True)
    log_path = out / "run.log"
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(message)s")
    start = time.perf_counter(); logging.info("starting %s", args.experiment)
    if args.experiment == "figure1": config = run_figure1(args, out)
    elif args.experiment == "figure2": config = run_figure2(args, out)
    elif args.experiment == "importance": config = run_importance(args, out)
    else: config = run_smoke(args, out)
    machine = {"python": sys.version, "platform": platform.platform(), "processor": platform.processor(),
               "numpy": np.__version__, "logical_cpus": __import__("os").cpu_count(),
               "elapsed_seconds": time.perf_counter() - start}
    _write_json(out / "machine.json", machine); logging.info("completed in %.3fs", machine["elapsed_seconds"])
    _write_json(out / "resolved_config.json", config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
