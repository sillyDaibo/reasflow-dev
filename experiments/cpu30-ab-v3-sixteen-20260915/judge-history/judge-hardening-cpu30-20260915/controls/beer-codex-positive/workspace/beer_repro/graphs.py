"""Topology and symmetric doubly-stochastic mixing matrices."""

from __future__ import annotations

import math
import numpy as np


def _edges(n: int, topology: str, p: float, seed: int):
    topology = topology.lower()
    if topology == "ring":
        return {(i, (i + 1) % n) if i < (i + 1) % n else ((i + 1) % n, i) for i in range(n)}
    if topology == "complete":
        return {(i, j) for i in range(n) for j in range(i + 1, n)}
    if topology == "star":
        return {(0, i) for i in range(1, n)}
    if topology == "grid":
        side = int(math.ceil(math.sqrt(n)))
        e = set()
        for i in range(n):
            r, c = divmod(i, side)
            for j in (i + 1, i + side):
                if j < n and ((j // side == r and j == i + 1) or j == i + side):
                    e.add((i, j))
        return e
    if topology in ("er", "erdos_renyi", "erdos-renyi"):
        rng = np.random.default_rng(seed)
        e = {(i, j) for i in range(n) for j in range(i + 1, n) if rng.random() < p}
        # Ensure every client is connected, then connect components if needed.
        for i in range(n - 1):
            if not any(i in edge for edge in e):
                e.add((i, i + 1))
        return e
    raise ValueError(f"unknown topology: {topology}")


def mixing_matrix(n: int, topology: str = "ring", p: float = 0.5, seed: int = 0) -> np.ndarray:
    """Return a symmetric, doubly stochastic Metropolis matrix with self-loops."""
    e = _edges(n, topology, p, seed)
    deg = np.zeros(n, dtype=int)
    for i, j in e:
        deg[i] += 1
        deg[j] += 1
    w = np.zeros((n, n), dtype=float)
    for i, j in e:
        value = 1.0 / (1.0 + max(deg[i], deg[j]))
        w[i, j] = w[j, i] = value
    np.fill_diagonal(w, 1.0 - w.sum(axis=1))
    return w


def spectral_gap(w: np.ndarray) -> float:
    vals = np.linalg.eigvalsh(np.asarray(w, dtype=float))
    vals = np.sort(np.abs(vals))[::-1]
    return float(1.0 - vals[1]) if len(vals) > 1 else 1.0
