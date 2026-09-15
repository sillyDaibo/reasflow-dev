import unittest
import numpy as np

from beer_repro.algorithms import BEER, CHOCOSGD, DSGD, D2
from beer_repro.compression import compress
from beer_repro.graphs import mixing_matrix, spectral_gap


class CoreTests(unittest.TestCase):
    def test_graph_is_symmetric_stochastic(self):
        w = mixing_matrix(8, "ring")
        self.assertTrue(np.allclose(w, w.T))
        self.assertTrue(np.allclose(w.sum(axis=1), 1.0))
        self.assertGreater(spectral_gap(w), 0.0)

    def test_compressors_preserve_shape_and_topk(self):
        x = np.arange(20, dtype=float)
        self.assertEqual(compress(x, "gsgd", 5).shape, x.shape)
        self.assertEqual(np.count_nonzero(compress(x, "top", 4)), 4)
        self.assertTrue(np.allclose(compress(x, "identity"), x))

    def test_beer_tracker_recursion_changes_both_trackers(self):
        rng = np.random.default_rng(2)
        x0 = np.zeros((3, 5))
        w = mixing_matrix(3, "ring")
        alg = BEER(x0, w, lr=0.1, gamma=0.2, compressor="identity", compression_param=0)
        g0 = rng.normal(size=x0.shape)
        alg.initialize(g0)
        h0, g0_state = alg.h.copy(), alg.g.copy()
        alg.step(rng.normal(size=x0.shape))
        self.assertFalse(np.allclose(alg.h, h0))
        self.assertFalse(np.allclose(alg.g, g0_state))
        self.assertEqual(alg.x.shape, x0.shape)

    def test_baselines_run_one_step(self):
        x0 = np.zeros((3, 4)); w = mixing_matrix(3)
        grad = np.ones_like(x0)
        for cls in (CHOCOSGD, DSGD, D2):
            kwargs = {"lr": 0.1}
            if cls is CHOCOSGD:
                kwargs.update(gamma=0.2, compressor="identity", compression_param=0)
            alg = cls(x0, w, **kwargs)
            alg.step(grad)
            self.assertTrue(np.isfinite(alg.x).all())


if __name__ == "__main__":
    unittest.main()
