"""Federated Random Reshuffling and Local SGD simulations."""

from __future__ import annotations

import time
import numpy as np

from .algorithms import Trace
from .objectives import ElasticNetLogistic


def _client_objective(A, b, l1, l2, l2_in_prox):
    return ElasticNetLogistic(A, b, l1=l1, l2=l2, l2_in_prox=l2_in_prox)


class FedRR:
    def __init__(self, clients, epochs: int, step_size: float, seed: int = 0, l1: float = 0.0, l2: float = 0.0,
                 reshuffle: bool = True, l2_in_prox: bool = True, local_batch_size: int = 1,
                 decay_coefficient: float = 0.0, decay_power: float = 1.0):
        self.clients, self.epochs, self.step_size, self.seed = clients, int(epochs), float(step_size), int(seed)
        self.l1, self.l2, self.reshuffle, self.l2_in_prox = float(l1), float(l2), bool(reshuffle), bool(l2_in_prox)
        self.local_batch_size = max(1, int(local_batch_size))
        self.decay_coefficient, self.decay_power = float(decay_coefficient), float(decay_power)

    def run(self, x0=None):
        dim = self.clients[0][0].shape[1]
        x = np.zeros(dim) if x0 is None else np.array(x0, dtype=float, copy=True)
        rng = np.random.default_rng(self.seed)
        total_n = sum(A.shape[0] for A, _ in self.clients); M = len(self.clients)
        objective = ElasticNetLogistic(_vstack([A for A, _ in self.clients]), np.concatenate([b for _, b in self.clients]), l1=self.l1, l2=self.l2, l2_in_prox=self.l2_in_prox)
        tr = Trace("FedRR" if self.reshuffle else "FedSO", self.seed, [0], [0.0], [0], [objective.value(x)], 0.0)
        t0 = time.perf_counter(); prox_count = 0
        perms = [rng.permutation(A.shape[0]) for A, _ in self.clients]
        for epoch in range(self.epochs):
            if epoch and self.reshuffle:
                perms = [rng.permutation(A.shape[0]) for A, _ in self.clients]
            local_models = []
            step = 1.0 / (1.0 / self.step_size + self.decay_coefficient * max(0, epoch) ** self.decay_power)
            for (A, b), perm in zip(self.clients, perms):
                local = _client_objective(A, b, l1=0.0, l2=self.l2, l2_in_prox=self.l2_in_prox)
                z = x.copy()
                for start in range(0, len(perm), self.local_batch_size):
                    idx = perm[start:start + self.local_batch_size]
                    z -= step * local.gradient(z, idx, normalization=len(idx))
                local_models.append(z)
            x = np.mean(local_models, axis=0)
            # Algorithm 3 has prox_{gamma N/M R}; l2 is kept in R only here.
            if self.l2_in_prox:
                x = np.sign(x) * np.maximum(np.abs(x) - self.step_size * total_n / M * self.l1, 0.0)
                x /= 1.0 + self.step_size * total_n / M * self.l2
            prox_count += 1
            tr.iterations.append(epoch + 1); tr.epochs.append(epoch + 1); tr.prox_evaluations.append(prox_count); tr.objective.append(objective.value(x))
        tr.elapsed_seconds = time.perf_counter() - t0
        return x, tr


class LocalSGD:
    def __init__(self, clients, rounds: int, local_steps: int, step_size: float, seed: int = 0, l1: float = 0.0, l2: float = 0.0, l2_in_prox: bool = True, local_batch_size: int = 1, decay_coefficient: float = 0.0, decay_power: float = 1.0):
        self.clients, self.rounds, self.local_steps, self.step_size, self.seed = clients, int(rounds), int(local_steps), float(step_size), int(seed)
        self.l1, self.l2, self.l2_in_prox = float(l1), float(l2), bool(l2_in_prox)
        self.local_batch_size = max(1, int(local_batch_size))
        self.decay_coefficient, self.decay_power = float(decay_coefficient), float(decay_power)

    def run(self, x0=None):
        dim = self.clients[0][0].shape[1]
        x = np.zeros(dim) if x0 is None else np.array(x0, dtype=float, copy=True)
        rng = np.random.default_rng(self.seed)
        total_n = sum(A.shape[0] for A, _ in self.clients)
        objective = ElasticNetLogistic(_vstack([A for A, _ in self.clients]), np.concatenate([b for _, b in self.clients]), l1=self.l1, l2=self.l2, l2_in_prox=self.l2_in_prox)
        tr = Trace("LocalSGD", self.seed, [0], [0.0], [0], [objective.value(x)], 0.0)
        t0 = time.perf_counter(); prox_count = 0
        for r in range(self.rounds):
            locals_ = []
            step = 1.0 / (1.0 / self.step_size + self.decay_coefficient * max(0, r) ** self.decay_power)
            for A, b in self.clients:
                local = _client_objective(A, b, l1=0.0, l2=self.l2, l2_in_prox=self.l2_in_prox)
                z = x.copy(); perm = rng.permutation(A.shape[0])
                for start in range(0, self.local_steps, self.local_batch_size):
                    size = min(self.local_batch_size, self.local_steps - start)
                    idx = perm[np.arange(start, start + size) % len(perm)]
                    z -= step * local.gradient(z, idx, normalization=size)
                locals_.append(z)
            x = np.mean(locals_, axis=0)
            if self.l2_in_prox:
                x = np.sign(x) * np.maximum(np.abs(x) - self.step_size * self.l1, 0.0) / (1.0 + self.step_size * self.l2)
            prox_count += 1
            tr.iterations.append(r + 1); tr.epochs.append((r + 1) * self.local_steps * self.clients[0][0].shape[0] / total_n); tr.prox_evaluations.append(prox_count); tr.objective.append(objective.value(x))
        tr.elapsed_seconds = time.perf_counter() - t0
        return x, tr


def _vstack(mats):
    from scipy.sparse import vstack
    return vstack(mats, format="csr")
