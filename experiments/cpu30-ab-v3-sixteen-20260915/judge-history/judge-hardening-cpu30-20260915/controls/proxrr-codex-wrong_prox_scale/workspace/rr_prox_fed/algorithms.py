"""Single-machine proximal stochastic methods."""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict
import numpy as np

from .objectives import ElasticNetLogistic


@dataclass
class Trace:
    method: str
    seed: int
    iterations: list
    epochs: list
    prox_evaluations: list
    objective: list
    elapsed_seconds: float

    def as_dict(self):
        return asdict(self)


def _trace(method, seed, objective, x0):
    return Trace(method, seed, [0], [0.0], [0], [objective.value(x0)], 0.0)


class ProxRR:
    def __init__(self, objective: ElasticNetLogistic, epochs: int, step_size: float | None = None,
                 seed: int = 0, batch_size: int = 1, reshuffle: bool = True,
                 prox_every_iteration: bool = False, importance_sampling: bool = False,
                 decay_coefficient: float = 0.0, decay_power: float = 1.0, epoch_start_decay: int = 0,
                 record_every: int = 1):
        self.objective, self.epochs, self.seed = objective, int(epochs), int(seed)
        self.batch_size, self.reshuffle = int(batch_size), bool(reshuffle)
        self.prox_every_iteration, self.importance_sampling = bool(prox_every_iteration), bool(importance_sampling)
        self.decay_coefficient, self.decay_power, self.epoch_start_decay = float(decay_coefficient), float(decay_power), int(epoch_start_decay)
        self.record_every = max(1, int(record_every))
        self.step_size = float(step_size) if step_size is not None else 1.0 / objective.batch_smoothness(batch_size)

    def run(self, x0=None):
        rng = np.random.default_rng(self.seed)
        x = np.zeros(self.objective.dim) if x0 is None else np.array(x0, dtype=float, copy=True)
        tr = _trace(self.name, self.seed, self.objective, x)
        t0 = time.perf_counter(); prox_count = 0
        if self.importance_sampling:
            row_sq = np.asarray(self.objective.A.multiply(self.objective.A).sum(axis=1)).ravel()
            mean = max(row_sq.mean(), 1e-12)
            copies = np.maximum(1, np.ceil(np.sqrt(row_sq / mean)).astype(int))
            expanded = np.repeat(np.arange(self.objective.n), copies)
        else:
            expanded = np.arange(self.objective.n)
        permutation = rng.permutation(expanded)
        steps_per_epoch = int(np.ceil(len(expanded) / self.batch_size))
        for epoch in range(self.epochs):
            if epoch > 0 and self.reshuffle:
                permutation = rng.permutation(expanded)
            step = 1.0 / (1.0 / self.step_size + self.decay_coefficient * steps_per_epoch * max(0, epoch - self.epoch_start_decay) ** self.decay_power)
            for start in range(0, len(permutation), self.batch_size):
                idx = permutation[start:start + self.batch_size]
                # Copies are normalized as the equivalent expanded finite sum.
                norm = len(permutation) / steps_per_epoch if len(idx) < self.batch_size else len(idx)
                weights = (1.0 / copies[idx]) if self.importance_sampling else None
                grad = self.objective.gradient(x, idx, normalization=norm, sample_weights=weights)
                x -= step * grad
                if self.prox_every_iteration:
                    x = self.objective.regularizer(x, step)
                    prox_count += 1
                iteration = epoch * steps_per_epoch + start // self.batch_size + 1
                if iteration % self.record_every == 0 or start + len(idx) == len(permutation):
                    tr.iterations.append(iteration)
                    tr.epochs.append(epoch + (start + len(idx)) / len(permutation))
                    tr.prox_evaluations.append(prox_count)
                    tr.objective.append(self.objective.value(x))
            if not self.prox_every_iteration:
                x = self.objective.regularizer(x, step)
                prox_count += 1
                # The epoch-end proximal point is the algorithm iterate.
                if tr.iterations[-1] == (epoch + 1) * steps_per_epoch:
                    tr.prox_evaluations[-1] = prox_count
                    tr.objective[-1] = self.objective.value(x)
        tr.elapsed_seconds = time.perf_counter() - t0
        return x, tr

    @property
    def name(self):
        if self.prox_every_iteration:
            return "RR_heuristic"
        if self.importance_sampling:
            return "ProxRR_importance"
        return "ProxRR" if self.reshuffle else "ProxSO"


class ProxSGD:
    def __init__(self, objective, iterations: int, step_size: float | None = None, seed: int = 0, batch_size: int = 1,
                 decay_coefficient: float = 0.0, decay_power: float = 1.0, iteration_start_decay: int = 0):
        self.objective, self.iterations, self.seed = objective, int(iterations), int(seed)
        self.batch_size = int(batch_size)
        self.step_size = float(step_size) if step_size is not None else 1.0 / objective.batch_smoothness(batch_size)
        self.decay_coefficient, self.decay_power, self.iteration_start_decay = float(decay_coefficient), float(decay_power), int(iteration_start_decay)

    def run(self, x0=None):
        rng = np.random.default_rng(self.seed)
        x = np.zeros(self.objective.dim) if x0 is None else np.array(x0, dtype=float, copy=True)
        tr = _trace("ProxSGD", self.seed, self.objective, x)
        t0 = time.perf_counter()
        for it in range(self.iterations):
            idx = rng.integers(0, self.objective.n, size=self.batch_size)
            step = 1.0 / (1.0 / self.step_size + self.decay_coefficient * max(0, it - self.iteration_start_decay) ** self.decay_power)
            x -= step * self.objective.gradient(x, idx)
            x = self.objective.regularizer(x, step)
            tr.iterations.append(it + 1); tr.epochs.append((it + 1) * self.batch_size / self.objective.n)
            tr.prox_evaluations.append(it + 1); tr.objective.append(self.objective.value(x))
        tr.elapsed_seconds = time.perf_counter() - t0
        return x, tr


def run_reference_solver(objective, x0=None, iterations=4000, step_size=None):
    """Full-gradient proximal descent used only to define a reproducible f* reference."""
    x = np.zeros(objective.dim) if x0 is None else np.array(x0, dtype=float, copy=True)
    step_size = 1.0 / objective.smoothness if step_size is None else float(step_size)
    best = objective.value(x)
    for _ in range(int(iterations)):
        x -= step_size * objective.gradient(x)
        x = objective.regularizer(x, step_size)
        best = min(best, objective.value(x))
    return x, float(best)
