"""Read-only finite-difference audit of the saved DREAM B objective.
Run with NumPy installed: python3 audit_dream_gradient_scaling.py
This script imports the saved source and writes no benchmark files.
"""
from pathlib import Path
import importlib.util
import json
import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'evidence/OptiRepro_cpu_2/agent_reproduction/runs/2212.02387/ReasFlow实验Agent-完整复现-Goal/第003次运行/workspace/src/dream_reproduction/objective.py'
spec = importlib.util.spec_from_file_location('audit_dream_objective', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
features = np.array([[1., 2.], [-.5, 1.], [2., -.4], [.3, .7]])
labels = np.array([1., -1., 1., -1.])
x = np.array([.2, -.3])
epsilon = 1e-6
lambda2 = 0.0
value, reported_norm, y_star = module.primal_value_and_grad(features, labels, x, lambda2=lambda2)
gradient = np.empty(x.size)
for i, direction in enumerate(np.eye(x.size)):
    plus = module.primal_value_and_grad(features, labels, x + epsilon * direction, lambda2=lambda2)[0]
    minus = module.primal_value_and_grad(features, labels, x - epsilon * direction, lambda2=lambda2)[0]
    gradient[i] = (plus - minus) / (2 * epsilon)
print(json.dumps({
    'scope': 'Read-only deterministic diagnostic; does not rerun or modify benchmark',
    'source': str(SOURCE), 'features': features.tolist(), 'labels': labels.tolist(),
    'samples': len(labels), 'x': x.tolist(), 'epsilon': epsilon, 'regularizer_lambda2': lambda2,
    'primal_value': value, 'simplex_maximizer': y_star.tolist(),
    'finite_difference_gradient': gradient.tolist(),
    'finite_difference_norm': float(np.linalg.norm(gradient)),
    'function_returned_gradient_norm': reported_norm,
    'ratio': float(np.linalg.norm(gradient) / reported_norm),
    'finding': 'Returned gradient norm is 1/N of derivative of returned primal value when lambda2=0.',
}, indent=2))
