"""Local v0.3 calibration and bounded experiment proposals. No LLM, network or hardware.

Two deliberately separate routes:
- concentration_sigma_um: fit sigma**2 = a + b*t with a,b >= 0;
- geometric_track_width_um: empirical PolynomialFeatures/StandardScaler/Ridge.
A supplied holdout partition is NEVER used to choose or fit coefficients.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import platform
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import lsq_linear
from scipy.spatial import Delaunay, QhullError
from scipy.stats import qmc
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from _core import finite_number, file_hash, load_json, write_json

OBSERVABLES = {
    "concentration_sigma_um": [("elapsed_time_s", "s")],
    "geometric_track_width_um": [("speed_mm_s", "mm/s"), ("delay_s", "s")],
}
ROOT = Path(__file__).resolve().parents[1]


class InputError(ValueError):
    """Malformed or incompatible evidence: stop, rather than fabricate missing input."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise InputError(message)


def text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def safe_child(base: Path, rel: Any) -> Path:
    need(text(rel), "A relative dataset_file is required")
    root = base.resolve()
    target = (root / rel).resolve()
    need(not Path(rel).is_absolute() and target.is_relative_to(root), "dataset_file must stay within the task folder")
    return target


def validate_task(task: Any) -> None:
    need(isinstance(task, dict), "Task must be an object")
    need(task.get("schema_version") == "0.3", "schema_version must be 0.3")
    for key in ("task_id", "material_pair", "context_id", "dataset_file"):
        need(text(task.get(key)), f"Missing {key}")
    need(task.get("process") == "hybrid-vpp-diw", "Unsupported process")
    need(task.get("mode") in {"offline_demo", "research"}, "Explicit mode required")
    need(task.get("data_kind") in {"synthetic_demo", "measured", "public_measured"}, "Explicit data_kind required")
    need((task["mode"] == "offline_demo") == (task["data_kind"] == "synthetic_demo"), "Synthetic/demo and research/measured provenance must not be mixed")
    need(isinstance(task.get("fixed_conditions"), dict) and bool(task["fixed_conditions"]), "Record fixed_conditions")
    need(task.get("observable") in OBSERVABLES, "Unsupported observable: do not turn track width into concentration sigma, strength or cure conversion")
    obs = task["observable"]
    measure = task.get("measurement_definition", {})
    need(isinstance(measure, dict) and measure.get("quantity") == obs, "Measurement quantity must match observable; no automatic sigma-width mapping")
    for key in ("method", "scale_source_ref"):
        need(text(measure.get(key)), f"measurement_definition.{key} required")
    need(measure.get("unit") == "um", "Response must be explicitly in um; convert before import and record the conversion")
    need(task.get("group_column") in {"sample_id", "batch_id"}, "group_column must be sample_id or batch_id")
    perm = task.get("allow", {})
    need(isinstance(perm, dict) and all(perm.get(k) is False for k in ("hardware_commands", "dedicated_simulation_software")), "Hardware and dedicated simulation permissions must be false")
    factors = task.get("factors")
    need(isinstance(factors, list) and len(factors) == len(OBSERVABLES[obs]), "Wrong number of factors for observable")
    for f, (name, unit) in zip(factors, OBSERVABLES[obs]):
        need(isinstance(f, dict) and f.get("name") == name and f.get("unit") == unit, f"Factor order/units must match {OBSERVABLES[obs]}")
        bounds = f.get("bounds")
        need(isinstance(bounds, list) and len(bounds) == 2 and all(finite_number(v) for v in bounds), f"Finite bounds required for {name}")
        need(0 <= bounds[0] < bounds[1] and (name != "speed_mm_s" or bounds[0] > 0), f"Invalid bounds for {name}")
        need(finite_number(f.get("step")) and 0 < f["step"] <= bounds[1] - bounds[0], f"Positive attainable step required for {name}")
        need((bounds[1] - bounds[0]) / f["step"] <= 10000, "Grid resolution too fine; revise step")
        need(text(f.get("source_ref")), f"Bounds/step source_ref required for {name}")
    criteria = task.get("acceptance", {})
    need(isinstance(criteria, dict), "acceptance must be object")
    for name in ("max_cv_rmse_um", "max_holdout_rmse_um"):
        need(finite_number(criteria.get(name)) and criteria[name] > 0, f"Declare {name}; it is a task-specific gate, not a universal threshold")
    need(type(criteria.get("require_beats_constant")) is bool, "acceptance.require_beats_constant must be boolean")
    n = task.get("next_trials")
    need(type(n) is int and 1 <= n <= 20, "next_trials must be 1..20")
    seed = task.get("seed")
    need(type(seed) is int and 0 <= seed < 2**32, "seed must be a nonnegative 32-bit integer")
    need(finite_number(task.get("target_um")) and task["target_um"] > 0, "Positive target_um required")
    need(task.get("bounds_review_status") in {"needs_review", "reviewed"}, "bounds_review_status must be explicit")
    baseline = task.get("baseline_parameters", {})
    need(isinstance(baseline, dict) and set(baseline) == {f["name"] for f in factors}, "baseline_parameters must name exactly the factors")
    for f in factors:
        v = baseline[f["name"]]
        need(finite_number(v) and f["bounds"][0] <= v <= f["bounds"][1], "Baseline outside supplied bounds")
        need(abs((v-f["bounds"][0])/f["step"] - round((v-f["bounds"][0])/f["step"])) < 1e-7, "Baseline must lie on the declared attainable parameter grid")
    if obs == "geometric_track_width_um":
        model = task.get("empirical_model", {})
        need(isinstance(model, dict) and type(model.get("degree")) is int and model["degree"] in (1, 2), "Empirical polynomial degree must be preset to 1 or 2")
        need(finite_number(model.get("ridge_alpha")) and model["ridge_alpha"] > 0, "Positive preset ridge_alpha required")
    else:
        ass = task.get("assumptions", {})
        need(isinstance(ass, dict) and all(ass.get(k) is True for k in ("homogeneous_1d", "unbounded_domain", "constant_diffusivity", "pre_gel_only", "advection_ignored")), "Diffusion assumptions must be explicitly confirmed")
        need(task.get("time_reference") == "elapsed_since_reference_profile", "Diffusion time reference must be explicit")


