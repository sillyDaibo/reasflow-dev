#!/usr/bin/env python3
"""Validate the machine-readable gate that must pass before experiments run."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
ALLOWED_SOURCES = {
    "paper",
    "knowledge_card",
    "local_choice",
    "user",
    "not_applicable",
}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def text(value: Any) -> str:
    return str(value or "").strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_path(workspace: Path, raw: str) -> Path | None:
    if not raw:
        return None
    candidate = Path(raw)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (workspace / candidate).resolve()
    )
    try:
        resolved.relative_to(workspace)
    except ValueError:
        return None
    return resolved


def validate_sources(
    items: list[Any],
    label: str,
    errors: list[str],
    accepted_paper_keys: set[str],
) -> None:
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object.")
            continue
        source = text(item.get("source"))
        if source not in ALLOWED_SOURCES:
            errors.append(
                f"{label}[{index}].source must be one of "
                f"{sorted(ALLOWED_SOURCES)}."
            )
        if source == "paper" and not text(item.get("evidence_location")):
            errors.append(
                f"{label}[{index}] uses paper evidence without evidence_location."
            )
        if source == "paper":
            paper_key = text(item.get("paper_key"))
            if not paper_key:
                errors.append(
                    f"{label}[{index}] uses paper evidence without paper_key."
                )
            elif paper_key not in accepted_paper_keys:
                errors.append(
                    f"{label}[{index}].paper_key was not accepted by the "
                    "task-relevance gate."
                )


def validate_applicability(
    value: dict[str, Any],
    label: str,
    required_ready_fields: tuple[str, ...],
    ready: bool,
    errors: list[str],
) -> None:
    applicable = value.get("applicable")
    if not isinstance(applicable, bool):
        errors.append(f"{label}.applicable must be true or false.")
        return
    if applicable and ready:
        for field in required_ready_fields:
            if not text(value.get(field)):
                errors.append(f"{label}.{field} is required when ready.")
    if not applicable and not text(value.get("reason")):
        errors.append(f"{label}.reason is required when not applicable.")


def validate_required_object_fields(
    items: list[Any],
    label: str,
    required_fields: tuple[str, ...],
    ready: bool,
    errors: list[str],
) -> None:
    if not ready:
        return
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        for field in required_fields:
            if not text(item.get(field)):
                errors.append(f"{label}[{index}].{field} is required when ready.")


def validate_nonempty_strings(
    items: list[Any],
    label: str,
    ready: bool,
    errors: list[str],
) -> None:
    if not ready:
        return
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}[{index}] must be a non-empty string when ready.")


def validate_entrypoint(
    entrypoint: str,
    implementation: Path | None,
    implementation_text: str,
    ready: bool,
    errors: list[str],
) -> None:
    if not ready:
        return
    if not entrypoint:
        errors.append("algorithm.entrypoint is required when ready.")
        return
    match = re.fullmatch(
        r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*):([A-Za-z_]\w*)",
        entrypoint,
    )
    if match is None:
        errors.append("algorithm.entrypoint must use module:callable format.")
        return
    if implementation is None or not implementation.is_file():
        return
    module_name, symbol_name = match.groups()
    if module_name.rsplit(".", 1)[-1] != implementation.stem:
        errors.append(
            "algorithm.entrypoint module must match algorithm.implementation_path."
        )
        return
    try:
        tree = ast.parse(implementation_text, filename=str(implementation))
    except SyntaxError as exc:
        errors.append(f"Algorithm implementation is not valid Python: {exc.msg}.")
        return
    top_level_callables = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if symbol_name not in top_level_callables:
        errors.append(
            f"algorithm.entrypoint callable does not exist: {entrypoint}"
        )


def validate_contract(
    contract: dict[str, Any],
    workspace: Path,
    *,
    require_ready: bool = False,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    status = text(contract.get("status"))
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}.")
    if status not in {"ready", "blocked"}:
        errors.append("status must be ready or blocked.")
    if require_ready and status != "ready":
        errors.append("Execution requires status=ready.")
    ready = status == "ready"

    algorithm = as_dict(contract.get("algorithm"))
    experiment = as_dict(contract.get("experiment"))
    relevance = as_dict(contract.get("evidence_relevance"))
    accepted_paper_keys = {
        text(item)
        for item in as_list(relevance.get("accepted_paper_keys"))
        if text(item)
    }
    blockers = as_list(contract.get("unresolved_blockers"))
    if ready and blockers:
        errors.append("A ready contract cannot contain unresolved_blockers.")
    if status == "blocked" and not blockers:
        errors.append("A blocked contract must explain unresolved_blockers.")

    implementation_path = text(algorithm.get("implementation_path"))
    implementation = workspace_path(workspace, implementation_path)
    implementation_text = ""
    if implementation is None:
        errors.append("algorithm.implementation_path must stay inside workspace.")
    elif not implementation.is_file():
        errors.append(f"Algorithm implementation does not exist: {implementation_path}")
    else:
        actual_sha = sha256_file(implementation)
        expected_sha = text(algorithm.get("implementation_sha256"))
        if ready and not expected_sha:
            errors.append("algorithm.implementation_sha256 is required when ready.")
        elif expected_sha and expected_sha != actual_sha:
            errors.append("algorithm.implementation_sha256 does not match the file.")
        implementation_text = implementation.read_text(
            encoding="utf-8", errors="replace"
        )
        placeholder = bool(
            re.search(
                r"NotImplementedError|deliberately fixed input|"
                r"\bTODO\b.{0,80}\bimplement|placeholder",
                implementation_text,
                re.IGNORECASE | re.DOTALL,
            )
        )
        if ready and placeholder:
            errors.append("Algorithm implementation still contains a placeholder.")
        elif placeholder:
            warnings.append("Algorithm implementation contains a placeholder.")

    state_variables = as_list(algorithm.get("state_variables"))
    update_rules = as_list(algorithm.get("update_rules"))
    validate_entrypoint(
        text(algorithm.get("entrypoint")),
        implementation,
        implementation_text,
        ready,
        errors,
    )
    if ready and not state_variables:
        errors.append("algorithm.state_variables must be non-empty when ready.")
    if ready and not update_rules:
        errors.append("algorithm.update_rules must be non-empty when ready.")
    validate_nonempty_strings(
        state_variables,
        "algorithm.state_variables",
        ready,
        errors,
    )
    validate_sources(
        update_rules,
        "algorithm.update_rules",
        errors,
        accepted_paper_keys,
    )
    validate_required_object_fields(
        update_rules,
        "algorithm.update_rules",
        ("name", "formula"),
        ready,
        errors,
    )

    validate_applicability(
        as_dict(algorithm.get("proximal_or_projection")),
        "algorithm.proximal_or_projection",
        ("rule",),
        ready,
        errors,
    )
    validate_applicability(
        as_dict(algorithm.get("privacy")),
        "algorithm.privacy",
        ("sensitivity", "noise", "accounting"),
        ready,
        errors,
    )

    datasets = as_list(experiment.get("datasets"))
    baselines = as_list(experiment.get("baselines"))
    metrics = as_list(experiment.get("metrics"))
    seeds = as_list(experiment.get("seeds"))
    commands = as_list(experiment.get("commands"))
    validate_sources(
        datasets,
        "experiment.datasets",
        errors,
        accepted_paper_keys,
    )
    validate_sources(
        baselines,
        "experiment.baselines",
        errors,
        accepted_paper_keys,
    )
    validate_sources(
        metrics,
        "experiment.metrics",
        errors,
        accepted_paper_keys,
    )
    validate_required_object_fields(
        datasets,
        "experiment.datasets",
        ("name",),
        ready,
        errors,
    )
    validate_required_object_fields(
        baselines,
        "experiment.baselines",
        ("name",),
        ready,
        errors,
    )
    validate_required_object_fields(
        metrics,
        "experiment.metrics",
        ("name", "computation"),
        ready,
        errors,
    )
    if ready and not datasets:
        errors.append("experiment.datasets must be non-empty when ready.")
    if ready and not baselines:
        errors.append("experiment.baselines must be non-empty when ready.")
    if ready and not metrics:
        errors.append("experiment.metrics must be non-empty when ready.")
    if ready and not seeds:
        errors.append("experiment.seeds must be non-empty when ready.")
    if ready and not commands:
        errors.append("experiment.commands must be non-empty when ready.")
    if ready:
        for index, seed in enumerate(seeds):
            if not isinstance(seed, int) or isinstance(seed, bool):
                errors.append(
                    f"experiment.seeds[{index}] must be an integer when ready."
                )
    validate_nonempty_strings(
        commands,
        "experiment.commands",
        ready,
        errors,
    )
    budget = as_dict(experiment.get("budget"))
    if ready:
        for field in ("unit", "limit", "fairness_rule"):
            if not text(budget.get(field)):
                errors.append(f"experiment.budget.{field} is required when ready.")

    return {
        "schema_version": SCHEMA_VERSION,
        "valid": not errors,
        "status": status,
        "ready_for_execution": ready and not errors,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".")
    parser.add_argument(
        "contract_path",
        nargs="?",
        help="Contract path relative to the workspace.",
    )
    parser.add_argument(
        "--contract",
        default="Alg_Exp/document/execution_contract.json",
    )
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    contract_path = workspace_path(
        workspace,
        args.contract_path or args.contract,
    )
    if contract_path is None or not contract_path.is_file():
        print(
            json.dumps(
                {
                    "valid": False,
                    "ready_for_execution": False,
                    "errors": ["Execution contract file is missing or outside workspace."],
                    "warnings": [],
                },
                indent=2,
            )
        )
        return 1
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "valid": False,
                    "ready_for_execution": False,
                    "errors": [f"Cannot read execution contract: {exc}"],
                    "warnings": [],
                },
                indent=2,
            )
        )
        return 1
    if not isinstance(contract, dict):
        print(
            json.dumps(
                {
                    "valid": False,
                    "ready_for_execution": False,
                    "errors": ["Execution contract must be a JSON object."],
                    "warnings": [],
                },
                indent=2,
            )
        )
        return 1

    result = validate_contract(
        contract,
        workspace,
        require_ready=args.require_ready,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
