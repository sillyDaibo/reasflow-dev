"""Graph helpers for Laplacian-regularized stratified models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import networkx as nx
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator


def cartesian_product(graphs: Sequence[nx.Graph]) -> nx.Graph:
    """Return a flattened NetworkX Cartesian product.

    Node labels are tuples in the same order as ``graphs``. Existing edge
    weights are preserved; callers can set weights on component graphs before
    constructing the product.
    """
    if not graphs:
        raise ValueError("at least one graph is required")
    result = graphs[0].copy()
    for graph in graphs[1:]:
        result = nx.cartesian_product(result, graph)
    mapping = {node: _flatten(node) for node in result.nodes}
    return nx.relabel_nodes(result, mapping)


def _flatten(value):
    if isinstance(value, tuple):
        out = []
        for item in value:
            out.extend(_flatten(item) if isinstance(item, tuple) else [item])
        return tuple(out)
    return (value,)


def set_edge_weight(graph: nx.Graph, weight: float) -> None:
    if weight < 0:
        raise ValueError("edge weight must be nonnegative")
    for _, _, data in graph.edges(data=True):
        data["weight"] = float(weight)


@dataclass
class GraphOperator:
    """Indexed graph and Laplacian operator used by the ADMM solver."""

    nodes: list
    matrix: sparse.spmatrix | None
    operator: LinearOperator
    diagonal: np.ndarray

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    def matvec(self, x: np.ndarray) -> np.ndarray:
        return self.operator.matvec(np.asarray(x, dtype=float))

    def system(self, rho: float) -> LinearOperator:
        n = self.n_nodes
        return LinearOperator(
            (n, n),
            matvec=lambda x: self.matvec(x) + 2.0 * rho * x,
            dtype=float,
        )


def from_networkx(graph: nx.Graph) -> GraphOperator:
    nodes = list(graph.nodes)
    index = {node: i for i, node in enumerate(nodes)}
    rows, cols, vals = [], [], []
    degree = np.zeros(len(nodes), dtype=float)
    for u, v, data in graph.edges(data=True):
        weight = float(data.get("weight", 1.0))
        if weight < 0:
            raise ValueError("edge weight must be nonnegative")
        i, j = index[u], index[v]
        rows.extend((i, j, i, j))
        cols.extend((i, j, j, i))
        vals.extend((weight, weight, -weight, -weight))
        degree[i] += weight
        degree[j] += weight
    lap = sparse.coo_matrix((vals, (rows, cols)), shape=(len(nodes), len(nodes))).tocsr()
    return GraphOperator(nodes, lap, LinearOperator(lap.shape, matvec=lap.dot, dtype=float), degree)


class ProductGridOperator(GraphOperator):
    """Laplacian operator for a Cartesian product of paths/cycles.

    This avoids materializing Chicago's 3.5 million by 3.5 million sparse
    matrix while retaining exactly the product-graph Laplacian in the paper.
    """

    def __init__(self, dimensions: Sequence[int], weights: Sequence[float], cycles: Sequence[bool]):
        self.dimensions = tuple(int(d) for d in dimensions)
        self.weights = tuple(float(w) for w in weights)
        self.cycles = tuple(bool(c) for c in cycles)
        if not (len(self.dimensions) == len(self.weights) == len(self.cycles)):
            raise ValueError("dimensions, weights, and cycles must have equal length")
        if any(d < 1 for d in self.dimensions) or any(w < 0 for w in self.weights):
            raise ValueError("invalid product graph specification")
        n = int(np.prod(self.dimensions))
        nodes = list(np.ndindex(*self.dimensions))
        diagonal = np.zeros(self.dimensions, dtype=float)
        for axis, (size, weight, cycle) in enumerate(zip(self.dimensions, self.weights, self.cycles)):
            degree = 2 if cycle and size > 2 else (1 if size == 2 else 2)
            if not cycle:
                degree_arr = np.full(size, 2.0)
                if size == 1:
                    degree_arr[:] = 0.0
                elif size == 2:
                    degree_arr[:] = 1.0
                else:
                    degree_arr[[0, -1]] = 1.0
            else:
                degree_arr = np.full(size, float(degree))
                if size == 1:
                    degree_arr[:] = 0.0
            reshape = [1] * len(self.dimensions)
            reshape[axis] = size
            diagonal += weight * degree_arr.reshape(reshape)
        self.diagonal_grid = diagonal

        def apply(vector):
            x = np.asarray(vector, dtype=float).reshape(self.dimensions)
            out = diagonal * x
            for axis, (size, weight, cycle) in enumerate(zip(self.dimensions, self.weights, self.cycles)):
                if size <= 1 or weight == 0:
                    continue
                if cycle:
                    out -= weight * (np.roll(x, 1, axis=axis) + np.roll(x, -1, axis=axis))
                else:
                    sl = [slice(None)] * x.ndim
                    sl[axis] = slice(1, None)
                    sl_prev = [slice(None)] * x.ndim
                    sl_prev[axis] = slice(0, -1)
                    out[tuple(sl)] -= weight * x[tuple(sl_prev)]
                    out[tuple(sl_prev)] -= weight * x[tuple(sl)]
            return out.ravel()

        super().__init__(nodes, None, LinearOperator((n, n), matvec=apply, dtype=float), diagonal.ravel())


def product_grid(dimensions: Sequence[int], weights: Sequence[float], cycles: Sequence[bool]) -> ProductGridOperator:
    return ProductGridOperator(dimensions, weights, cycles)

