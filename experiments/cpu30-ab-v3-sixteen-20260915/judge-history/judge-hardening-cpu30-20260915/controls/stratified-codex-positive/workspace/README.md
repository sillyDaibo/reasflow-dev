# A Distributed Method for Fitting Laplacian Regularized Stratified Models

This repository is a reproducible implementation and CPU evaluation of
Jonathan Tuck, Shane Barratt, and Stephen Boyd, “A Distributed Method for
Fitting Laplacian Regularized Stratified Models,” arXiv:1904.12017 (2019),
later published in JMLR. The paper objective is

```
sum_k (local_loss_k(theta_k) + local_regularizer(theta_k))
    + 1/2 sum_(i,j) W_ij ||theta_i - theta_j||_2^2.
```

The solver in `strat_models/solvers.py` is the paper's three-block ADMM:
local loss proximal updates are independent across strata, local regularizer
updates are independent, and the consensus update solves
`(L + 2 rho I) z = rho (theta + u + v + w)`. `strat_models/graph.py` contains
weighted NetworkX conversion and a matrix-free Cartesian product operator so
the 3,494,400-node Chicago graph is represented without materializing its
37-million-entry Laplacian.

## Installation

Use Python 3.10 or newer and install the pinned dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The four datasets are read from the preinstalled read-only assets listed in
`../input/DATASETS.json`. Set `STRAT_MODELS_ASSETS` to another directory with
the same dataset layout when reproducing elsewhere. Generated extraction and
intermediate data are placed in `.run-data/` and are not part of Git.

## Tests and minimal end-to-end run

Run the algorithm and graph tests with:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
```

A small real-data end-to-end check (mesothelioma, five ADMM iterations) is:

```bash
PYTHONPATH=. .venv/bin/python scripts/run_experiment.py mesothelioma --maxiter 5
```

## Formal experiments

Each formal run records an actual resolved configuration, data provenance, JSON
metrics, a PNG figure, and a captured stdout log under
`results/formal/<experiment_id>/`. The defaults use the paper's data splits,
graph weights, and baselines. To capture a fresh log, pipe stdout through
`tee results/formal/<experiment_id>/run.log` as in the checked-in evidence.

```bash
PYTHONPATH=. .venv/bin/python scripts/run_experiment.py mesothelioma
PYTHONPATH=. .venv/bin/python scripts/run_experiment.py houses
PYTHONPATH=. .venv/bin/python scripts/run_experiment.py senate
PYTHONPATH=. .venv/bin/python scripts/run_experiment.py chicago
```

`--maxiter` is available for timing checks; formal evidence was produced with
the values in `configs/`. To run all four sequentially:

```bash
PYTHONPATH=. .venv/bin/python scripts/run_experiment.py all
```

Experiment correspondence:

* `exp_001_mesothelioma`: 324 UCI patients, 90/10 random split, 46 engineered
  covariates plus intercept, sex-by-age graph, logistic loss, and separate and
  common logistic baselines. The glucose coefficient-by-age figure is saved.
* `exp_002_houses`: 21,596 filtered King County sales, 16,197/5,399 split,
  50x50 geographic bins, square loss, and a 50-tree random forest baseline.
* `exp_003_senate`: MEDSL statewide Senate winners through 2016, 639/68
  train/test elections, 50-state border graph (109 edges) times a 21-year
  path, Bernoulli loss, and separate/common baselines.
* `exp_004_chicago`: 2017/2018 Chicago records, all 20x20x52x7x24 cells
  including zero counts, Poisson loss, and the four 100-weight product-graph
  factors. The location/week/hour rate visualizations are combined in one PNG.

The `paper_reference` fields in each metrics file quote the corresponding
numbers in Tables 1–4. Results are not hand-tuned: seeds and all hyperparameters
are recorded in `resolved_config.json`, and convergence status/residuals are
recorded in the log output. Differences from the paper can arise from newer
dataset revisions, solver tolerances, and the paper's 2019 software stack.

## Repository structure

`strat_models/` is the reusable solver and graph implementation;
`experiments/common.py` contains deterministic loaders, preprocessing, model
comparisons, and plots; `scripts/run_experiment.py` is the formal entry point;
`configs/` stores the intended settings; `tests/` covers proximal operators,
ADMM behavior, and product-graph equivalence; and `results/formal/` contains
machine-readable evidence.

## Sources and citation

The reference implementation and examples were consulted from the authors'
repository at <https://github.com/cvxgrp/strat_models>, commit
`0108114afe1265262f345bf93a5bc147f6cb146c`. This implementation was rewritten
for current NumPy/SciPy APIs, replaces the reference's dense/torch local code
with numerically equivalent proximal updates, fixes empty-node handling, and
adds the matrix-free product-grid operator. Dataset URLs and checksums are
listed in the supplied asset `download_manifest.json` files. Cite the paper:

```bibtex
@article{tuck2019distributed,
  author  = {Jonathan Tuck and Shane Barratt and Stephen Boyd},
  title   = {A Distributed Method for Fitting Laplacian Regularized Stratified Models},
  journal = {Journal of Machine Learning Research},
  year    = {2021},
  note    = {arXiv:1904.12017}
}
```
