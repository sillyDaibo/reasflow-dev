"""Formal and smoke experiment driver."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import time
import numpy as np

from .algorithms import BEER, CHOCOSGD, DSGD, D2
from .data import load_a9a, load_mnist, write_sources
from .graphs import mixing_matrix, spectral_gap
from .objectives import logistic_accuracy, logistic_loss_gradient, nn_accuracy, nn_loss_gradient


def _initial_params(task, dimension, seed):
    rng = np.random.default_rng(seed)
    if task == "a9a":
        return rng.normal(0, 0.01, dimension)
    # Xavier initialization for the 32-neuron, 784-input network.
    hidden, classes = 32, 10
    w1 = rng.normal(0, np.sqrt(2.0 / (dimension + hidden)), (hidden, dimension))
    w2 = rng.normal(0, np.sqrt(2.0 / (hidden + classes)), (classes, hidden))
    return np.concatenate([w1.ravel(), np.zeros(hidden), w2.ravel(), np.zeros(classes)])


def _make_algorithm(name, x0, w, cfg, seed):
    common = dict(mixing=w, lr=cfg["lr"], compressor=cfg.get("compressor", "identity"), compression_param=cfg.get("compression_param", 0), seed=seed)
    if name == "BEER":
        return BEER(x0, gamma=cfg["gamma"], **common)
    if name == "CHOCO-SGD":
        return CHOCOSGD(x0, gamma=cfg["gamma"], **common)
    if name == "DSGD":
        return DSGD(x0, mixing=w, lr=cfg["lr"])
    if name in ("D2", "D^2"):
        return D2(x0, mixing=w, lr=cfg["lr"])
    raise ValueError(name)


def run_experiment(config: dict, output: str | Path, rounds_override=None, clients_override=None):
    cfg = dict(config)
    if rounds_override is not None:
        cfg["rounds"] = rounds_override
    if clients_override is not None:
        cfg["clients"] = clients_override
    seed = int(cfg.get("seed", 0))
    clients = int(cfg["clients"])
    data_root = cfg["data_root"]
    if isinstance(data_root, str) and data_root.startswith("${"):
        env_name = data_root[2:data_root.find("}")]
        data_root = os.environ.get(env_name)
    if not data_root:
        data_root = "/home/hzy/optirepro/datasets/reproduction/v1/assets/" + ("libsvm_a9a" if cfg["task"] == "a9a" else "mnist")
    if cfg["task"] == "a9a":
        client_data, test, data_info = load_a9a(data_root, clients, cfg.get("alpha", 0.05))
        grad_fn = lambda p, x, y: logistic_loss_gradient(p, x, y, cfg.get("alpha", 0.05))
        acc_fn = logistic_accuracy
    elif cfg["task"] == "mnist":
        client_data, test, data_info = load_mnist(data_root, clients)
        grad_fn = lambda p, x, y: nn_loss_gradient(p, x, y, cfg.get("hidden", 32), 10)
        acc_fn = lambda p, x, y: nn_accuracy(p, x, y, cfg.get("hidden", 32), 10)
    else:
        raise ValueError(cfg["task"])
    dimension = data_info["features"] if cfg["task"] == "a9a" else cfg["hidden"] * data_info["features"] + cfg["hidden"] + 10 * cfg["hidden"] + 10
    w = mixing_matrix(clients, cfg.get("topology", "ring"), cfg.get("edge_probability", 0.5), seed)
    x0 = np.tile(_initial_params(cfg["task"], data_info["features"], seed), (clients, 1))
    methods = cfg.get("methods", ["BEER"])
    algorithms = {name: _make_algorithm(name, x0, w, cfg, seed + 17 * i) for i, name in enumerate(methods)}
    initial_gradients = []
    for client in client_data:
        bx, by = client.batch(0, cfg["batch_size"])
        initial_gradients.append(grad_fn(x0[0], bx, by)[1])
    initial_gradients = np.asarray(initial_gradients)
    for alg in algorithms.values():
        if isinstance(alg, BEER):
            alg.initialize(initial_gradients)
    metrics = {name: {"round": [], "gradient_norm": [], "test_accuracy": [], "objective": [], "communication_bits": []} for name in methods}
    log_lines = [f"experiment={cfg.get('experiment_id')} seed={seed} clients={clients} topology={cfg.get('topology')} spectral_gap={spectral_gap(w):.8f}"]
    start_time = time.time()
    for round_id in range(int(cfg["rounds"])):
        batch_data = [client.batch(round_id, cfg["batch_size"]) for client in client_data]
        for name, alg in algorithms.items():
            grads = []
            losses = []
            for i, (bx, by) in enumerate(batch_data):
                # BEER's gradient tracker consumes the gradient at X^{t+1}.
                point = alg.x[i]
                if isinstance(alg, BEER):
                    point = point + cfg["gamma"] * ((w - np.eye(clients)) @ alg.h)[i] - cfg["lr"] * alg.v[i]
                loss, grad = grad_fn(point, bx, by)
                losses.append(loss)
                grads.append(grad)
            grads = np.asarray(grads)
            alg.step(grads)
            avg = alg.average
            # The paper reports a training gradient norm. Evaluate the global
            # minibatch gradient at the post-update average model, rather than
            # using test labels (which would leak evaluation data into a train metric).
            eval_grad = np.mean([grad_fn(avg, bx, by)[1] for bx, by in batch_data], axis=0)
            metrics[name]["round"].append(round_id + 1)
            metrics[name]["gradient_norm"].append(float(np.linalg.norm(eval_grad)))
            metrics[name]["test_accuracy"].append(float(acc_fn(avg, test.features, test.labels)))
            metrics[name]["objective"].append(float(np.mean(losses)))
            metrics[name]["communication_bits"].append(int(alg.bits))
            log_lines.append(f"round={round_id+1} method={name} gradient_norm={metrics[name]['gradient_norm'][-1]:.8g} accuracy={metrics[name]['test_accuracy'][-1]:.6f} bits={alg.bits}")
    elapsed = time.time() - start_time
    out = Path(output)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    (out / "resolved_config.json").write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload = {"experiment_id": cfg.get("experiment_id"), "paper_id": "2201.13320", "data": data_info, "topology": cfg.get("topology"), "mixing_matrix": w.tolist(), "spectral_gap": spectral_gap(w), "elapsed_seconds": elapsed, "metrics": metrics}
    (out / "metrics.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out / "resource.json").write_text(json.dumps({"platform": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(), "elapsed_seconds": elapsed}, indent=2) + "\n", encoding="utf-8")
    (out / "run.log").write_text("\n".join(log_lines) + f"\nelapsed_seconds={elapsed:.6f}\n", encoding="utf-8")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        for field, ylabel, filename in [("gradient_norm", "training gradient norm", "gradient_norm.png"), ("test_accuracy", "test accuracy", "test_accuracy.png")]:
            fig, ax = plt.subplots(figsize=(7, 4))
            for name, values in metrics.items():
                ax.plot(values["round"], values[field], label=name)
            ax.set_xlabel("communication rounds")
            ax.set_ylabel(ylabel)
            ax.grid(alpha=0.25)
            ax.legend()
            fig.tight_layout()
            fig.savefig(out / "figures" / filename, dpi=140)
            plt.close(fig)
    except ImportError:
        # A textual SVG remains a valid figure artifact if plotting is unavailable.
        for filename in ("gradient_norm.svg", "test_accuracy.svg"):
            (out / "figures" / filename).write_text("<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360'><text x='20' y='40'>Plot dependencies unavailable</text></svg>\n", encoding="utf-8")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a BEER paper experiment")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--rounds", type=int, default=None)
    parser.add_argument("--clients", type=int, default=None)
    args = parser.parse_args(argv)
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    output = args.output or str(Path("results/formal") / cfg["experiment_id"])
    run_experiment(cfg, output, args.rounds, args.clients)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
