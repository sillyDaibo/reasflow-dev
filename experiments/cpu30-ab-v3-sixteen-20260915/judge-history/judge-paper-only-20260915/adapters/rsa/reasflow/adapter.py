"""External RSA observation adapters; no expected trajectories are read or computed."""
from __future__ import annotations

import importlib
import inspect
import json
import os
from pathlib import Path
import sys

import numpy as np


def emit_case(case, data, status="ok", reason=None, diagnostics=None):
    wanted = {(item["step"], item["name"]) for item in case["observation_schema"]}
    observations = [{"step": step, "name": name, "value": np.asarray(value).tolist()}
                    for (step, name), value in data.items() if (step, name) in wanted]
    result = {"id": case["id"], "observations": observations, "status": status}
    if reason:
        result["reason"] = reason
    if diagnostics:
        result["diagnostics"] = diagnostics
    return result


def input_arrays(case):
    inputs = case["inputs"]
    master = np.asarray(inputs["initial_master"], dtype=float)
    regular = np.asarray(inputs["initial_regular_workers"], dtype=float)
    centers = np.asarray(inputs["regular_worker_quadratic_centers"], dtype=float)
    adversarial = np.asarray(inputs["byzantine_messages_by_step"], dtype=float)
    if np.any(np.asarray(inputs["master_quadratic_center"]) != 0):
        raise ValueError("The implementation's master regularizer cannot express a nonzero quadratic center.")
    return master, regular, centers, adversarial


def codex_case(module, case):
    master, regular, centers, adversarial = input_arrays(case)
    nr, dimension = regular.shape
    nb = adversarial.shape[1]
    workers = nr + nb
    state = module.RSAState(master.copy(), np.concatenate([regular, np.zeros((nb, dimension))]))
    batches = [(np.asarray([[i]], dtype=float), np.zeros(1, dtype=int)) for i in range(workers)]
    data = {(0, "master"): state.master.copy(), (0, "regular_workers"): state.locals[:nr].copy()}
    norm = {1: "l1", 2: "l2", "infinity": "linf"}[case["parameters"]["p"]]
    step_context = {}
    saved_gradient = module.softmax_gradient
    saved_attack = module.attack_message

    def quadratic_gradient(x, y, theta, *args, **kwargs):
        worker = int(x[0, 0])
        gradient = theta - centers[worker] if worker < nr else np.zeros_like(theta)
        if worker < nr:
            step_context["gradients"].append(gradient.copy())
        return gradient

    def external_sender(message, attack, rng, *args, **kwargs):
        index = step_context["sender"]
        step_context["sender"] += 1
        return adversarial[step_context["step"] - 1, index].copy()

    def trace(frame, event, arg):
        if event == "return" and frame.f_code is module.norm_subgradient.__code__:
            step_context["norm_returns"].append(np.asarray(arg).copy())
        elif event == "return" and frame.f_code is module.rsa_step.__code__:
            step_context["penalty"] = frame.f_locals["penalty"].copy()
            # Read the original update operands; this value is never fed back.
            step_context["regularizer_gradient"] = frame.f_locals["weight_decay"] * frame.f_locals["state"].master
        return trace

    module.softmax_gradient = quadratic_gradient
    module.attack_message = external_sender
    previous_trace = sys.gettrace()
    try:
        for step, alpha in enumerate(case["parameters"]["step_sizes"], start=1):
            step_context.clear()
            step_context.update(step=step, sender=0, gradients=[], norm_returns=[])
            sys.settrace(trace)
            state, received = module.rsa_step(
                state, batches, alpha=alpha, lam=case["parameters"]["lambda"],
                weight_decay=1.0, norm=norm, byzantine=nb, attack="same_value",
                rng=np.random.default_rng(0),
            )
            sys.settrace(previous_trace)
            norms = step_context["norm_returns"]
            if len(norms) != 2 * workers:
                raise RuntimeError("Unexpected norm call structure; refuse to infer missing observations.")
            data[step, "worker_loss_gradients_before_update"] = np.asarray(step_context["gradients"])
            data[step, "worker_penalty_subgradients_before_update"] = np.asarray(norms[:nr])
            data[step, "byzantine_master_subgradients_before_update"] = np.asarray(norms[workers + nr:])
            data[step, "master_penalty_subgradient_sum_before_update"] = step_context["penalty"]
            data[step, "master_regularizer_gradient_before_update"] = step_context["regularizer_gradient"]
            data[step, "regular_workers"] = state.locals[:nr].copy()
            data[step, "master"] = state.master.copy()
    finally:
        sys.settrace(previous_trace)
        module.softmax_gradient = saved_gradient
        module.attack_message = saved_attack
    return emit_case(case, data, diagnostics={
        "objective_boundary": "softmax_gradient replaced by the supplied quadratic gradient; original / workers retained",
        "byzantine_boundary": "attack_message returns prescribed external sender vectors",
        "actual_step_sizes": case["parameters"]["step_sizes"],
        "algorithm_functions_replaced": False,
    })


