"""Dataset loading and provenance helpers for the paper experiments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
from sklearn.datasets import load_svmlight_file


def load_libsvm(name: str, data_dir: str | Path, *, zero_based: bool = True) -> Tuple[object, np.ndarray, Dict[str, object]]:
    path = Path(data_dir) / name
    if not path.is_file():
        raise FileNotFoundError(f"dataset {name!r} not found at {path}; copy the official libsvm file into .run-data/datasets")
    A, b = load_svmlight_file(path, zero_based=zero_based)
    b = np.asarray(b, dtype=float)
    # The objective uses labels in {0, 1}; libsvm a1a is encoded as {-1, 1}.
    labels = np.unique(b)
    if np.array_equal(labels, [-1.0, 1.0]):
        b = (b + 1.0) / 2.0
    elif not np.all(np.isin(labels, [0.0, 1.0])):
        b = (b == labels.max()).astype(float)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    provenance = {"name": name, "path": str(path), "sha256": digest, "bytes": path.stat().st_size,
                  "rows": int(A.shape[0]), "features": int(A.shape[1])}
    return A.tocsr(), b, provenance


def partition_clients(A, b, n_clients: int):
    """Return deterministic contiguous, equal-size client shards."""
    if n_clients < 1 or A.shape[0] < n_clients:
        raise ValueError("n_clients must be positive and no larger than the number of rows")
    n = A.shape[0] // n_clients
    usable = n * n_clients
    return [(A[i * n:(i + 1) * n], b[i * n:(i + 1) * n]) for i in range(n_clients)], usable

