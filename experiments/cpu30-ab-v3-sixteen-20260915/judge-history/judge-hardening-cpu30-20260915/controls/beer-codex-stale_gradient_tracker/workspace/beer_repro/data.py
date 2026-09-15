"""Readers and deterministic heterogeneous client partitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np


@dataclass
class ClientData:
    features: np.ndarray
    labels: np.ndarray

    def batch(self, round_id: int, batch_size: int) -> tuple[np.ndarray, np.ndarray]:
        if len(self.labels) == 0:
            raise ValueError("client has no samples")
        start = (round_id * batch_size) % len(self.labels)
        idx = (start + np.arange(batch_size)) % len(self.labels)
        return self.features[idx], self.labels[idx]


def _partition(features, labels, clients: int, by_label: bool) -> list[ClientData]:
    if by_label:
        parts = []
        for client in range(clients):
            idx = np.flatnonzero(labels == client)
            if not len(idx):
                raise ValueError(f"label {client} is absent; cannot make label partition")
            parts.append(ClientData(features[idx], labels[idx]))
        return parts
    chunks = np.array_split(np.arange(len(labels)), clients)
    return [ClientData(features[idx], labels[idx]) for idx in chunks]


def load_a9a(root: str | Path, clients: int = 10, alpha: float = 0.05) -> tuple[list[ClientData], ClientData, dict]:
    root = Path(root)
    def read(path):
        rows, ys = [], []
        max_dim = 123
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            fields = line.split()
            ys.append(1 if float(fields[0]) > 0 else -1)
            row = np.zeros(max_dim, dtype=np.float64)
            for token in fields[1:]:
                j, value = token.split(":")
                if int(j) <= max_dim:
                    row[int(j) - 1] = float(value)
            rows.append(row)
        return np.asarray(rows), np.asarray(ys, dtype=np.int8)
    train_x, train_y = read(root / "a9a")
    test_x, test_y = read(root / "a9a.t")
    # The official experiment uses sort=True: labels are grouped before the
    # contiguous split, producing the paper's strongly label-skewed clients.
    order = np.argsort(train_y, kind="stable")
    train_x, train_y = train_x[order], train_y[order]
    info = {"name": "LIBSVM a9a / Adult", "alpha": alpha, "train_samples": len(train_y), "test_samples": len(test_y), "features": train_x.shape[1], "partition": "label-sorted contiguous (official sort=True)"}
    return _partition(train_x, train_y, clients, False), ClientData(test_x, test_y), info


def load_mnist(root: str | Path, clients: int = 10) -> tuple[list[ClientData], ClientData, dict]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("MNIST loading requires pyarrow; install requirements.txt") from exc
    root = Path(root)
    def read(path):
        table = pq.read_table(path)
        columns = table.column_names
        # Mirrors the supplied mirror's labels/images without assuming column order.
        label_name = next((c for c in columns if c.lower() in {"label", "labels", "target", "targets"}), None)
        if label_name is None:
            raise ValueError(f"cannot identify label column in {path}: {columns}")
        labels = np.asarray(table[label_name].to_numpy(), dtype=np.int64)
        feature_names = [c for c in columns if c != label_name]
        if len(feature_names) == 1 and feature_names[0].lower() == "image":
            # HuggingFace parquet stores images as {bytes, path} structs.
            from io import BytesIO
            from PIL import Image
            entries = table[feature_names[0]].to_pylist()
            features = np.stack([np.asarray(Image.open(BytesIO(item["bytes"])).convert("L"), dtype=np.float64).reshape(-1) for item in entries])
        elif len(feature_names) == 1:
            features = np.asarray(table[feature_names[0]].to_pylist(), dtype=np.float64)
        else:
            features = np.column_stack([np.asarray(table[c].to_numpy()) for c in feature_names]).astype(np.float64)
        features = features.reshape(len(labels), -1) / 255.0
        features = (features - 0.1307) / 0.3081
        return features, labels
    train_x, train_y = read(root / "train.parquet")
    test_x, test_y = read(root / "test.parquet")
    info = {"name": "MNIST", "train_samples": len(train_y), "test_samples": len(test_y), "features": train_x.shape[1], "partition": "one digit label per client"}
    return _partition(train_x, train_y, clients, True), ClientData(test_x, test_y), info


def write_sources(path: str | Path, records: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Dataset sources\n\n" + "\n".join(f"- {json.dumps(record, sort_keys=True)}" for record in records) + "\n", encoding="utf-8")
