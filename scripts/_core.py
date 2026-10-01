"""Small, deterministic local helpers. No network, LLM, or equipment calls."""
from __future__ import annotations
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

FACTOR_UNITS = {"speed_mm_s": "mm/s", "delay_s": "s"}
KINDS = {"synthetic_demo", "measured", "public_measured"}


def load_json(path: Path) -> Any:
    if path.stat().st_size > 2_000_000:
        raise ValueError("JSON file exceeds the 2 MB starter limit")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_task(task: Any) -> list[str]:
    if not isinstance(task, dict):
        return ["Task must be a JSON object"]
    errors: list[str] = []
    if task.get("schema_version") != "0.1":
        errors.append("schema_version must be 0.1")
    for field in ("task_id", "material_pair", "dataset_file"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            errors.append(f"{field} is required and must be a nonempty string")
    if task.get("process") != "hybrid-vpp-diw" or task.get("geometry") != "single-track":
        errors.append("Starter supports only hybrid-vpp-diw / single-track tasks")
    if task.get("mode") not in {"offline_demo", "research"}:
        errors.append("mode must be offline_demo or research")
    if task.get("data_kind") not in KINDS:
        errors.append("data_kind must explicitly identify the data source type")
    if task.get("mode") == "research" and task.get("data_kind") == "synthetic_demo":
        errors.append("Synthetic data cannot be declared a research-mode measured run")
    objective = task.get("objective")
    if not isinstance(objective, dict):
        errors.append("objective is required")
    else:
        if objective.get("metric") != "track_width_um" or objective.get("unit") != "um":
            errors.append("Starter response must be track_width_um in um")
        if not finite_number(objective.get("target")) or objective["target"] <= 0:
            errors.append("target must be a finite positive number")
    factors = task.get("factors")
    if not isinstance(factors, list) or len(factors) != 2:
        errors.append("Exactly two named factors are required in this starter")
    else:
        names: list[str] = []
        for factor in factors:
            if not isinstance(factor, dict):
                errors.append("Every factor must be an object")
                continue
            name = factor.get("name")
            if name not in FACTOR_UNITS:
                errors.append(f"Unsupported factor: {name}")
            else:
                names.append(name)
                if factor.get("unit") != FACTOR_UNITS[name]:
                    errors.append(f"Wrong unit for {name}; expected {FACTOR_UNITS[name]}")
            bounds = factor.get("bounds")
            if not isinstance(bounds, list) or len(bounds) != 2 or not all(finite_number(v) for v in bounds):
                errors.append(f"Finite lower/upper bounds required for {name}")
            elif bounds[0] < 0 or bounds[0] >= bounds[1] or (name == "speed_mm_s" and bounds[0] == 0):
                errors.append(f"Invalid bounds for {name}")
        if len(set(names)) != 2:
            errors.append("Factors must contain speed_mm_s and delay_s exactly once")
    if not isinstance(task.get("fixed_conditions"), dict) or not task["fixed_conditions"]:
        errors.append("fixed_conditions must explicitly record the fixed context")
    budget = task.get("budget")
    n = budget.get("next_trials") if isinstance(budget, dict) else None
    if type(n) is not int or not 1 <= n <= 20:
        errors.append("budget.next_trials must be an integer from 1 to 20")
    permissions = task.get("allow")
    if not isinstance(permissions, dict) or any(permissions.get(k) is not False for k in ("hardware_commands", "dedicated_simulation_software")):
        errors.append("Hardware commands and dedicated simulation software must both be disabled")
    return errors


def validate_rows(task: dict, rows: list[dict[str, str]], columns: list[str]) -> dict:
    required = {"record_id", "sample_id", "batch_id", "material_pair", "data_kind", "source_ref", *FACTOR_UNITS, "track_width_um"}
    missing = sorted(required - set(columns))
    errors: list[str] = [f"Missing CSV column: {c}" for c in missing]
    if not rows:
        errors.append("Dataset has no rows")
    if errors:
        return {"valid": False, "errors": errors, "n_rows": len(rows)}
    if len(columns) != len(set(columns)):
        errors.append("Duplicate CSV column names")
    seen: set[str] = set()
    bounds = {f["name"]: f["bounds"] for f in task["factors"]}
    samples: set[str] = set()
    for index, row in enumerate(rows, 2):
        prefix = f"CSV row {index}"
        if None in row:
            errors.append(f"{prefix}: extra values beyond the header")
        for key in ("record_id", "sample_id", "batch_id", "source_ref"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                errors.append(f"{prefix}: missing {key}")
        record = row.get("record_id", "")
        if record in seen:
            errors.append(f"{prefix}: duplicate record_id {record}")
        seen.add(record)
        samples.add(row.get("sample_id", ""))
        for key in ("material_pair", "data_kind"):
            if row.get(key) != task[key]:
                errors.append(f"{prefix}: {key} differs from task; do not pool these rows")
        for field in (*FACTOR_UNITS, "track_width_um"):
            try:
                value = float(row.get(field, ""))
            except (ValueError, TypeError):
                errors.append(f"{prefix}: {field} is not numeric")
                continue
            if not math.isfinite(value):
                errors.append(f"{prefix}: {field} is not finite")
            elif field == "track_width_um":
                if value <= 0:
                    errors.append(f"{prefix}: track width must be positive")
            elif not bounds[field][0] <= value <= bounds[field][1]:
                errors.append(f"{prefix}: {field} outside task bounds; review instead of silent extrapolation")
    return {"valid": not errors, "errors": errors, "n_rows": len(rows), "n_distinct_sample_ids": len(samples - {""})}


def validate_bundle(task_path: Path) -> dict:
    task_path = task_path.resolve()
    task = load_json(task_path)
    errors = validate_task(task)
    report = {"schema_version": "0.1", "status": "blocked" if errors else "checking", "valid": False,
              "errors": errors, "scientific_validity": "not_assessed", "prediction_performed": False,
              "input_hashes": {"task_sha256": file_hash(task_path)}}
    if errors:
        return report
    rel = Path(task["dataset_file"])
    data_path = (task_path.parent / rel).resolve()
    if rel.is_absolute() or not data_path.is_relative_to(task_path.parent):
        report.update(status="blocked", errors=["dataset_file must be inside the task folder; path traversal is disallowed"])
        return report
    if not data_path.is_file():
        report.update(status="blocked", errors=["Referenced CSV file does not exist"])
        return report
    if data_path.stat().st_size > 10_000_000:
        report.update(status="blocked", errors=["CSV exceeds the 10 MB starter limit"])
        return report
    with data_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        rows = list(reader)
    checks = validate_rows(task, rows, columns)
    report.update(checks)
    report.update(status="format_checks_passed" if checks["valid"] else "blocked",
                  mode=task["mode"], data_kind=task["data_kind"], task_id=task["task_id"],
                  warnings=["Passing format checks does not validate a material model or establish parameter effects.",
                            "Images/rows from one specimen must not be counted as independent replicate specimens."])
    if task["data_kind"] == "synthetic_demo":
        report["warnings"].append("SYNTHETIC SOFTWARE TEST DATA. No real printing or scientific validation.")
    report["input_hashes"]["data_sha256"] = file_hash(data_path)
    return report


QUERIES = {
    "literature": ["literature evidence extraction SKILL.md", "scientific literature search claim source mapping", "VPP DIW process evidence skill"],
    "model": ["symbolic equations numerical computation skill", "surrogate modelling skill physical units"],
    "experiment_design": ["experimental design SKILL.md", "constrained optimisation experimental planning skill"],
    "measurement": ["direct ink writing image measurement skill", "track width binary image measurement"],
    "validation": ["grouped model validation statistical analysis SKILL.md"],
}


def search_plan(registry: dict, stage: str) -> dict:
    if stage not in QUERIES:
        raise ValueError(f"Unknown stage {stage}")
    candidates = [dict(c) for c in registry.get("candidates", []) if c.get("stage") == stage]
    return {"schema_version": "0.1", "stage": stage, "status": "offline_search_plan_only", "queries_to_run": QUERIES[stage],
            "seed_candidates": candidates, "selected_candidate_id": None, "live_search_executed": False,
            "remote_skill_executed": False,
            "next_actions": ["Use an authorised live GitHub search tool or review a trusted cache.",
                             "Read complete candidate instructions and executable resources; compare task fit and dependencies.",
                             "Obtain execution approval and pin reviewed versions.",
                             "Run actual authorised tools, validate outputs, then record a decision."],
            "limitation": "This script prepares discovery. It does not perform GitHub search or decide that any candidate is safe."}