def load_measurements(task: dict, path: Path) -> tuple[list[dict], dict]:
    need(path.is_file(), "Measurement CSV does not exist")
    need(path.stat().st_size <= 10_000_000, "Measurement CSV exceeds 10 MB")
    fields = [f["name"] for f in task["factors"]]
    required = {"record_id", "sample_id", "batch_id", "material_pair", "context_id", "data_kind", "source_ref", "partition", "response_um", *fields}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        need(len(set(columns)) == len(columns), "Duplicate CSV headers")
        need(required.issubset(columns), "Missing CSV columns: " + ", ".join(sorted(required-set(columns))))
        raw = list(reader)
    need(len(raw) <= 10000, "Too many input rows")
    ids, samples, group_parts = set(), {}, defaultdict(set)
    aggregates: dict[tuple, list] = defaultdict(list)
    for index, row in enumerate(raw, 2):
        need(None not in row, f"CSV row {index}: extra fields")
        need(all(text(row.get(k)) for k in required), f"CSV row {index}: missing required value")
        need(row["record_id"] not in ids, "Duplicate record_id")
        ids.add(row["record_id"])
        for k in ("material_pair", "context_id", "data_kind"):
            need(row[k] == task[k], f"CSV row {index}: {k} mismatch; select a single context")
        need(row["partition"] in {"fit", "holdout"}, "partition must be fit or holdout")
        numeric = {}
        for k in [*fields, "response_um"]:
            try:
                v = float(row[k])
            except (ValueError, TypeError) as exc:
                raise InputError(f"CSV row {index}: invalid {k}") from exc
            need(math.isfinite(v), f"CSV row {index}: nonfinite {k}")
            numeric[k] = v
        need(numeric["response_um"] > 0, "Measured sigma/width must be positive")
        for f in task["factors"]:
            need(f["bounds"][0] <= numeric[f["name"]] <= f["bounds"][1], "Measurement outside task bounds; review instead of silently dropping")
        sid = row["sample_id"]
        sample_ctx = (row["batch_id"], row["partition"])
        need(sid not in samples or samples[sid] == sample_ctx, "One sample crosses batch or fit/holdout partitions")
        samples[sid] = sample_ctx
        group = row[task["group_column"]]
        group_parts[group].add(row["partition"])
        need(len(group_parts[group]) == 1, "Group leakage: same independent group in fit and holdout")
        key = (sid, row["batch_id"], row["partition"], *(numeric[k] for k in fields))
        aggregates[key].append((numeric["response_um"], row["record_id"], row["source_ref"]))
    output = []
    for key, vals in aggregates.items():
        output.append({"sample_id": key[0], "batch_id": key[1], "partition": key[2],
                       "group_id": key[0] if task["group_column"] == "sample_id" else key[1],
                       **dict(zip(fields, key[3:])), "response_um": float(np.mean([v[0] for v in vals])),
                       "n_repeated_measurements": len(vals), "record_ids": [v[1] for v in vals],
                       "source_refs": sorted({v[2] for v in vals})})
    if task["observable"] == "geometric_track_width_um":
        conditions = defaultdict(set)
        for row in output:
            conditions[row["sample_id"]].add(tuple(row[f] for f in fields))
        need(all(len(v) == 1 for v in conditions.values()), "Empirical v0.3 requires one parameter combination per independent sample; define a repeated-measures model otherwise")
    summary = {"n_raw_rows": len(raw), "n_aggregated_rows": len(output), "n_samples": len(samples),
               "aggregation": "mean of repeated measurements of same sample at same settings; not extra replicates",
               "group_column": task["group_column"],
               "partitions": {p: {"n_rows": sum(r["partition"] == p for r in output),
                                   "groups": sorted({r["group_id"] for r in output if r["partition"] == p})} for p in ("fit", "holdout")}}
    return output, summary


