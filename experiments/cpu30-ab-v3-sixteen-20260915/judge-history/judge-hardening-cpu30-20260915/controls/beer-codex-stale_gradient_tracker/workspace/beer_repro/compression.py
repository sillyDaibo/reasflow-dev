"""Compression operators used by BEER and CHOCO-SGD."""

from __future__ import annotations

import math
import numpy as np


def identity(x: np.ndarray, param=None, rng=None) -> np.ndarray:
    return np.asarray(x, dtype=float).copy()


def top_k(x: np.ndarray, k: int, rng=None) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if k <= 0:
        return np.zeros_like(x)
    if k >= x.size:
        return x.copy()
    out = np.zeros_like(x)
    idx = np.argpartition(np.abs(x), -k)[-k:]
    out[idx] = x[idx]
    return out


def random_k(x: np.ndarray, k: int, rng=None) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if k <= 0:
        return np.zeros_like(x)
    if k >= x.size:
        return x.copy()
    rng = np.random.default_rng() if rng is None else rng
    idx = rng.choice(x.size, size=k, replace=False)
    out = np.zeros_like(x)
    out[idx] = x[idx] * (x.size / k)
    return out


def gsgd(x: np.ndarray, bits: int, rng=None) -> np.ndarray:
    """Biased norm quantizer gsgd_b from Alistarh et al. (2017).

    The random threshold is Gaussian as in the authors' implementation. The
    returned vector is intentionally biased; this is the compressor used in
    the paper's Figures 1--3.
    """
    x = np.asarray(x, dtype=float)
    if bits <= 0 or not np.any(x):
        return np.zeros_like(x)
    rng = np.random.default_rng() if rng is None else rng
    norm = np.linalg.norm(x)
    levels = 2.0 ** (bits - 1)
    delta = math.sqrt(x.size) / levels
    tau = 1.0 + delta if delta > 1.0 else 1.0 + delta * delta
    noisy = levels * np.abs(x) / norm + rng.normal(size=x.shape)
    return np.sign(x) * np.floor(np.maximum(noisy, 0.0)) * (norm / levels / tau)


def compress(x: np.ndarray, kind: str = "identity", param=None, rng=None) -> np.ndarray:
    kind = kind.lower()
    if kind in ("identity", "none", "uncompressed"):
        return identity(x, param, rng)
    if kind in ("gsgd", "gsgd_b"):
        return gsgd(x, int(param), rng)
    if kind in ("top", "top_k"):
        return top_k(x, int(param), rng)
    if kind in ("random", "random_k"):
        return random_k(x, int(param), rng)
    raise ValueError(f"unknown compressor: {kind}")


def compressor_bits(kind: str, param, dimension: int) -> int:
    """Approximate payload bits per directed message, matching paper plots."""
    kind = kind.lower()
    if kind in ("identity", "none", "uncompressed"):
        return int(32 * dimension)
    if kind in ("gsgd", "gsgd_b"):
        # one sign and b-bit level per coordinate; norm is an extra scalar
        return int(dimension * (int(param) + 1) + 32)
    if kind in ("top", "top_k", "random", "random_k"):
        k = min(int(param), dimension)
        return int(k * 32 + k * math.ceil(math.log2(max(dimension, 2))) + 32)
    raise ValueError(f"unknown compressor: {kind}")
