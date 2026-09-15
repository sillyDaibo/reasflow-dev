"""Laplacian-regularized stratified models (paper 1904.12017)."""

from .graph import GraphOperator, ProductGridOperator, cartesian_product, from_networkx, product_grid, set_edge_weight
from .solvers import ADMMInfo, bernoulli_prox, fit_admm, logistic_local_prox, poisson_prox, ridge_prox, ridge_regularizer_prox

__all__ = [
    "GraphOperator", "ProductGridOperator", "cartesian_product", "from_networkx", "product_grid", "set_edge_weight",
    "ADMMInfo", "fit_admm", "poisson_prox", "bernoulli_prox", "ridge_prox", "ridge_regularizer_prox", "logistic_local_prox",
]

