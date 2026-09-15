import json
import tempfile
import unittest
from pathlib import Path
import numpy as np

from beer_repro.data import ClientData, load_a9a
from beer_repro.runner import run_experiment


class DataRunnerTests(unittest.TestCase):
    def test_batch_is_deterministic_and_wraps(self):
        data = ClientData(np.arange(10).reshape(5, 2), np.arange(5))
        x1, y1 = data.batch(0, 8)
        x2, y2 = data.batch(0, 8)
        self.assertTrue(np.array_equal(x1, x2)); self.assertTrue(np.array_equal(y1, y2))
        self.assertEqual(len(y1), 8)

    def test_small_a9a_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def write(name):
                rows = []
                for i in range(30):
                    label = 1 if i % 2 else -1
                    rows.append(f"{label} 1:{0.1*i:.4f} 2:1\n")
                (root / name).write_text("".join(rows), encoding="utf-8")
            write("a9a"); write("a9a.t")
            out = root / "out"
            cfg = {"experiment_id":"test", "task":"a9a", "data_root":str(root), "clients":3, "topology":"ring", "lr":0.01, "gamma":0.1, "batch_size":4, "rounds":2, "compressor":"identity", "compression_param":0, "alpha":0.05, "seed":1, "methods":["BEER","DSGD"]}
            payload = run_experiment(cfg, out)
            self.assertEqual(len(payload["metrics"]["BEER"]["round"]), 2)
            self.assertTrue((out / "metrics.json").is_file())
            self.assertTrue((out / "figures" / "gradient_norm.png").is_file() or (out / "figures" / "gradient_norm.svg").is_file())

    def test_a9a_sorting_creates_label_skew(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rows = [f"{1 if i < 10 else -1} 1:1\n" for i in range(20)]
            (root / "a9a").write_text("".join(rows), encoding="utf-8")
            (root / "a9a.t").write_text("".join(rows), encoding="utf-8")
            clients, _, info = load_a9a(root, clients=2)
            self.assertEqual([set(c.labels.tolist()) for c in clients], [{-1}, {1}])
            self.assertIn("sort=True", info["partition"])


if __name__ == "__main__":
    unittest.main()
