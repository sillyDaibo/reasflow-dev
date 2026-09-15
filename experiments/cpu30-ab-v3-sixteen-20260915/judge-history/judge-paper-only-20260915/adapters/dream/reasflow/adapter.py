"""External DREAM input adapter and read-only execution observer.

No update/estimator/mixing algorithm is defined in this module. The only math
supplied here is the public synthetic objective and its feasible-set projection.
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys

import numpy as np


def execute(variant: str) -> None:
    sys.dont_write_bytecode = True
    workspace = Path(os.environ['OPTIREPRO_WORKSPACE']).resolve()
    public_path = Path(os.environ['OPTIREPRO_CASES']).resolve()
    if public_path.name != 'public_cases.json':
        raise ValueError('Only the redacted public_cases.json is accepted')
    public = json.loads(public_path.read_text())
    package = 'dream_repro' if variant == 'native' else 'dream_reproduction'
    sys.path.insert(0, str(workspace if variant == 'native' else workspace / 'src'))
    alg = importlib.import_module(package + '.algorithms')
    mixing = importlib.import_module(package + '.mixing')
    data = importlib.import_module(package + '.data')
    results = []
    for case in public['cases']:
        results.append(run_case(case, variant, alg, mixing, data))
    print('OPTIREPRO_OBSERVATIONS=' + json.dumps({'cases': results}, allow_nan=False, separators=(',', ':')))


def run_case(case, variant, alg, mixing, data):
    inp, par = case['inputs'], case['parameters']
    coefficients = np.asarray(inp['component_coefficients'], dtype=float)
    m, local_n, _ = coefficients.shape
    initial = np.asarray(inp['initial_z'], dtype=float)
    if initial.shape != (2,):
        raise ValueError('This adapter supports the supplied one-x/one-y cases')
    features = np.zeros((m * local_n, 1), dtype=float)
    labels = np.ones(m * local_n, dtype=float)
    if variant == 'native':
        dataset = data.Dataset(case['id'], features, labels, 'synthetic public input', '', m * local_n)
        config = alg.ExperimentConfig(
            agents=m, max_steps=par['T'], batch_size=par['b'],
            large_batch_size=par['b_prime'], probability=par['p'], q=par['q'],
            lr_x=par['gamma'] * par['eta'], lr_y=par['eta'],
            kappa=float(inp['W'][0][0]), initial_mix=par['K0'],
            small_mix=par['K'], large_mix=par['K_prime'], print_every=1,
        )
        runner_code = alg.run_algorithm.__code__
        init_code = alg._initial_state.__code__
        gradient_name, projection_name = 'local_gradient', 'project_simplex_rows'
    else:
        partitions = tuple(np.arange(i * local_n, (i + 1) * local_n) for i in range(m))
        dataset = data.Dataset(case['id'], features, labels, partitions, 'synthetic public input', '')
        config = alg.AlgorithmConfig(
            eta=par['eta'], gamma=par['gamma'], prob=par['p'], q=par['q'],
            b=par['b'], b0=par['b_prime'], tau=float(inp['W'][0][0]),
            K0=par['K0'], K=par['K'], K_prime=par['K_prime'], eval_every=1,
        )
        runner_code = alg._run_dream.__code__
        init_code = alg._fresh_state.__code__
        gradient_name, projection_name = 'local_gradients', 'project_simplex'

    captured = {}
    mixes = {}
    projections = {}
    random_calls = {}

    def runner(frame):
        while frame is not None:
            if frame.f_code is runner_code:
                return frame
            frame = frame.f_back
        raise RuntimeError('Boundary was called outside the original DREAM runner')

    def state_step(frame):
        return int(runner(frame).f_locals.get('step', 0))

    def save(step, name, value):
        captured[(step, name)] = np.asarray(value, dtype=float).copy()

    def synthetic_gradient(features_arg, labels_arg, x, y, indices, *args, **kwargs):
        # Dataset partitions encode node and component IDs. Average only the
        # original runner's requested samples; do not apply any gating or q.
        indices = np.asarray(indices, dtype=int)
        nodes = indices // local_n
        if len(indices) == 0 or not np.all(nodes == nodes[0]):
            raise ValueError('Invalid synthetic component selection')
        selected = coefficients[int(nodes[0]), indices % local_n]
        a, c, d, e, h = selected.mean(axis=0)
        gx = np.asarray([a * x[0] + c * y[0] + e])
        gy = np.asarray([c * x[0] - d * y[0] + h])
        return np.concatenate((gx, gy)) if variant == 'native' else (gx, gy)

    def domain_projection(values):
        step = state_step(sys._getframe(1))
        before = np.asarray(values, dtype=float).copy()
        interval = inp['y_interval']
        after = before.copy() if interval is None else np.clip(before, interval[0], interval[1])
        projections.setdefault(step, []).append((before, after.copy()))
        return after

    class InputRNG:
        def __init__(self, node):
            self.node = node

        def random(self, size=None):
            if size is not None:
                raise ValueError('Unexpected vector-valued Bernoulli input')
            step = state_step(sys._getframe(1))
            key = (step, self.node)
            call = random_calls.get(key, 0)
            random_calls[key] = call + 1
            if self.node == 0 and call == 0:
                bit = inp['refresh_draws'][step - 1]
                threshold = par['p']
            else:
                bit = inp['active_draws'][step - 1][self.node]
                threshold = par['q']
            return threshold / 2 if bit else (1 + threshold) / 2

        def sample(self, size):
            step = state_step(sys._getframe(1))
            result = np.asarray(inp['sample_indices'][step - 1][self.node], dtype=int)
            if len(result) != size:
                raise ValueError('Requested batch does not match public random input')
            return result.copy()

        def integers(self, low, high=None, size=None, **kwargs):
            if low != 0 or high != local_n:
                raise ValueError('Unexpected component-index bounds')
            return self.sample(size)

        def choice(self, candidates, size=None, replace=True, **kwargs):
            return np.asarray(candidates)[self.sample(size)]

    rng_count = 0

    def input_rng(seed=None):
        nonlocal rng_count
        if rng_count >= m:
            raise RuntimeError('Original runner created unexpected extra random generators')
        value = InputRNG(rng_count)
        rng_count += 1
        return value

    def trace(frame, event, arg):
        if frame.f_code is init_code and event == 'return':
            # Modify only initialized input buffers before the runner consumes
            # them. No gradient/tracker/update local is assigned by the adapter.
            x, y = arg[:2]
            x.resize((m, 1), refcheck=False)
            y.resize((m, 1), refcheck=False)
            x[:] = initial[0]
            y[:] = initial[1]
        elif frame.f_code is mixing.fast_mix.__code__ and event == 'call':
            owner = runner(frame.f_back)
            step = int(owner.f_locals.get('step', 0))
            actual_matrix = frame.f_locals['matrix']
            if not np.allclose(actual_matrix, inp['W'], atol=1e-14, rtol=0):
                raise ValueError('Public W is not represented by the original ring interface')
            mixes.setdefault(step, []).append(np.asarray(frame.f_locals['values']).copy())
        elif frame.f_code is alg._record.__code__ and event == 'call':
            loc = runner(frame.f_back).f_locals
            step = int(frame.f_locals['step'])
            z = np.concatenate((loc['x'], loc['y']), axis=1)
            save(step, 'z', z)
            if variant == 'native':
                save(step, 'g', loc['g'])
                save(step, 's', loc['s'])
            else:
                save(step, 'g', np.concatenate((loc['gx'], loc['gy']), axis=1))
                save(step, 's', np.concatenate((loc['sx'], loc['sy']), axis=1))
            if step:
                save(step, 'mean_z', z.mean(axis=0))
                actual_mixes = mixes[step]
                actual_projections = projections[step]
                if variant == 'native':
                    if len(actual_mixes) != 3 or len(actual_projections) != 1:
                        raise RuntimeError('Unexpected native algorithm operation sequence')
                    # These are the original descent/ascent proposals,
                    # observed as FastMix inputs before any mixing/projection.
                    save(step, 'pre_projection', np.concatenate(actual_mixes[:2], axis=1))
                    # This runner projects only after mixing. It has no
                    # pre-mixing projected state; do not synthesize that field.
                    save(step, 'tracker_input', actual_mixes[2])
                else:
                    if len(actual_mixes) != 4 or len(actual_projections) != m:
                        raise RuntimeError('Unexpected ReasFlow algorithm operation sequence')
                    # x's pre-mix value is the actual first FastMix argument;
                    # y's before/after values are actual projection I/O rows.
                    before_y = np.vstack([pair[0] for pair in actual_projections])
                    after_y = np.vstack([pair[1] for pair in actual_projections])
                    save(step, 'pre_projection', np.concatenate((actual_mixes[0], before_y), axis=1))
                    save(step, 'projected', np.concatenate((actual_mixes[0], after_y), axis=1))
                    save(step, 'tracker_input', np.concatenate(actual_mixes[2:4], axis=1))
        return trace

    saved_gradient = getattr(alg, gradient_name)
    saved_projection = getattr(alg, projection_name)
    saved_rng = np.random.default_rng
    saved_trace = sys.gettrace()
    setattr(alg, gradient_name, synthetic_gradient)
    setattr(alg, projection_name, domain_projection)
    np.random.default_rng = input_rng
    try:
        sys.settrace(trace)
        if variant == 'native':
            alg.run_algorithm('DREAM', dataset, config)
        else:
            alg.run_algorithm(dataset, 'DREAM', iterations=par['T'], seed=0, config=config)
    finally:
        sys.settrace(saved_trace)
        np.random.default_rng = saved_rng
        setattr(alg, gradient_name, saved_gradient)
        setattr(alg, projection_name, saved_projection)

    observations = []
    missing = []
    for schema in case['observation_schema']:
        key = (schema['step'], schema['name'])
        if key not in captured:
            missing.append({'step': key[0], 'name': key[1]})
            continue
        value = captured[key]
        if list(value.shape) != schema['shape']:
            raise RuntimeError(f'Unexpected observation shape for {key}: {value.shape}')
        observations.append({'step': key[0], 'name': key[1], 'value': value.tolist()})
    reason = ('Original algorithm returns metric histories, with no historical '
              'candidate list or random x output (output_candidates/x_out).')
    if variant == 'native':
        reason += (' It projects after mixing and never forms the requested '
                   'pre-mixing projected state; projected is therefore unavailable.')
    result = {'id': case['id'], 'status': 'blocked', 'reason': reason,
              'observations': observations, 'missing_observations': missing}
    print(json.dumps({'case': case['id'], 'variant': variant, 'status': result['status'],
                      'missing_observations': missing, 'reason': reason}), file=sys.stderr)
    return result


if __name__ == "__main__":
    execute('reasflow')