def reasflow_case(module, case):
    master, regular, centers, adversarial = input_arrays(case)
    nr, dimension = regular.shape
    nb = adversarial.shape[1]
    workers = nr + nb
    # Preserve original model allocation, dimensionality and float32 dtype.
    # A vector is embedded in row zero; all other coordinates stay zero.
    partitions = [(np.full((1, dimension - 1), i, dtype=np.float32), np.zeros(1, dtype=int))
                  for i in range(workers)]
    test_x = np.zeros((1, dimension - 1), dtype=np.float32)
    test_y = np.zeros(1, dtype=int)
    requested = case["parameters"]["step_sizes"]
    actual = [requested[0] / np.sqrt(i + 1.0) for i in range(len(requested))]
    mismatch = next((i for i, (left, right) in enumerate(zip(actual, requested))
                     if not np.isclose(left, right, atol=0, rtol=1e-14)), None)
    # Only the initial valid prefix is executed. Never reset the training loop to
    # simulate a forbidden schedule, and never overwrite its local alpha.
    iterations = len(requested) if mismatch is None else mismatch
    data = {}
    context = {"initialized": False, "rounds": {}}
    saved_gradient = module.softmax_gradient
    saved_attack = module._attack_message
    source_lines, first_line = inspect.getsourcelines(module.run_training)
    initial_line = first_line + next(i for i, line in enumerate(source_lines) if "for step in range(iterations):" in line)
    completed_line = first_line + next(i for i, line in enumerate(source_lines) if "local_regular =" in line)

    def training_frame(frame):
        while frame is not None:
            if frame.f_code is module.run_training.__code__:
                return frame
            frame = frame.f_back
        raise RuntimeError("Observation boundary was called outside run_training.")

    def quadratic_gradient(x, y, theta, l2):
        frame = training_frame(sys._getframe().f_back)
        worker = frame.f_locals["worker_id"]
        step = frame.f_locals["step"] + 1
        gradient = np.zeros_like(theta)
        if worker < nr:
            gradient[0, :dimension] = theta[0, :dimension] - centers[worker]
            context["rounds"][step]["gradients"].append(gradient[0, :dimension].copy())
        return gradient

    def external_sender(true_value, *, attack, rng, **kwargs):
        frame = training_frame(sys._getframe().f_back)
        worker = frame.f_locals["worker_id"]
        if worker < nr:
            # Honest sender behavior is the original attack helper.
            return saved_attack(true_value, attack=attack, rng=rng, **kwargs)
        message = np.zeros_like(true_value)
        message[0, :dimension] = adversarial[frame.f_locals["step"], worker - nr]
        return message

    def trace(frame, event, arg):
        if frame.f_code is module.run_training.__code__ and event == "line":
            if frame.f_lineno == initial_line and not context["initialized"]:
                frame.f_locals["theta"][0, :dimension] = master
                frame.f_locals["local"][:nr, 0, :dimension] = regular
                data[0, "master"] = frame.f_locals["theta"][0, :dimension].copy()
                data[0, "regular_workers"] = frame.f_locals["local"][:nr, 0, :dimension].copy()
                context["initialized"] = True
            if "step" in frame.f_locals:
                step = frame.f_locals["step"] + 1
                if step not in context["rounds"]:
                    context["rounds"][step] = {
                        "gradients": [], "norm_returns": [],
                        "old_master": frame.f_locals["theta"][0, :dimension].copy(),
                    }
                if frame.f_lineno == completed_line:
                    record = context["rounds"][step]
                    data[step, "worker_loss_gradients_before_update"] = np.asarray(record["gradients"])
                    data[step, "worker_penalty_subgradients_before_update"] = np.asarray(record["norm_returns"][:nr])
                    data[step, "byzantine_master_subgradients_before_update"] = np.asarray(record["norm_returns"][workers + nr:])
                    data[step, "master_penalty_subgradient_sum_before_update"] = frame.f_locals["penalty"][0, :dimension].copy()
                    data[step, "master_regularizer_gradient_before_update"] = frame.f_locals["l2"] * record["old_master"]
                    data[step, "regular_workers"] = frame.f_locals["local"][:nr, 0, :dimension].copy()
                    data[step, "master"] = frame.f_locals["theta"][0, :dimension].copy()
        elif event == "return" and frame.f_code is module.norm_subgradient.__code__:
            origin = training_frame(frame.f_back)
            step = origin.f_locals["step"] + 1
            context["rounds"][step]["norm_returns"].append(np.asarray(arg)[0, :dimension].copy())
        return trace

    module.softmax_gradient = quadratic_gradient
    module._attack_message = external_sender
    previous_trace = sys.gettrace()
    try:
        sys.settrace(trace)
        module.run_training(
            partitions, test_x, test_y,
            method={1: "rsa_l1", 2: "rsa_l2", "infinity": "rsa_linf"}[case["parameters"]["p"]],
            iterations=iterations, seed=0, num_byzantine=nb, attack="same", batch_size=1,
            alpha0=requested[0], l2=1.0, lam=case["parameters"]["lambda"], eval_every=1,
        )
    finally:
        sys.settrace(previous_trace)
        module.softmax_gradient = saved_gradient
        module._attack_message = saved_attack
    reason = None if mismatch is None else (
        f"Blocked from step {mismatch + 1}: run_training fixes alpha=alpha0/sqrt(step+1); "
        f"requested {requested[mismatch]}, implementation would use {actual[mismatch]}. "
        "Only the matching prefix was run; remaining observations are intentionally absent."
    )
    return emit_case(case, data, "ok" if reason is None else "blocked", reason, diagnostics={
        "objective_boundary": "softmax_gradient replaced by supplied quadratic gradient; original / workers retained",
        "byzantine_boundary": "_attack_message returns prescribed external sender vectors; honest branch unchanged",
        "initial_state_boundary": "values injected once into original float32 arrays, first row; all other coordinates zero",
        "executed_step_sizes": actual[:iterations],
        "requested_step_sizes": requested,
        "algorithm_functions_replaced": False,
    })


def main(variant):
    workspace = Path(os.environ["OPTIREPRO_WORKSPACE"]).resolve()
    public = Path(os.environ["OPTIREPRO_CASES"])
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(workspace))
    module = importlib.import_module("rsa_repro.rsa" if variant == "codex" else "rsa_reproduction.algorithms")
    function = codex_case if variant == "codex" else reasflow_case
    results = []
    for case in json.loads(public.read_text())["cases"]:
        try:
            results.append(function(module, case))
        except Exception as exc:
            results.append({"id": case["id"], "observations": [], "status": "blocked",
                            "reason": f"{type(exc).__name__}: {exc}"})
    print("OPTIREPRO_OBSERVATIONS=" + json.dumps({"cases": results}, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main('reasflow')
