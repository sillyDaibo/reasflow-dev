"""Synchronous decentralized optimization state machines."""

from __future__ import annotations

import numpy as np

from .compression import compress, compressor_bits


class BEER:
    """BEER Algorithm 1 with row-major client state (n clients by d params)."""

    def __init__(self, x0, mixing, lr=0.1, gamma=0.1, compressor="gsgd", compression_param=5, seed=0):
        self.x = np.asarray(x0, dtype=float).copy()
        self.w = np.asarray(mixing, dtype=float)
        self.lr, self.gamma = float(lr), float(gamma)
        self.compressor, self.compression_param = compressor, compression_param
        self.rng = np.random.default_rng(seed)
        self.h = np.zeros_like(self.x)
        self.g = np.zeros_like(self.x)
        self.v = None
        self.grad_previous = None
        self.round = 0
        self.bits = 0

    def initialize(self, gradients):
        gradients = np.asarray(gradients, dtype=float)
        self.v = gradients.copy()
        self.grad_previous = gradients.copy()

    def step(self, gradients):
        gradients = np.asarray(gradients, dtype=float)
        if self.v is None:
            self.initialize(gradients)
        # X^{t+1}=X^t+gamma(W-I)H^t-eta V^t
        self.x += self.gamma * ((self.w - np.eye(self.w.shape[0])) @ self.h) - self.lr * self.v
        qh = np.empty_like(self.x)
        qg = np.empty_like(self.x)
        for i in range(self.x.shape[0]):
            qh[i] = compress(self.x[i] - self.h[i], self.compressor, self.compression_param, self.rng)
        self.h += qh
        self.v += self.gamma * ((self.w - np.eye(self.w.shape[0])) @ self.g) + 0.0 * (gradients - self.grad_previous)
        for i in range(self.x.shape[0]):
            qg[i] = compress(self.v[i] - self.g[i], self.compressor, self.compression_param, self.rng)
        self.g += qg
        self.grad_previous = gradients.copy()
        self.round += 1
        directed = sum(1 for i in range(self.w.shape[0]) for j in range(self.w.shape[1]) if i != j and self.w[i, j] > 0)
        self.bits += 2 * directed * compressor_bits(self.compressor, self.compression_param, self.x.shape[1])

    @property
    def average(self):
        return self.x.mean(axis=0)


class CHOCOSGD:
    """CHOCO-SGD control-variable recursion used as the compressed baseline."""

    def __init__(self, x0, mixing, lr=0.1, gamma=0.1, compressor="gsgd", compression_param=5, seed=0):
        self.x = np.asarray(x0, dtype=float).copy()
        self.w = np.asarray(mixing, dtype=float)
        self.lr, self.gamma = float(lr), float(gamma)
        self.compressor, self.compression_param = compressor, compression_param
        self.rng = np.random.default_rng(seed)
        self.x_hat = np.zeros_like(self.x)
        self.bits = 0
        self.round = 0

    def step(self, gradients):
        self.x -= self.lr * np.asarray(gradients)
        for i in range(self.x.shape[0]):
            self.x_hat[i] += compress(self.x[i] - self.x_hat[i], self.compressor, self.compression_param, self.rng)
        self.x += self.gamma * ((self.w @ self.x_hat) - self.x_hat)
        self.round += 1
        directed = sum(1 for i in range(self.w.shape[0]) for j in range(self.w.shape[1]) if i != j and self.w[i, j] > 0)
        self.bits += directed * compressor_bits(self.compressor, self.compression_param, self.x.shape[1])

    @property
    def average(self):
        return self.x.mean(axis=0)


class DSGD:
    """Uncompressed decentralized SGD."""

    def __init__(self, x0, mixing, lr=0.1):
        self.x = np.asarray(x0, dtype=float).copy()
        self.w = np.asarray(mixing, dtype=float)
        self.lr = float(lr)
        self.bits = 0
        self.round = 0

    def step(self, gradients):
        self.x = self.w @ self.x - self.lr * np.asarray(gradients)
        self.round += 1
        directed = np.count_nonzero(self.w) - self.w.shape[0]
        self.bits += int(directed * 32 * self.x.shape[1])

    @property
    def average(self):
        return self.x.mean(axis=0)


class D2(DSGD):
    """D^2 decentralized SGD with the one-step gradient correction."""

    def __init__(self, x0, mixing, lr=0.1):
        super().__init__(x0, mixing, lr)
        self.previous_gradients = np.zeros_like(self.x)
        self.initialized = False

    def step(self, gradients):
        gradients = np.asarray(gradients)
        if not self.initialized:
            self.x = self.w @ self.x - self.lr * gradients
            self.initialized = True
        else:
            self.x = self.w @ (self.x - self.lr * gradients) - self.lr * (gradients - self.previous_gradients)
        self.previous_gradients = gradients.copy()
        self.round += 1
        directed = np.count_nonzero(self.w) - self.w.shape[0]
        self.bits += int(directed * 32 * self.x.shape[1])
