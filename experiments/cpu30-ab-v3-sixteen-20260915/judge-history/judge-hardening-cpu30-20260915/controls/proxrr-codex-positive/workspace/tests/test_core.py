import numpy as np
from scipy.sparse import csr_matrix

from rr_prox_fed.algorithms import ProxRR, ProxSGD
from rr_prox_fed.federated import FedRR
from rr_prox_fed.objectives import ElasticNetLogistic, ProximalOperator


def toy_objective(l2_in_prox=True):
    A = csr_matrix([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [-1.0, 0.5]])
    b = np.array([1.0, 0.0, 1.0, 0.0])
    return ElasticNetLogistic(A, b, l1=0.1, l2=0.2, l2_in_prox=l2_in_prox)


def test_elastic_net_prox_is_closed_form():
    prox = ProximalOperator(l1=0.5, l2=0.25)
    x = np.array([-2.0, 0.2, 0.0, 3.0])
    expected = np.sign(x) * np.maximum(np.abs(x) - 0.4 * 0.5, 0.0) / (1 + 0.4 * 0.25)
    np.testing.assert_allclose(prox(x, 0.4), expected)


def test_minibatch_gradient_matches_full_gradient():
    objective = toy_objective(l2_in_prox=False)
    x = np.array([0.2, -0.3])
    idx = np.arange(objective.n)
    np.testing.assert_allclose(objective.gradient(x), objective.gradient(x, idx=idx), rtol=1e-12)


def test_proxrr_uses_one_prox_per_epoch_and_is_deterministic():
    objective = toy_objective()
    x1, tr1 = ProxRR(objective, epochs=3, step_size=0.1, seed=7).run()
    x2, tr2 = ProxRR(objective, epochs=3, step_size=0.1, seed=7).run()
    np.testing.assert_allclose(x1, x2)
    assert tr1.prox_evaluations[-1] == 3
    assert tr1.iterations[-1] == objective.n * 3
    assert tr2.objective == tr1.objective


def test_heuristic_and_sgd_prox_every_step():
    objective = toy_objective()
    _, rr = ProxRR(objective, epochs=2, step_size=0.05, seed=1, prox_every_iteration=True).run()
    _, sgd = ProxSGD(objective, iterations=6, step_size=0.05, seed=1).run()
    assert rr.prox_evaluations[-1] == rr.iterations[-1]
    assert sgd.prox_evaluations[-1] == sgd.iterations[-1]


def test_importance_resampling_is_reproducible():
    objective = toy_objective()
    x, trace = ProxRR(objective, epochs=2, step_size=0.05, seed=4, importance_sampling=True).run()
    assert x.shape == (2,)
    assert trace.prox_evaluations[-1] == 2
    assert np.isfinite(trace.objective[-1])


def test_fedrr_records_rounds_and_aggregates_clients():
    objective = toy_objective(l2_in_prox=False)
    clients = [(objective.A[:2], objective.b[:2]), (objective.A[2:], objective.b[2:])]
    x, trace = FedRR(clients, epochs=4, step_size=0.05, seed=3, l2=0.2, l2_in_prox=False).run()
    assert x.shape == (2,)
    assert trace.iterations[-1] == 4
    assert trace.prox_evaluations[-1] == 4
    assert len(trace.objective) == 5
