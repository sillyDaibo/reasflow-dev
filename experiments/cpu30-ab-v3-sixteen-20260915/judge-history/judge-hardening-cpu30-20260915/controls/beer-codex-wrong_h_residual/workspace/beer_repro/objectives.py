"""Paper objectives and NumPy gradients."""

from __future__ import annotations

import numpy as np


def logistic_loss_gradient(params, features, labels, alpha=0.05):
    params = np.asarray(params, dtype=float)
    margin = labels * (features @ params)
    # stable logistic loss and derivative
    loss = np.logaddexp(0.0, -margin).mean() + alpha * np.sum(params * params / (1.0 + params * params))
    coeff = -labels / (1.0 + np.exp(np.clip(margin, -60.0, 60.0)))
    grad = features.T @ coeff / len(labels)
    grad += alpha * 2.0 * params / (1.0 + params * params) ** 2
    return float(loss), grad


def logistic_accuracy(params, features, labels):
    return float(np.mean(np.sign(features @ params) == labels))


def nn_unpack(params, input_dim, hidden=32, classes=10):
    n1 = hidden * input_dim
    n2 = hidden
    n3 = classes * hidden
    return (params[:n1].reshape(hidden, input_dim), params[n1:n1+n2], params[n1+n2:n1+n2+n3].reshape(classes, hidden), params[n1+n2+n3:n1+n2+n3+classes])


def nn_pack(w1, b1, w2, b2):
    return np.concatenate([w1.ravel(), b1.ravel(), w2.ravel(), b2.ravel()])


def nn_loss_gradient(params, features, labels, hidden=32, classes=10):
    w1, b1, w2, b2 = nn_unpack(params, features.shape[1], hidden, classes)
    z1 = features @ w1.T + b1
    h = 1.0 / (1.0 + np.exp(-np.clip(z1, -40.0, 40.0)))
    logits = h @ w2.T + b2
    logits -= logits.max(axis=1, keepdims=True)
    probs = np.exp(logits)
    probs /= probs.sum(axis=1, keepdims=True)
    loss = -np.log(np.maximum(probs[np.arange(len(labels)), labels], 1e-12)).mean()
    dlogits = probs
    dlogits[np.arange(len(labels)), labels] -= 1.0
    dlogits /= len(labels)
    dw2 = dlogits.T @ h
    db2 = dlogits.sum(axis=0)
    dh = dlogits @ w2
    dz1 = dh * h * (1.0 - h)
    dw1 = dz1.T @ features
    db1 = dz1.sum(axis=0)
    return float(loss), nn_pack(dw1, db1, dw2, db2)


def nn_accuracy(params, features, labels, hidden=32, classes=10):
    w1, b1, w2, b2 = nn_unpack(params, features.shape[1], hidden, classes)
    h = 1.0 / (1.0 + np.exp(-np.clip(features @ w1.T + b1, -40.0, 40.0)))
    return float(np.mean(np.argmax(h @ w2.T + b2, axis=1) == labels))
