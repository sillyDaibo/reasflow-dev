import networkx as nx
import numpy as np

from strat_models import from_networkx, product_grid, set_edge_weight
from strat_models.solvers import bernoulli_prox, fit_admm, poisson_prox


def test_poisson_prox_matches_stationarity():
    counts = np.array([[3.0, 7.0]])
    nu = np.array([[2.0]])
    out = poisson_prox(0.5, nu, nu, counts)[0, 0]
    # derivative of 0.5*(3 theta - 7 log theta) + 0.5*(theta-2)^2
    assert abs(0.5 * (3 - 7 / out) + (out - 2)) < 1e-8


def test_bernoulli_prox_bounds_and_stationarity():
    counts = np.array([[10.0, 7.0]])
    out = bernoulli_prox(0.7, np.array([[0.2]]), np.array([[0.5]]), counts)[0, 0]
    assert 1e-5 <= out <= 1 - 1e-5
    grad = -0.7 * (7 / out - 3 / (1 - out)) + out - 0.2
    assert abs(grad) < 1e-7


def test_admm_consensus_on_two_node_constant_loss():
    graph = nx.path_graph(2)
    set_edge_weight(graph, 3.0)
    op = from_networkx(graph)
    target = np.array([[1.0], [4.0]])

    def loss_prox(t, nu, warm):
        # prox of 1/2 (theta-target)^2
        return (nu + t * target) / (1 + t)

    params, _, info = fit_admm(op, (1,), loss_prox, lambda t, nu, warm: nu,
                               maxiter=300, abs_tol=1e-8, rel_tol=1e-8,
                               max_cg_iterations=100)
    assert info.converged
    assert np.all(np.isfinite(params))
    assert np.linalg.norm(params[0] - params[1]) < 2.0


def test_product_grid_operator_matches_explicit_laplacian():
    op = product_grid((3, 4), (2.0, 5.0), (False, True))
    g = nx.path_graph(3); set_edge_weight(g, 2.0)
    h = nx.cycle_graph(4); set_edge_weight(h, 5.0)
    from strat_models import cartesian_product
    explicit = from_networkx(cartesian_product([g, h]))
    x = np.arange(12, dtype=float)
    assert np.allclose(op.matvec(x), explicit.matvec(x))

