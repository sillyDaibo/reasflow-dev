# BEER reproduction

This repository reproduces the numerical claims in **BEER: Fast O(1/T) Rate for Decentralized Nonconvex Optimization with Communication Compression** (Zhao, Li, Li, Richtárik, Chi, NeurIPS 2022; arXiv:2201.13320). It contains a self-contained NumPy implementation of BEER and the comparison algorithms, real a9a and MNIST data readers, deterministic heterogeneous client partitions, formal experiment configurations, tests, and the recorded results under `results/formal/`.

## Installation

Use Python 3.10 or newer. Install the pinned runtime dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

The supplied datasets are read-only shared assets. No dataset is committed to this repository; set `BEER_A9A_ROOT` and `BEER_MNIST_ROOT` to the local dataset roots listed in `DATASETS.json` (or to your own downloaded copies) before running the real-data commands. Derived arrays belong in `.run-data/`.

## Project structure

`beer_repro/` implements compressors, mixing graphs, BEER/CHOCO-SGD/DSGD/D2 state machines, objectives, data loading, and the experiment runner. `configs/` contains the five paper-scale experiment configurations. `tests/` checks the BEER recursion, compression contracts, graph properties, client partitioning, and a small end-to-end run. `results/formal/<experiment_id>/` contains the resolved configuration, complete JSON metrics, a run log, and figures from the runs reported in `CLAIM_RESULTS.json`.

## Minimal end-to-end check

```bash
python3 run_experiment.py --config configs/exp_001_a9a_comparison.json --rounds 2 --clients 3 --output results/smoke
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Formal experiments

Run an individual experiment with its recorded configuration:

```bash
export BEER_A9A_ROOT=/path/to/libsvm_a9a
export BEER_MNIST_ROOT=/path/to/mnist
python3 run_experiment.py --config configs/exp_001_a9a_comparison.json
python3 run_experiment.py --config configs/exp_002_mnist_comparison.json
python3 run_experiment.py --config configs/exp_003_a9a_topology.json
python3 run_experiment.py --config configs/exp_004_a9a_compression.json
python3 run_experiment.py --config configs/exp_005_mnist_heterogeneity.json
```

The formal runs use ten clients (forty for the topology/ablation settings where stated), contiguous unshuffled partitions, the paper objectives, minibatch size 100, and fixed seeds. CPU execution is supported; `--rounds` and `--output` can be overridden for a fresh run. Each run writes `resolved_config.json`, `metrics.json`, `run.log`, `figures/gradient_norm.png`, `figures/test_accuracy.png`, and `resource.json`.

## Scientific scope and deviations

 BEER follows Algorithm 1: model and gradient trackers are maintained per client, both tracker differences are compressed before mixing, and the gradient difference uses the new and previous minibatch gradients. CHOCO-SGD, DSGD, and D² are implemented as genuine decentralized baselines with the same initialization, client batches, mixing matrix, and evaluation budget. The official repository uses a GPU/distributed PyTorch framework; this version uses a synchronous NumPy simulator so it is independently runnable on the CPU environment. The paper’s FDLA weights are represented by symmetric Metropolis weights on the requested topology; this preserves the paper’s symmetric doubly-stochastic mixing contract while making the construction explicit and reproducible. The supplied MNIST parquet mirror is decoded with PyArrow and partitioned by label (client `i` receives label `i`) as described in Section 5. For a9a, the official `sort=True` convention is reproduced by stable label sorting before contiguous client splits. Experiments are finite CPU runs, so they test the empirical trends rather than proving asymptotic rates.

## Sources and citation

The algorithmic reference is the authors’ repository at commit `ebd11e0effb6bef448bf7261dfb7601935edce98`, used only to cross-check update ordering and experiment conventions. Dataset sources and checksums are recorded in `.run-data/SOURCES.md` when data are prepared. Please cite:

```bibtex
@inproceedings{zhao2022beer,
  title={BEER: Fast O(1/T) Rate for Decentralized Nonconvex Optimization with Communication Compression},
  author={Zhao, Haoyu and Li, Boyue and Li, Zhize and Richt{\'a}rik, Peter and Chi, Yuejie},
  booktitle={Advances in Neural Information Processing Systems},
  volume={35}, year={2022}
}
```

## Limitations

Only the real-data numerical claims are evaluated here. The paper’s proofs are not re-derived in code, and CPU wall time is substantially longer than the original GPU implementation. Results are reported exactly as run, including any discrepancy from the paper’s plots.
