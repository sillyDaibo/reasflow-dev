# Proximal and Federated Random Reshuffling

This repository reproduces the empirical experiments in **Proximal and Federated Random Reshuffling** by Konstantin Mishchenko, Ahmed Khaled, and Peter Richtarik (arXiv:2102.06704, 2021).

The implementation covers the methods needed by the paper's experiments:

- ProxRR and ProxSO (one proximal evaluation per epoch),
- the per-iteration proximal RR heuristic,
- proximal SGD,
- FedRR/FedSO and Local SGD baselines, and
- importance-resampled ProxRR.

## Project Structure

`rr_prox_fed/` contains the objective, single-machine algorithms, federated algorithms, and dataset helpers. `run_experiment.py` is the formal entry point; `configs/` stores the declared experiment settings; `tests/` contains core behavior tests; and `results/formal/` stores committed metrics, histories, logs, and figures.

The code uses the official repository at commit `7a72e2bb38794897e729d1a474b59e671f51701d` as a reference. The optimization core was rewritten into a small, deterministic package; the official libsvm files are used only as read-only source data and are copied to `.run-data/datasets/` by the setup commands below.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

The formal runner needs the public `a1a`, `a9a`, and `mushrooms` libsvm datasets. In this task checkout they can be copied from the permitted official snapshot:

```bash
mkdir -p .run-data/datasets
cp ../runtime/official_code/datasets/{a1a,a9a,mushrooms} .run-data/datasets/
```

For another checkout, place equivalent libsvm files in `.run-data/datasets/` or pass `--data-dir` to the runner. Dataset provenance and SHA256 checksums are written to each formal result directory.

## Tests and a minimal end-to-end run

```bash
PYTHONPATH=. pytest -q
PYTHONPATH=. python run_experiment.py --experiment smoke --output-dir results/smoke
```

The smoke run uses a deterministic synthetic objective only for checking the entry point. It is not used as paper evidence.

## Formal experiments

Run both paper experiments (the defaults use the paper's minibatch size one and theoretical step-size rules):

```bash
PYTHONPATH=. python run_experiment.py --experiment figure1 --data-dir .run-data/datasets --output-dir results/formal/figure1_a9a
PYTHONPATH=. python run_experiment.py --experiment figure2 --data-dir .run-data/datasets --output-dir results/formal/figure2_mushrooms
PYTHONPATH=. python run_experiment.py --experiment importance --data-dir .run-data/datasets --output-dir results/formal/importance_a1a
```

`figure1` writes `history.csv`, `metrics.json`, `config.json`, `machine.json`, `run.log`, and `figure1.png`. `figure2` writes the analogous files plus `communication_rounds.png` and `data_passes.png`. Every result records the seed, exact command configuration, elapsed time, and dataset checksums. The reference optimum used for objective gaps is computed by a deterministic full-gradient proximal solver and is recorded in `metrics.json`.

## Mapping to the paper

`figure1` implements the elastic-net logistic problem (14) on `a1a`, with SGD, ProxRR, and the paper's “RR (heuristic)” comparison. The plot reports objective gap versus stochastic iterations and proximal evaluations.

`figure2` implements Algorithm 3 on `mushrooms`, partitioned into equal client shards. It compares FedRR with Local SGD using a full local pass and a five-times shorter local budget, reporting objective gap versus communication rounds and processed data passes. Following the official federated notebook, these client passes use minibatches of eight examples.

`importance` compares standard ProxRR with the paper's expanded finite-sum importance construction (`n_i = ceil(L_i / mean(L_i))`) on the same real `a1a` task.

## Limitations and deviations

The PDF gives exact algorithmic updates but leaves some plotting and partition details implicit. We use a fixed seed set, deterministic contiguous client shards, and the paper's stated five-fold partial Local-SGD budget. The supplied official notebook uses `a9a` for its federated example while the paper's supplementary text specifies `mushrooms`; this reproduction follows the paper text and uses `mushrooms` for Figure 2. Ray is not required: Local SGD is simulated sequentially, with the same local updates and aggregation, so the numerical method is unchanged.

## Citation

```bibtex
@article{mishchenko2021proximal,
  title={Proximal and Federated Random Reshuffling},
  author={Mishchenko, Konstantin and Khaled, Ahmed and Richtarik, Peter},
  journal={arXiv preprint arXiv:2102.06704},
  year={2021}
}
```
