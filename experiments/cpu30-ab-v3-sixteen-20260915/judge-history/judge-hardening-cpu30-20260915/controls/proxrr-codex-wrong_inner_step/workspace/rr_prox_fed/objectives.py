"""Sparse logistic ERM and the elastic-net proximal map."""

from __future__ import annotations

import numpy as np
from scipy.special import expit
from scipy.sparse import issparse
from scipy.sparse.linalg import svds


class ProximalOperator:
    def __init__(self, l1: float = 0.0, l2: float = 0.0):
        if l1 < 0 or l2 < 0:
            raise ValueError("regularization coefficients must be non-negative")
        self.l1, self.l2 = float(l1), float(l2)

    def value(self, x):
        return self.l1 * float(np.linalg.norm(x, 1)) + 0.5 * self.l2 * float(np.dot(x, x))

    def __call__(self, x, step: float):
        if step < 0:
            raise ValueError("proximal step must be non-negative")
        z = np.sign(x) * np.maximum(np.abs(x) - step * self.l1, 0.0)
        return z / (1.0 + step * self.l2)


class ElasticNetLogistic:
    """Objective (14), with sparse sample storage and exact minibatch gradients."""

    def __init__(self, A, b, l1: float = 0.0, l2: float = 0.0, l2_in_prox: bool = True):
        if A.shape[0] != len(b):
            raise ValueError("A and b have incompatible sizes")
        self.A = A.tocsr() if issparse(A) else np.asarray(A, dtype=float)
        self.b = np.asarray(b, dtype=float)
        self.n, self.dim = self.A.shape
        self.l1, self.l2, self.l2_in_prox = float(l1), float(l2), bool(l2_in_prox)
        self.regularizer = ProximalOperator(l1, l2 if self.l2_in_prox else 0.0)
        self._smoothness = None

    def value(self, x):
        z = np.asarray(self.A @ x).ravel()
        # log(1 + exp(z)) - b*z is stable for both label conventions.
        smooth = float(np.mean(np.logaddexp(0.0, z) - self.b * z))
        return smooth + self.l1 * float(np.linalg.norm(x, 1)) + 0.5 * self.l2 * float(np.dot(x, x))

    def smooth_value(self, x):
        z = np.asarray(self.A @ x).ravel()
        return float(np.mean(np.logaddexp(0.0, z) - self.b * z))

    def gradient(self, x, idx=None, normalization=None, include_l2: bool | None = None, sample_weights=None):
        if idx is None:
            rows, labels = self.A, self.b
            normalization = self.n if normalization is None else normalization
        else:
            idx = np.asarray(idx, dtype=int)
            rows, labels = self.A[idx], self.b[idx]
            normalization = len(idx) if normalization is None else normalization
        z = np.asarray(rows @ x).ravel()
        residual = expit(z) - labels
        if sample_weights is not None:
            residual = residual * np.asarray(sample_weights)
        grad = np.asarray(rows.T @ residual).ravel() / float(normalization)
        if include_l2 is None:
            include_l2 = not self.l2_in_prox
        if include_l2:
            grad = grad + self.l2 * x
        return grad

    def batch_smoothness(self, batch_size: int = 1):
        batch_size = max(1, int(batch_size))
        L = self.smoothness
        row_sq = np.asarray(self.A.multiply(self.A).sum(axis=1)).ravel()
        Lmax = 0.25 * float(row_sq.max())
        return self.n / max(1, self.n - 1) * (1 - 1 / batch_size) * L + (self.n / batch_size - 1) / max(1, self.n - 1) * Lmax

    @property
    def smoothness(self):
        if self._smoothness is None:
            if min(self.A.shape) <= 1:
                smax = float(np.linalg.norm(self.A.toarray() if issparse(self.A) else self.A))
            else:
                smax = float(svds(self.A, k=1, return_singular_vectors=False, random_state=0)[0])
            self._smoothness = 0.25 * smax * smax / self.n + (0.0 if self.l2_in_prox else self.l2)
        return self._smoothness

    def clone(self, *, l1=None, l2=None):
        return ElasticNetLogistic(self.A, self.b, self.l1 if l1 is None else l1,
                                  self.l2 if l2 is None else l2, self.l2_in_prox)