def arrays(rows: list[dict], task: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (np.asarray([[r[f["name"]] for f in task["factors"]] for r in rows], dtype=float).reshape(-1, len(task["factors"])),
            np.asarray([r["response_um"] for r in rows], dtype=float),
            np.asarray([r["group_id"] for r in rows], dtype=str))


def group_weights(groups: np.ndarray) -> np.ndarray:
    counts = Counter(groups)
    weights = np.asarray([1/counts[g] for g in groups], dtype=float)
    return weights * len(weights) / weights.sum()


def error_metrics(y: np.ndarray, p: np.ndarray, groups: np.ndarray) -> dict:
    need(len(y) > 0 and len(y) == len(p), "Cannot score empty/mismatched arrays")
    need(np.isfinite(p).all(), "Nonfinite prediction")
    w = group_weights(groups)
    e = p-y
    return {"group_weighted_rmse_um": float(np.sqrt(np.average(e*e, weights=w))),
            "group_weighted_mae_um": float(np.average(np.abs(e), weights=w)),
            "max_abs_error_um": float(np.max(np.abs(e))),
            "n_groups": len(set(groups)), "n_rows": len(y)}


def fit_model(task: dict, x: np.ndarray, y: np.ndarray, groups: np.ndarray) -> tuple[Any, dict]:
    w = group_weights(groups)
    if task["observable"] == "concentration_sigma_um":
        design = np.column_stack([np.ones(len(x)), x[:, 0]])
        need(np.linalg.matrix_rank(design) == 2 and len(np.unique(x[:, 0])) >= 3, "Diffusion calibration needs at least three distinct elapsed times")
        target = y*y
        need(np.isfinite(target).all(), "Variance overflow")
        aw, yw = design*np.sqrt(w[:, None]), target*np.sqrt(w)
        unconstrained = np.linalg.lstsq(aw, yw, rcond=None)[0]
        need(unconstrained[1] >= -1e-8, "Variance decreases with time: constant nonnegative diffusion model is incompatible")
        fit = lsq_linear(aw, yw, bounds=([0.0, 0.0], [np.inf, np.inf]), method="trf")
        need(bool(fit.success) and np.isfinite(fit.x).all(), "Bounded variance fit failed")
        a, b = map(float, fit.x)
        summary = {"type": "bounded_diffusion_variance_regression", "a_um2": a, "b_um2_s": b,
                   "sigma0_um": math.sqrt(a), "diffusivity_um2_s": b/2,
                   "fit_loss": "group-balanced squared residuals in variance units; diagnostics reported in sigma units",
                   "formula": "sigma^2 = a + b*t", "physical_parameters_verified": False,
                   "initial_profile_time_zero_observed": bool(np.any(np.isclose(x[:, 0], 0))),
                   "boundary_parameter": bool(a < 1e-8 or b < 1e-8)}
        return (a, b), summary
    cfg = task["empirical_model"]
    poly = PolynomialFeatures(degree=cfg["degree"], include_bias=False)
    design = poly.fit_transform(x)
    need(np.isfinite(design).all(), "Polynomial features overflow")
    need(np.linalg.matrix_rank(np.column_stack([np.ones(len(x)), design])) == design.shape[1]+1, "Insufficient independent parameter combinations for the declared empirical response surface")
    model = make_pipeline(PolynomialFeatures(degree=cfg["degree"], include_bias=False), StandardScaler(), Ridge(alpha=cfg["ridge_alpha"]))
    model.fit(x, y, standardscaler__sample_weight=w, ridge__sample_weight=w)
    summary = {"type": "empirical_polynomial_ridge", "degree": cfg["degree"], "ridge_alpha": cfg["ridge_alpha"],
               "selection": "degree and alpha specified before evaluation; no hyperparameter search on holdout",
               "feature_names": model[0].get_feature_names_out([f["name"] for f in task["factors"]]).tolist(),
               "scaler_mean": model[1].mean_.tolist(), "scaler_scale": model[1].scale_.tolist(),
               "coef_standardized": model[2].coef_.tolist(), "intercept": float(model[2].intercept_),
               "is_physical_diffusion_model": False, "diffusivity_inferred": False}
    return model, summary


def predict(model: Any, x: np.ndarray, task: dict) -> np.ndarray:
    if task["observable"] == "concentration_sigma_um":
        a, b = model
        y = np.sqrt(a + b*x[:, 0])
    else:
        y = model.predict(x)
    need(np.isfinite(y).all(), "Nonfinite model output")
    return y


def in_training_domain(train_x: np.ndarray, query: np.ndarray) -> np.ndarray:
    if len(train_x) == 0:
        return np.zeros(len(query), dtype=bool)
    lo, hi = train_x.min(axis=0), train_x.max(axis=0)
    inside_box = np.all((query >= lo-1e-10) & (query <= hi+1e-10), axis=1)
    if train_x.shape[1] == 1:
        return inside_box
    scale = np.where(hi > lo, hi-lo, 1)
    try:
        hull = Delaunay(np.unique((train_x-lo)/scale, axis=0))
        return inside_box & (hull.find_simplex((query-lo)/scale, tol=1e-10) >= 0)
    except QhullError:
        return np.zeros(len(query), dtype=bool)


def calibrate(task: dict, rows: list[dict]) -> tuple[dict, Any | None]:
    fit_rows = [r for r in rows if r["partition"] == "fit"]
    held_rows = [r for r in rows if r["partition"] == "holdout"]
    x, y, groups = arrays(fit_rows, task)
    hx, hy, hg = arrays(held_rows, task)
    result = {"status": "needs_calibration_data", "numerical_fit_performed": False, "model_usable_for_proposals": False,
              "reasons": [], "fit_groups": sorted(set(groups)), "holdout_groups": sorted(set(hg)),
              "holdout_used_for_fitting": False, "holdout_used_for_hyperparameter_selection": False,
              "uncertainty": {"type": "not_quantified", "note": "CV/holdout RMSE is an error diagnostic, not a pointwise confidence or prediction interval"}}
    if len(set(groups)) < 3:
        result["reasons"].append("Need at least three independent fit groups for this prototype's grouped diagnostics; this is not a sample-size guarantee")
        return result, None
    try:
        folds, oof, base = [], np.zeros(len(y)), np.zeros(len(y))
        for no, (tr, va) in enumerate(GroupKFold(n_splits=min(5, len(set(groups)))).split(x, y, groups), 1):
            m, _ = fit_model(task, x[tr], y[tr], groups[tr])
            oof[va] = predict(m, x[va], task)
            dummy = DummyRegressor(strategy="mean").fit(x[tr], y[tr], sample_weight=group_weights(groups[tr]))
            base[va] = dummy.predict(x[va])
            folds.append({"fold": no, "fit_groups": sorted(set(groups[tr])), "validation_groups": sorted(set(groups[va])),
                          "fit_row_indices": tr.tolist(), "validation_row_indices": va.tolist()})
        cv, cv_base = error_metrics(y, oof, groups), error_metrics(y, base, groups)
        model, info = fit_model(task, x, y, groups)
        result.update(status="fit_pending_review", numerical_fit_performed=True, model=info, cv=cv, constant_baseline_cv=cv_base, folds=folds,
                      oof_rows=[{"sample_id": r["sample_id"], "group_id": r["group_id"], "measured_um": float(v),
                                 "out_of_fold_prediction_um": float(p), "constant_baseline_um": float(b)} for r,v,p,b in zip(fit_rows,y,oof,base)],
                      training_metrics=error_metrics(y,predict(model,x,task),groups))
        checks = {
            "cv_within_preset_tolerance": cv["group_weighted_rmse_um"] <= task["acceptance"]["max_cv_rmse_um"],
            "cv_beats_constant_if_required": not task["acceptance"]["require_beats_constant"] or cv["group_weighted_rmse_um"] < cv_base["group_weighted_rmse_um"],
            "has_two_independent_holdout_groups": len(set(hg)) >= 2,
            "holdout_within_training_domain": False,
            "holdout_within_preset_tolerance": False,
            "positive_fit_and_cv_predictions": bool(np.all(oof > 0) and np.all(predict(model,x,task) > 0)),
        }
        if len(hy):
            hp = predict(model,hx,task)
            result["holdout"] = error_metrics(hy,hp,hg)
            result["holdout_rows"] = [{"sample_id":r["sample_id"],"group_id":r["group_id"], "measured_um":float(v),"prediction_um":float(p),
                                        "inside_training_domain":bool(ok)} for r,v,p,ok in zip(held_rows,hy,hp,in_training_domain(x,hx))]
            checks["holdout_within_training_domain"] = bool(in_training_domain(x,hx).all())
            checks["holdout_within_preset_tolerance"] = result["holdout"]["group_weighted_rmse_um"] <= task["acceptance"]["max_holdout_rmse_um"] and bool(np.all(hp>0))
        result["checks"] = checks
        result["reasons"] = [k for k,v in checks.items() if not v]
        result["model_usable_for_proposals"] = all(checks.values())
        result["status"] = "numerical_gates_passed_not_physical_validation" if all(checks.values()) else "diagnostics_failed_or_incomplete"
        return result, model
    except (InputError, ValueError, np.linalg.LinAlgError) as exc:
        result["reasons"].append(str(exc))
        return result, None


def candidate_grid(task: dict) -> np.ndarray:
    axes = [np.round(f["bounds"][0] + np.arange(int(math.floor((f["bounds"][1]-f["bounds"][0])/f["step"]+1e-9))+1)*f["step"], 12) for f in task["factors"]]
    count = math.prod(len(a) for a in axes)
    if count <= 5000:
        return np.asarray(list(itertools.product(*axes)), dtype=float)
    # Space-filling subset at attainable values, never clip an out-of-range DOE.
    sample = qmc.LatinHypercube(d=len(axes), rng=np.random.default_rng(task["seed"])).random(2048)
    pts = np.column_stack([a[np.minimum((sample[:, j]*len(a)).astype(int),len(a)-1)] for j,a in enumerate(axes)])
    return np.unique(pts, axis=0)


def propose(task: dict, rows: list[dict], calibration: dict, model: Any | None) -> dict:
    candidates = candidate_grid(task)
    fit_rows = [r for r in rows if r["partition"] == "fit"]
    x, _, _ = arrays(fit_rows,task)
    domain = in_training_domain(x,candidates)
    usable = bool(calibration["model_usable_for_proposals"] and model is not None)
    predictions = np.full(len(candidates),np.nan)
    if usable and domain.any():
        predictions[domain] = predict(model,candidates[domain],task)
    good = domain & np.isfinite(predictions) & (predictions>0)
    baseline = np.asarray([task["baseline_parameters"][f["name"]] for f in task["factors"]],dtype=float)
    lower = np.asarray([f["bounds"][0] for f in task["factors"]]); span = np.asarray([f["bounds"][1]-f["bounds"][0] for f in task["factors"]])
    chosen: list[tuple[np.ndarray,str,str]] = []
    # Reserve a same-run baseline replication, rather than counting old data as a fresh control.
    remaining = task["next_trials"]-1
    if remaining and good.any():
        idx = int(np.flatnonzero(good)[np.argmin(np.abs(predictions[good]-task["target_um"]))])
        if not np.allclose(candidates[idx],baseline,atol=1e-10,rtol=0):
            chosen.append((candidates[idx],"predicted_target_candidate","Smallest absolute target error among tested-grid model predictions within training convex hull; not a verified optimum"))
            remaining -= 1
    refs = [*x,baseline,*[p for p,_,_ in chosen]]
    while remaining>0:
        distances = np.min(np.linalg.norm((candidates[:,None,:]-np.asarray(refs)[None,:,:])/span,axis=2),axis=1)
        for pt,_,_ in chosen:
            distances[np.all(np.isclose(candidates,pt,atol=1e-10,rtol=0),axis=1)] = -1
        distances[np.all(np.isclose(candidates,baseline,atol=1e-10,rtol=0),axis=1)] = -1
        if np.max(distances)<0:
            break
        idx=int(np.argmax(distances)); pt=candidates[idx]
        chosen.append((pt,"coverage_or_calibration","Maximin coverage in normalized parameter space; not Bayesian information gain or evidence of safety"))
        refs.append(pt); remaining-=1
    chosen.append((baseline,"baseline_replication","New independent reference specimen at the declared baseline; do not replace with an old measurement"))
    rng=np.random.default_rng(task["seed"])
    trials=[]
    for order,index in enumerate(rng.permutation(len(chosen)),1):
        point,purpose,reason=chosen[int(index)]
        inside=bool(in_training_domain(x,point[None,:])[0])
        value=float(predict(model,point[None,:],task)[0]) if usable and inside else None
        if value is not None and value<=0:value=None
        trials.append({"trial_id":f"T{index+1:02d}","run_order":order,"purpose":purpose,
                       "parameters":{f["name"]:float(v) for f,v in zip(task["factors"],point)},
                       "predicted_response_um":value,"inside_training_domain":inside,
                       "prediction_interval":None,"rationale":reason,
                       "state":"suggested","human_approval_required":True,"physical_feasibility":"not_verified",
                       "required_measurements":[task["observable"],"actual_timing_and_settings","sample_id","batch_id","measurement_method"],
                       "data_kind":task["data_kind"]})
    return {"status":"candidate_plan_not_executed" if usable else "calibration_plan_without_validated_predictions",
            "predicted_target_selection_performed":bool(any(r["purpose"]=="predicted_target_candidate" for r in trials)),
            "candidate_count":len(candidates),"candidates_inside_training_domain":int(domain.sum()),
            "sampling":"attainable bounded grid, or quantized Latin-hypercube subset when grid exceeds 5000",
            "budget_requested":task["next_trials"],"trials":trials,
            "baseline_found_in_data":bool(any(np.allclose(pt,baseline,atol=1e-10,rtol=0) for pt in x)),
            "no_claims":["No physical improvement demonstrated","No guaranteed feasible curing/interface outcome","No global optimum or calibrated prediction interval","Not a sample-size/power calculation"],
            "candidate_rows":[{**{f["name"]:float(v) for f,v in zip(task["factors"],pt)},
                               "inside_training_domain":bool(inside),"predicted_response_um":float(p) if ok else None}
                              for pt,inside,p,ok in zip(candidates,domain,predictions,good)]}


def analyse(task: dict, rows: list[dict]) -> dict:
    cal, model = calibrate(task,rows)
    plan = propose(task,rows,cal,model)
    return {"version":"0.3.0","task_id":task["task_id"],"mode":task["mode"],"data_kind":task["data_kind"],
            "observable":task["observable"],"status":plan["status"],"calibration":cal,"experiment_plan":plan,
            "physical_printing_performed":False,"physical_validation_performed":False,"hardware_commands_sent":False,
            "dedicated_simulation_software_called":False,"external_llm_api_called":False,"live_github_search_in_this_run":False,
            "runtime_routing":"deterministic observable/data gates among previously reviewed local adapters; not autonomous GitHub discovery",
            "calibration_review_status":"needs_scientific_review","measured_improvement":None,
            "not_predicted":["cure_conversion","interface_strength","fatigue_life","device_performance"],
            "python_version":platform.python_version()}


def write_csv(path: Path, rows: list[dict], fields: list[str] | None=None) -> None:
    if not rows and not fields:return
    with path.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields or list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def summary_md(result: dict) -> str:
    cal=result["calibration"];plan=result["experiment_plan"]
    lines=["# v0.3 标定与实验规划结果","",f"模式：**{result['mode']} / {result['data_kind']}**。",
           "合成数据只用于软件演示；数值检查通过不代表真实材料模型已验证。","",f"观测量：`{result['observable']}`；状态：`{result['status']}`。","",
           "## 模型检查",f"数值拟合：{cal['numerical_fit_performed']}；可用于候选排序：{cal['model_usable_for_proposals']}。",
           "留出数据未用于拟合或超参数选择；重复测量先聚合，验证按独立组划分。",
           "交叉验证误差不是每个候选点的置信区间；本版本不输出±精度。"]
    for k,label in (("cv","分组交叉验证"),("holdout","预留验证"),("constant_baseline_cv","常数基准CV")):
        if k in cal:lines.append(f"{label}：RMSE={cal[k]['group_weighted_rmse_um']:.6g} μm；MAE={cal[k]['group_weighted_mae_um']:.6g} μm。")
    if cal["reasons"]:lines.extend(["","未通过或缺失："]+[f"- {r}" for r in cal["reasons"]])
    lines.extend(["","## 下一轮试验（待人工确认）","","| 次序 | 编号 | 目的 | 参数 | 预测值（μm） |","|---|---|---|---|---|"])
    for row in plan["trials"]:
        v=row["predicted_response_um"]
        lines.append(f"| {row['run_order']} | {row['trial_id']} | {row['purpose']} | {json.dumps(row['parameters'],ensure_ascii=False)} | {'不提供' if v is None else format(v,'.6g')} |")
    lines.extend(["","覆盖性试验采用距离准则，不宣称最优信息增益。超出训练凸包不提供预测。",
                  "没有新实际打印/测试，因此不能报告成品性能改善。真实设备范围仍须人工核查。",
                  "`measurement_import_template.csv`为空白表头模板，不包含编造的新测量。", ""])
    return "\n".join(lines)


def run(task_path: Path, out: Path) -> dict:
    need(not out.exists(), "Output exists; use a new run directory")
    task=load_json(task_path)
    validate_task(task)
    data_path=safe_child(task_path.parent,task["dataset_file"])
    rows,checks=load_measurements(task,data_path)
    result=analyse(task,rows)
    result["input_hashes"]={"task_sha256":file_hash(task_path),"dataset_sha256":file_hash(data_path)}
    result["data_check"]=checks
    import importlib.metadata as md
    result["environment"]={name:md.version(name) for name in ("numpy","scipy","scikit-learn")}
    out.mkdir(parents=True)
    write_json(out/"result.json",result)
    write_json(out/"task_snapshot.json",task)
    write_json(out/"calibration.json",result["calibration"])
    write_json(out/"aggregated_measurements.json",rows)
    write_json(out/"data_check.json",checks)
    write_csv(out/"candidate_predictions.csv",result["experiment_plan"]["candidate_rows"])
    trials=[{"trial_id":r["trial_id"],"run_order":r["run_order"],"purpose":r["purpose"],**r["parameters"],
             "predicted_response_um":r["predicted_response_um"],"state":r["state"],"data_kind":r["data_kind"]} for r in result["experiment_plan"]["trials"]]
    write_csv(out/"next_experiments.csv",trials)
    write_csv(out/"measurement_import_template.csv",[],["record_id","sample_id","batch_id","trial_id","material_pair","context_id","data_kind","source_ref",*[f["name"] for f in task["factors"]],"response_um"])
    (out/"summary.md").write_text(summary_md(result),encoding="utf-8")
    events=[{"stage":"input","action":"validate_and_aggregate","tool":"calibration_planning.load_measurements","status":"complete"},
            {"stage":"calibration","selected_skill":"measured-response-calibration","upstream":"K-Dense-AI/scientific-agent-skills:scikit-learn","tool":"calibration_planning.calibrate","status":result["calibration"]["status"]},
            {"stage":"planning","selected_skill":"bounded-experiment-planning","upstream":"K-Dense-AI/scientific-agent-skills:experimental-design","tool":"calibration_planning.propose","status":result["experiment_plan"]["status"]}]
    for event in events:
        event.update(run_mode=task["mode"],source_data_kind=task["data_kind"],python_file_sha256=file_hash(Path(__file__)),upstream_helper_executed=False)
        if "selected_skill" in event:
            event["local_skill_sha256"]=file_hash(ROOT/"skills"/event["selected_skill"]/"SKILL.md")
    (out/"events.jsonl").write_text("".join(json.dumps(e,ensure_ascii=False)+"\n" for e in events),encoding="utf-8")
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    try:
        result=run(args.task,args.out)
    except (ValueError,OSError,TypeError,KeyError) as exc:
        print(json.dumps({"status":"blocked","error":str(exc)},ensure_ascii=False))
        return 2
    print(json.dumps({"status":result["status"],"observable":result["observable"],"data_kind":result["data_kind"],"out":str(args.out)},ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
