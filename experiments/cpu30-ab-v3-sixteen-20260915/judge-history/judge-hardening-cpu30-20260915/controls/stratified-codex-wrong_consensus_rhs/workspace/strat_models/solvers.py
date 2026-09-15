"""ADMM solver and proximal operators from the stratified-model paper."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from scipy.special import expit
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, cg

from .graph import GraphOperator


@dataclass
class ADMMInfo:
    iterations: int
    converged: bool
    elapsed_seconds: float
    primal_residual: float
    dual_residual: float


def _solve_system(graph: GraphOperator, rho: float, rhs: np.ndarray, x0: np.ndarray, max_cg_iterations: int) -> np.ndarray:
    if graph.matrix is not None and graph.n_nodes <= 10000:
        # Sparse CG is considerably faster for the small product graphs.
        A = graph.matrix + 2.0 * rho * sparse.eye(graph.n_nodes, format="csr")
    else:
        A = graph.system(rho)
    try:
        result, info = cg(A, rhs, x0=x0, maxiter=max_cg_iterations, rtol=1e-8, atol=0.0)
    except TypeError:  # scipy < 1.12
        result, info = cg(A, rhs, x0=x0, maxiter=max_cg_iterations, tol=1e-8)
    return result if info == 0 else result


def fit_admm(
    graph: GraphOperator,
    shape: tuple[int, ...],
    loss_prox,
    regularizer_prox,
    *,
    maxiter: int = 200,
    abs_tol: float = 1e-5,
    rel_tol: float = 1e-5,
    rho: float = 1.0,
    max_cg_iterations: int = 50,
    verbose: bool = False,
    initial: dict | None = None,
):
    """Solve min sum_k l_k(theta_k)+r(v_k)+1/2 theta^T L theta.

    ``loss_prox`` and ``regularizer_prox`` operate on arrays of shape
    ``(K, *shape)`` and implement prox_{t f}. The returned parameters are the
    consensus variables ``z`` and local copies, together with convergence info.
    """
    k = graph.n_nodes
    p = int(np.prod(shape))
    init = initial or {}
    theta = np.array(init.get("theta", np.zeros((k, p))), dtype=float).reshape(k, p)
    v = np.array(init.get("v", theta), dtype=float).reshape(k, p)
    z = np.array(init.get("z", theta), dtype=float).reshape(k, p)
    u = np.array(init.get("u", np.zeros_like(theta)), dtype=float).reshape(k, p)
    w = np.array(init.get("w", np.zeros_like(theta)), dtype=float).reshape(k, p)
    start = time.perf_counter()
    converged = False
    primal = dual = np.inf
    scale = np.sqrt(2 * k * p)
    for iteration in range(1, maxiter + 1):
        theta = np.asarray(loss_prox(1.0 / rho, z - u, theta), dtype=float).reshape(k, p)
        v = np.asarray(regularizer_prox(1.0 / rho, z - w, v), dtype=float).reshape(k, p)
        rhs = 0.5 * rho * (theta + u + v + w)
        new_z = np.empty_like(z)
        for j in range(p):
            new_z[:, j] = _solve_system(graph, rho, rhs[:, j], z[:, j], max_cg_iterations)
        dual = rho * np.linalg.norm(new_z - z)
        z = new_z
        r1, r2 = theta - z, v - z
        u += r1
        w += r2
        primal = np.linalg.norm(np.concatenate((r1, r2)))
        eps_pri = scale * abs_tol + rel_tol * max(np.linalg.norm(theta), np.linalg.norm(v), np.linalg.norm(z))
        eps_dual = scale * abs_tol + rel_tol * rho * np.linalg.norm(np.concatenate((u, w)))
        if verbose and (iteration == 1 or iteration % 10 == 0):
            print(f"iter={iteration:4d} primal={primal:.3e} dual={dual:.3e} eps=({eps_pri:.3e},{eps_dual:.3e})")
        if primal <= eps_pri and dual <= eps_dual:
            converged = True
            break
    info = ADMMInfo(iteration, converged, time.perf_counter() - start, float(primal), float(dual))
    return z.reshape((k,) + shape), {"theta": theta.reshape((k,) + shape), "v": v.reshape((k,) + shape), "u": u.reshape((k,) + shape), "w": w.reshape((k,) + shape)}, info


def ridge_prox(t, nu, warm, sufficient_stats):
    """Prox for sum_i (x_i theta-y_i)^2 plus optional ridge handled separately."""
    xtx, xty = sufficient_stats
    out = np.empty_like(nu)
    for i in range(nu.shape[0]):
        rhs = 2.0 * np.asarray(xty[i]).reshape(-1) + nu[i] / t
        out[i] = np.linalg.solve(2.0 * xtx[i] + np.eye(xtx.shape[1]) / t, rhs)
    return out


def ridge_regularizer_prox(t, nu, warm, lambd=0.0, intercept_index=None):
    if lambd == 0:
        return nu
    out = nu / (1.0 + t * lambd)
    if intercept_index is not None:
        out[..., intercept_index] = nu[..., intercept_index]
    return out


def poisson_prox(t, nu, warm, counts, min_theta=1e-5):
    n = counts[..., 0]
    s = counts[..., 1]
    b = t * n - nu[..., 0]
    theta = (-b + np.sqrt(np.maximum(b * b + 4 * t * s, 0.0))) / 2.0
    return np.maximum(theta, min_theta)[..., None]


def bernoulli_prox(t, nu, warm, counts, min_theta=1e-5, max_theta=1 - 1e-5):
    """Newton solve for prox of -S log p -(N-S) log(1-p)."""
    n = counts[..., 0]
    s = counts[..., 1]
    p = np.clip(warm[..., 0], min_theta, max_theta)
    target = nu[..., 0]
    for _ in range(30):
        grad = -t * (s / p - (n - s) / (1 - p)) + p - target
        hess = t * (s / p**2 + (n - s) / (1 - p) ** 2) + 1.0
        step = grad / np.maximum(hess, 1e-12)
        candidate = np.clip(p - step, min_theta, max_theta)
        if np.max(np.abs(candidate - p)) < 1e-10:
            p = candidate
            break
        p = candidate
    return p[..., None]


def logistic_local_prox(t, nu, warm, X_by_node, y_by_node, ridge=0.0):
    """Newton proximal update for binary logistic losses, one node at a time."""
    out = np.array(warm, dtype=float, copy=True)
    for i, (x, y) in enumerate(zip(X_by_node, y_by_node)):
        if x is None or len(y) == 0:
            out[i] = nu[i]
            continue
        beta = out[i]
        for _ in range(40):
            prob = expit(x @ beta)
            grad = x.T @ (prob - y) + (beta - nu[i]) / t + ridge * beta
            hess = x.T @ ((prob * (1 - prob))[:, None] * x) + np.eye(x.shape[1]) / t + ridge * np.eye(x.shape[1])
            step = np.linalg.solve(hess, grad)
            beta_new = beta - step
            if np.linalg.norm(step) < 1e-8:
                beta = beta_new
                break
            beta = beta_new
        out[i] = beta
    return out
