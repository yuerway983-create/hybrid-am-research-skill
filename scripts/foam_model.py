"""发泡 FDM 分级泡沫的独立简化计算；不调用 LLM、商业求解器或设备。"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import platform
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.optimize import lsq_linear
from scipy.spatial import Delaunay, QhullError

from _core import file_hash, finite_number, load_json, write_json

VERSION = "foam-0.1"
OBSERVABLES = {"compression_modulus_MPa", "compression_yield_strength_MPa"}
UNITS = {
    "temperature_C": "degC", "flow_ratio": "1",
    "total_relative_density": "1", "microscale_porosity_fraction": "1",
    "wall_thickness_um": "um", "mean_pore_diameter_um": "um", "response_MPa": "MPa",
}
FEATURES = {"porosity_partition_interaction", "temperature_C", "inverse_scale_ratio"}
SCALES = {"micro", "macro", "hierarchical"}
SOURCE = "https://doi.org/10.1063/5.0301777"
FACTOR_LABELS = {"total_relative_density": "总相对密度", "microscale_porosity_fraction": "微观孔隙占全部孔隙的份额",
                 "temperature_C": "打印温度", "flow_ratio": "切片出料倍率"}
DIRECTION_LABELS = {"increasing": "随输入增大而上升", "decreasing": "随输入增大而下降",
                    "non_monotonic": "非单调变化", "flat": "在数值精度内近似不变"}
CHECK_LABELS = {"cv_error": "训练条件交叉验证误差", "holdout_error": "独立留出误差",
                "beats_constant_cv": "优于常数预测", "nondegradation_holdout": "留出结果不退化",
                "density_eta_domain": "分级密度／孔隙份额覆盖", "extra_feature_bounds": "修正特征范围",
                "refinement_beats_baseline": "修正优于原模型", "monoscale_density_domain": "单尺度留出密度覆盖",
                "hierarchical_within_monoscale_calibration_domain": "两级标定向分级结构转移的密度覆盖"}


class InputError(ValueError):
    """输入或可识别性不符合计算条件。"""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise InputError(message)


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def positive(value: Any) -> bool:
    return finite_number(value) and value > 0


def safe_child(base: Path, relative: Any) -> Path:
    need(nonempty(relative), "dataset_file 必须是相对路径")
    root = base.resolve()
    target = (root / relative).resolve()
    need(not Path(relative).is_absolute() and target.is_relative_to(root), "数据路径不能离开任务目录")
    return target


def hierarchy_from_density_eta(relative_density: float, eta: float) -> dict:
    need(finite_number(relative_density) and 0 < relative_density <= 1, "总相对密度必须在 (0, 1] 内")
    need(finite_number(eta) and 0 <= eta <= 1, "微观孔隙占总孔隙的比例 eta 必须在 [0, 1] 内")
    need(relative_density < 1 or eta == 0, "完全致密时 eta 无定义，请使用规范值 0")
    macro = relative_density + eta * (1 - relative_density)
    return {
        "total_relative_density": float(relative_density),
        "microscale_porosity_fraction": float(eta),
        "macro_relative_density": float(macro),
        "micro_relative_density": float(relative_density / macro),
    }


def powerlaw_prediction(relative_density: float, eta: float, base_property_MPa: float,
                        micro_params: dict, macro_params: dict) -> float:
    state = hierarchy_from_density_eta(relative_density, eta)
    need(positive(base_property_MPa), "基体性能必须是有限正数，单位 MPa")
    for params in (micro_params, macro_params):
        need(isinstance(params, dict) and positive(params.get("coefficient"))
             and positive(params.get("exponent")), "两级模型均需有限正系数和指数")
    value = base_property_MPa * micro_params["coefficient"] * macro_params["coefficient"]
    value *= state["micro_relative_density"] ** micro_params["exponent"]
    value *= state["macro_relative_density"] ** macro_params["exponent"]
    need(positive(value), "幂律预测发生数值溢出或下溢")
    return float(value)


def validate_task(task: Any) -> None:
    need(isinstance(task, dict), "任务必须是 JSON 对象")
    need(task.get("schema_version") == VERSION, f"schema_version 必须是 {VERSION}")
    for field in ("task_id", "material_id", "context_id", "dataset_file"):
        need(nonempty(task.get(field)), f"缺少 {field}")
    need(task.get("process") == "foaming-fdm", "本模块只支持声明为 foaming-fdm 的任务")
    need(task.get("observable") in OBSERVABLES, "只支持压缩模量或初始压缩屈服强度；不预测吸能或寿命")
    need(task.get("mode") in {"offline_demo", "research"}, "必须明确 mode")
    need(task.get("data_kind") in {"synthetic_demo", "measured", "public_measured"}, "必须明确数据来源类别")
    need((task["mode"] == "offline_demo") == (task["data_kind"] == "synthetic_demo"), "合成演示与真实研究来源不能混用")
    need(task.get("units") == UNITS, "必须明确所有列的单位，程序不进行隐式换算")
    need(isinstance(task.get("fixed_conditions"), dict) and bool(task["fixed_conditions"]), "必须记录固定实验及测试条件")
    measurement = task.get("measurement_definition", {})
    need(isinstance(measurement, dict) and measurement.get("quantity") == task["observable"]
         and measurement.get("unit") == "MPa", "测量定义和 MPa 单位必须匹配响应")
    need(nonempty(measurement.get("method")) and nonempty(measurement.get("source_ref")), "测量方法及来源必填")
    base = task.get("base_property", {})
    need(isinstance(base, dict) and positive(base.get("value")) and base.get("unit") == "MPa"
         and nonempty(base.get("source_ref")), "需要有来源的正基体性能，单位 MPa；不提供材料默认值")
    expected = "synthetic_demo" if task["mode"] == "offline_demo" else "user_calibration"
    need(base.get("origin") == expected, "基体性能来源必须与演示或实测标定模式一致")
    assumptions = task.get("assumptions", {})
    need(isinstance(assumptions, dict) and assumptions.get("two_scale_structure") is True
         and assumptions.get("equivalent_microporous_material") is True, "必须明确两级孔结构与微观等效材料假设")
    review = task.get("scale_separation", {})
    need(isinstance(review, dict) and positive(review.get("min_wall_to_pore_ratio"))
         and nonempty(review.get("source_ref")), "尺度分离阈值必须事先声明并注明来源，非通用常数")
    need(review.get("review_status") in {"needs_review", "reviewed"}, "必须注明尺度假设审核状态")
    permissions = task.get("allow", {})
    need(isinstance(permissions, dict) and all(permissions.get(key) is False for key in
         ("hardware_commands", "dedicated_simulation_software")), "不得启用硬件或商业求解器")
    model = task.get("powerlaw", {})
    need(isinstance(model, dict), "powerlaw 必须是对象")
    for key in ("coefficient_bounds", "exponent_bounds"):
        bounds = model.get(key)
        need(isinstance(bounds, list) and len(bounds) == 2 and all(positive(v) for v in bounds)
             and bounds[0] < bounds[1], f"{key} 必须为递增有限正区间")
    process = task.get("process_model", {})
    need(isinstance(process, dict) and type(process.get("degree")) is int
         and process["degree"] in (1, 2), "密度响应面阶数必须预设为 1 或 2")
    for key in ("ridge_alpha", "max_cv_density_rmse", "max_holdout_density_rmse"):
        need(positive(process.get(key)), f"process_model.{key} 必须为有限正数")
    refinement = task.get("refinement", {})
    need(isinstance(refinement, dict), "refinement 必须是对象")
    features = refinement.get("features")
    need(isinstance(features, list) and 1 <= len(features) <= 2
         and all(isinstance(x, str) and x in FEATURES for x in features)
         and len(set(features)) == len(features), "修正项必须是白名单中 1～2 个不重复特征，不执行生成表达式")
    need(positive(refinement.get("ridge_alpha")) and nonempty(refinement.get("rationale")), "修正强度与选择理由必须预先记录")
    need(refinement.get("proposal_origin") in {"host_selected", "operator_selected", "synthetic_fixture"}, "必须说明候选修正的选择者")
    need(isinstance(refinement.get("source_refs"), list) and bool(refinement["source_refs"])
         and all(nonempty(x) for x in refinement["source_refs"]), "候选机理需有引用；引用不证明机理成立")
    acceptance = task.get("acceptance", {})
    need(isinstance(acceptance, dict), "acceptance 必须是对象")
    for key in ("max_cv_rmse_MPa", "max_holdout_rmse_MPa"):
        need(positive(acceptance.get(key)), f"需预先声明 {key}")
    need(finite_number(acceptance.get("max_degradation_MPa")) and acceptance["max_degradation_MPa"] >= 0,
         "max_degradation_MPa 必须为有限非负值")
    need(type(acceptance.get("require_beats_baseline")) is bool, "require_beats_baseline 必须为布尔值")


def load_measurements(task: dict, path: Path) -> tuple[list[dict], dict]:
    need(path.is_file() and path.stat().st_size <= 10_000_000, "CSV 不存在或超过 10 MB")
    identities = {"record_id", "sample_id", "condition_id", "batch_id", "material_id",
                  "context_id", "data_kind", "source_ref", "partition", "scale"}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        need(len(columns) == len(set(columns)) and identities.union(UNITS).issubset(columns), "CSV 列缺失或重复")
        raw = list(reader)
    need(bool(raw) and len(raw) <= 20000, "CSV 必须含 1～20000 条记录")
    records, partitions, conditions, samples = set(), {}, {}, defaultdict(list)
    for index, row in enumerate(raw, 2):
        prefix = f"CSV 第 {index} 行"
        need(None not in row and all(nonempty(row.get(key)) for key in identities), f"{prefix}: 标识缺失或列数错误")
        need(row["record_id"] not in records, f"{prefix}: record_id 重复")
        records.add(row["record_id"])
        for key in ("material_id", "context_id", "data_kind"):
            need(row[key] == task[key], f"{prefix}: {key} 与任务不符")
        need(row["scale"] in SCALES and row["partition"] in {"train", "holdout"}, f"{prefix}: scale 或 partition 非法")
        for key in UNITS:
            try:
                row[key] = float(row[key])
            except (TypeError, ValueError) as exc:
                raise InputError(f"{prefix}: {key} 需要有限数值") from exc
            need(math.isfinite(row[key]), f"{prefix}: {key} 非有限数值")
        state = hierarchy_from_density_eta(row["total_relative_density"], row["microscale_porosity_fraction"])
        row.update(state)
        need(row["temperature_C"] > -273.15 and positive(row["flow_ratio"]), f"{prefix}: 温度或出料倍率非法")
        need(positive(row["response_MPa"]) and positive(row["wall_thickness_um"])
             and row["mean_pore_diameter_um"] >= 0, f"{prefix}: 性能、壁厚或孔径非法")
        if row["micro_relative_density"] < 1:
            need(positive(row["mean_pore_diameter_um"]), f"{prefix}: 存在微观孔隙时需提供实测平均孔径")
        else:
            need(row["mean_pore_diameter_um"] == 0, f"{prefix}: 无微观孔隙时平均孔径必须为 0")
        if row["scale"] == "micro":
            need(row["microscale_porosity_fraction"] == 1 and row["total_relative_density"] < 1,
                 f"{prefix}: 单微观尺度数据必须 eta=1 且非完全致密")
        if row["scale"] == "macro":
            need(row["microscale_porosity_fraction"] == 0, f"{prefix}: 单宏观尺度数据必须 eta=0")
        for key in ("sample_id", "condition_id", "batch_id"):
            identity = (key, row[key])
            need(identity not in partitions or partitions[identity] == row["partition"],
                 f"{prefix}: {key} 跨训练／留出分区，存在泄漏")
            partitions[identity] = row["partition"]
        # 条件是共同制备设置；独立样品的实测密度和尺寸允许自然变化。
        settings = (row["scale"], row["temperature_C"], row["flow_ratio"])
        need(row["condition_id"] not in conditions or conditions[row["condition_id"]] == settings,
             f"{prefix}: 同一 condition_id 的制备设置或尺度不一致")
        conditions[row["condition_id"]] = settings
        samples[row["sample_id"]].append(row)
    aggregated = []
    for sample_id, repeats in sorted(samples.items()):
        first = repeats[0]
        for row in repeats[1:]:
            for key in ("condition_id", "batch_id", "scale", "partition", *[k for k in UNITS if k != "response_MPa"]):
                need(row[key] == first[key], f"样品 {sample_id} 的技术重复设置不一致")
        sample = {k: v for k, v in first.items() if k not in {"record_id", "source_ref"}}
        sample["response_MPa"] = float(np.mean([r["response_MPa"] for r in repeats]))
        sample["technical_repeats"] = len(repeats)
        sample["source_refs"] = sorted({r["source_ref"] for r in repeats})
        aggregated.append(sample)
    counts = {}
    for scale in sorted(SCALES):
        for part in ("train", "holdout"):
            group_count = len({r["condition_id"] for r in aggregated if r["scale"] == scale and r["partition"] == part})
            minimum = 4 if scale == "hierarchical" and part == "train" else 3 if part == "train" else 2
            need(group_count >= minimum, f"{scale}/{part} 至少需要 {minimum} 个不同条件")
            counts[f"{scale}/{part}"] = group_count
    return aggregated, {"valid": True, "raw_records": len(raw), "samples": len(aggregated),
                        "conditions_by_scale_and_partition": counts,
                        "technical_repeats_aggregated": True, "group_column": "condition_id",
                        "independent_batch_or_physical_validity_certified": False}


def group_weights(rows: list[dict]) -> np.ndarray:
    counts = Counter(row["condition_id"] for row in rows)
    return np.asarray([1 / counts[row["condition_id"]] for row in rows], dtype=float)


def error_metrics(rows: list[dict], predictions: list[float] | np.ndarray, response: str = "response_MPa") -> dict:
    actual = np.asarray([row[response] for row in rows], dtype=float)
    predicted = np.asarray(predictions, dtype=float)
    need(actual.ndim == predicted.ndim == 1 and len(actual) == len(predicted) and len(actual) > 0
         and np.isfinite(actual).all() and np.isfinite(predicted).all(), "评分需匹配且有限的实测与预测")
    weights = group_weights(rows)
    with np.errstate(over="ignore", invalid="ignore"):
        delta = predicted - actual
        rmse = float(np.sqrt(np.average(delta ** 2, weights=weights)))
    need(math.isfinite(rmse), "评分误差发生数值溢出")
    return {"rmse": rmse,
            "mae": float(np.average(np.abs(delta), weights=weights)),
            "n_conditions": len({r["condition_id"] for r in rows}), "n_samples": len(rows)}


def fit_powerlaw(rows: list[dict], base_property_MPa: float, scale: str,
                 coefficient_bounds: list[float], exponent_bounds: list[float]) -> dict:
    need(scale in {"micro", "macro"} and positive(base_property_MPa), "需要单尺度数据与正基体性能")
    for bounds in (coefficient_bounds, exponent_bounds):
        need(isinstance(bounds, (list, tuple)) and len(bounds) == 2 and all(positive(v) for v in bounds)
             and bounds[0] < bounds[1], "幂律边界必须为递增有限正区间")
    subset = [r for r in rows if r["scale"] == scale]
    need(len({r["condition_id"] for r in subset}) >= 2, "幂律拟合至少需要两个条件")
    need(all(finite_number(r.get("total_relative_density")) and 0 < r["total_relative_density"] <= 1
             and positive(r.get("response_MPa")) for r in subset), "幂律标定需要合法密度和有限正响应")
    densities = np.asarray([r["total_relative_density"] for r in subset], dtype=float)
    response = np.asarray([r["response_MPa"] for r in subset], dtype=float)
    design = np.column_stack([np.ones(len(subset)), np.log(densities)])
    need(np.linalg.matrix_rank(design) == 2, "单尺度密度变化不足，幂律参数不可识别")
    weights = np.sqrt(group_weights(subset))
    # 对数相减避免有限正数相除时溢出／下溢。
    result = lsq_linear(design * weights[:, None], (np.log(response) - math.log(base_property_MPa)) * weights,
                        bounds=([math.log(coefficient_bounds[0]), exponent_bounds[0]],
                                [math.log(coefficient_bounds[1]), exponent_bounds[1]]))
    need(result.success and np.isfinite(result.x).all(), "有界幂律标定失败")
    return {"coefficient": float(math.exp(result.x[0])), "exponent": float(result.x[1]),
            "fit_scale": scale, "fit_objective": "condition_equal_weighted_log_least_squares",
            "n_train_conditions": len({r["condition_id"] for r in subset}),
            "training_density_bounds": [float(densities.min()), float(densities.max())]}


def feature_value(row: dict, name: str) -> float:
    eta = row["microscale_porosity_fraction"]
    if name == "porosity_partition_interaction":
        return eta * (1 - eta)
    if name == "temperature_C":
        return row[name]
    if name == "inverse_scale_ratio":
        return row["mean_pore_diameter_um"] / row["wall_thickness_um"]
    state = hierarchy_from_density_eta(row["total_relative_density"], eta)
    if name == "log_micro_density":
        return math.log(state["micro_relative_density"])
    if name == "log_macro_density":
        return math.log(state["macro_relative_density"])
    raise InputError("未知修正特征")


def _fit_ridge(features: np.ndarray, target: np.ndarray, rows: list[dict], alpha: float) -> dict:
    weights = group_weights(rows)
    means = np.average(features, axis=0, weights=weights)
    deviations = np.sqrt(np.average((features - means) ** 2, axis=0, weights=weights))
    need(np.all(deviations > 1e-12), "候选特征缺少变化，无法识别修正")
    normal = (features - means) / deviations
    design = np.column_stack([np.ones(len(rows)), normal])
    need(np.linalg.matrix_rank(design) == design.shape[1], "候选特征相关或条件不足，无法识别修正")
    penalty = np.column_stack([np.zeros(features.shape[1]), np.eye(features.shape[1])]) * math.sqrt(alpha)
    root_weights = np.sqrt(weights)
    beta = np.linalg.lstsq(np.vstack([design * root_weights[:, None], penalty]),
                           np.concatenate([target * root_weights, np.zeros(features.shape[1])]), rcond=None)[0]
    need(np.isfinite(beta).all(), "修正拟合发生数值错误")
    return {"means": means.tolist(), "scales": deviations.tolist(), "coefficients": beta.tolist(), "ridge_alpha": alpha}


def _predict_linear(state: dict, features: np.ndarray) -> np.ndarray:
    normal = (features - np.asarray(state["means"])) / np.asarray(state["scales"])
    return np.column_stack([np.ones(len(features)), normal]) @ np.asarray(state["coefficients"])


def baseline_predict(row: dict, baseline: dict) -> float:
    return powerlaw_prediction(row["total_relative_density"], row["microscale_porosity_fraction"],
                               baseline["base_property_MPa"], baseline["micro"], baseline["macro"])


def fit_refinement(rows: list[dict], baseline: dict, features: list[str], alpha: float) -> dict:
    need(len({r["condition_id"] for r in rows}) >= len(features) + 1, "修正参数超过可用制备条件")
    x = np.asarray([[feature_value(r, name) for name in features] for r in rows])
    target = np.asarray([math.log(r["response_MPa"]) - math.log(baseline_predict(r, baseline)) for r in rows])
    return {"kind": "empirical_log_residual", "feature_names": features, **_fit_ridge(x, target, rows, alpha)}


def model_predict(rows: list[dict], baseline: dict, state: dict | None) -> list[float]:
    values = np.asarray([baseline_predict(row, baseline) for row in rows])
    if state is not None:
        x = np.asarray([[feature_value(r, name) for name in state["feature_names"]] for r in rows])
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            values *= np.exp(_predict_linear(state, x))
    need(np.isfinite(values).all() and np.all(values > 0), "预测发生数值溢出或下溢")
    return values.tolist()


def _folds(rows: list[dict]):
    for group in sorted({r["condition_id"] for r in rows}):
        yield [r for r in rows if r["condition_id"] != group], [r for r in rows if r["condition_id"] == group]


def _inside_hull(train_points: list[list[float]], point: list[float]) -> bool:
    points = np.unique(np.asarray(train_points, dtype=float), axis=0)
    if len(points) < 3 or np.linalg.matrix_rank(points - points.mean(axis=0)) < 2:
        return False
    centre, extent = points.mean(axis=0), np.ptp(points, axis=0)
    try:
        return bool(Delaunay((points - centre) / extent).find_simplex((np.asarray(point) - centre) / extent, tol=1e-9) >= 0)
    except QhullError:
        return False


def _process_features(rows: list[dict], degree: int, centres: list[float]) -> np.ndarray:
    t = np.asarray([(r["temperature_C"] - centres[0]) / 10 for r in rows])
    f = np.asarray([r["flow_ratio"] - centres[1] for r in rows])
    columns = [t, f] if degree == 1 else [t, f, t * t, t * f, f * f]
    return np.column_stack(columns)


def _fit_process(rows: list[dict], config: dict) -> dict:
    weights = group_weights(rows)
    centres = [float(np.average([r[name] for r in rows], weights=weights)) for name in ("temperature_C", "flow_ratio")]
    density = np.asarray([r["micro_relative_density"] for r in rows])
    need(np.all((density > 0) & (density < 1)), "密度响应面只标定非致密微观泡沫")
    target = np.log(density / (1 - density))
    return {"kind": "empirical_logit_density_response_surface", "degree": config["degree"],
            "centres": centres, **_fit_ridge(_process_features(rows, config["degree"], centres), target, rows, config["ridge_alpha"])}


def _predict_process(rows: list[dict], state: dict) -> list[float]:
    logits = _predict_linear(state, _process_features(rows, state["degree"], state["centres"]))
    # 两侧稳定计算，避免 exp 对大幅 logit 溢出；不对预测密度作隐式截断。
    result = np.empty_like(logits)
    positive_mask = logits >= 0
    result[positive_mask] = 1 / (1 + np.exp(-logits[positive_mask]))
    exponential = np.exp(logits[~positive_mask])
    result[~positive_mask] = exponential / (1 + exponential)
    need(np.isfinite(result).all() and np.all((result > 0) & (result < 1)), "密度响应面数值范围失效")
    return result.tolist()


def _direction_details(inputs: list[float], predictions: list[float]) -> dict:
    """只描述受支持、按输入排序的有限网格；不推断因果、显著性或最优点。"""
    need(len(inputs) >= 2 and len(set(inputs)) >= 2 and len(inputs) == len(predictions), "受支持扰动点不足")
    differences = np.diff(predictions)
    tolerance = 1e-9 * max(1., max(abs(v) for v in predictions))
    if np.all(np.abs(differences) <= tolerance):
        direction = "flat"
    elif np.all(differences >= -tolerance):
        direction = "increasing"
    elif np.all(differences <= tolerance):
        direction = "decreasing"
    else:
        direction = "non_monotonic"
    return {"direction": direction, "direction_numerical_tolerance": tolerance,
            "endpoint_predictions": [{"input_value": inputs[0], "predicted_value": predictions[0]},
                                     {"input_value": inputs[-1], "predicted_value": predictions[-1]}]}


def _process_analysis(rows: list[dict], config: dict) -> dict:
    train = [r for r in rows if r["scale"] == "micro" and r["partition"] == "train"]
    holdout = [r for r in rows if r["scale"] == "micro" and r["partition"] == "holdout"]
    try:
        state = _fit_process(train, config)
        cv_rows, cv_predictions = [], []
        for fit, test in _folds(train):
            cv_rows.extend(test)
            cv_predictions.extend(_predict_process(test, _fit_process(fit, config)))
        cv = error_metrics(cv_rows, cv_predictions, "micro_relative_density")
        test_predictions = _predict_process(holdout, state)
        test = error_metrics(holdout, test_predictions, "micro_relative_density")
        points = [[r["temperature_C"], r["flow_ratio"]] for r in train]
        support = [_inside_hull(points, [r["temperature_C"], r["flow_ratio"]]) for r in holdout]
        effects = []
        reference = dict(train[0])
        for i, key in enumerate(("temperature_C", "flow_ratio")):
            reference[key] = state["centres"][i]
        for key in ("temperature_C", "flow_ratio"):
            bounds = [min(r[key] for r in train), max(r[key] for r in train)]
            scenarios = [dict(reference, **{key: float(v)}) for v in np.linspace(*bounds, 21)]
            supported = [r for r in scenarios if _inside_hull(points, [r["temperature_C"], r["flow_ratio"]])]
            item = {"factor": key, "declared_training_range": bounds, "sampled_points_count": len(supported),
                    "fixed_reference": {name: reference[name] for name in ("temperature_C", "flow_ratio") if name != key}}
            if len(supported) >= 2 and len({r[key] for r in supported}) >= 2:
                values = _predict_process(supported, state)
                item.update(available=True, sampled_supported_range=[supported[0][key], supported[-1][key]],
                            density_span=max(values) - min(values),
                            **_direction_details([r[key] for r in supported], values))
            else:
                item.update(available=False, reason="受支持扰动点不足")
            effects.append(item)
        return {"available": True, "state": state, "cv": cv, "holdout": test,
                "training_domain_points": points, "holdout_inside_training_domain": support,
                "numerical_gates_passed": cv["rmse"] <= config["max_cv_density_rmse"]
                and test["rmse"] <= config["max_holdout_density_rmse"] and all(support),
                "sensitivity": sorted(effects, key=lambda item: item.get("density_span", -1), reverse=True),
                "causal_interpretation": False, "is_physical_foaming_simulation": False}
    except InputError as exc:
        return {"available": False, "numerical_gates_passed": False, "reason": str(exc)}


def _sensitivity(train: list[dict], baseline: dict, state: dict | None) -> list[dict]:
    reference = dict(train[0])
    weights = group_weights(train)
    for key in UNITS:
        if key != "response_MPa":
            reference[key] = float(np.average([r[key] for r in train], weights=weights))
    points = [[r["total_relative_density"], r["microscale_porosity_fraction"]] for r in train]
    feature_bounds = {name: [min(feature_value(r, name) for r in train), max(feature_value(r, name) for r in train)]
                      for name in state["feature_names"]} if state else {}

    def supported_scenario(row: dict) -> bool:
        if not _inside_hull(points, [row["total_relative_density"], row["microscale_porosity_fraction"]]):
            return False
        try:
            density_state = hierarchy_from_density_eta(row["total_relative_density"], row["microscale_porosity_fraction"])
        except InputError:
            # 扫描生成的无效组合不是原始测量；跳过情景，不放松真实输入检查。
            return False
        return all(baseline[scale]["training_density_bounds"][0] - 1e-10 <= density_state[f"{scale}_relative_density"]
                    <= baseline[scale]["training_density_bounds"][1] + 1e-10 for scale in ("micro", "macro")) \
            and all(bounds[0] - 1e-10 <= feature_value(row, name) <= bounds[1] + 1e-10
                    for name, bounds in feature_bounds.items())

    effects = []
    for key in ("total_relative_density", "microscale_porosity_fraction"):
        bounds = [min(r[key] for r in train), max(r[key] for r in train)]
        scenarios = [dict(reference, **{key: float(v)}) for v in np.linspace(*bounds, 31)]
        supported = [r for r in scenarios if supported_scenario(r)]
        item = {"factor": key, "unit": "1", "declared_training_range": bounds, "sampled_points_count": len(supported),
                "sampled_supported_values": [r[key] for r in supported],
                "fixed_reference": {k: reference[k] for k in UNITS if k not in {key, "response_MPa"}},
                "support_checks": ["density_eta_convex_hull", "monoscale_calibration_ranges", "refinement_feature_marginal_bounds"],
                "interpretation": "限定模型与固定参考下的单因素情景变化，非因果重要性或可执行打印计划"}
        if len(supported) >= 2 and len({r[key] for r in supported}) >= 2:
            values = model_predict(supported, baseline, state)
            item.update(available=True, sampled_supported_range=[supported[0][key], supported[-1][key]],
                        response_span_MPa=max(values) - min(values),
                        **_direction_details([r[key] for r in supported], values))
        else:
            item.update(available=False, reason="受支持扰动点不足")
        effects.append(item)
    return sorted(effects, key=lambda item: item.get("response_span_MPa", -1), reverse=True)


def _decision_summary(result: dict) -> dict:
    failed = [name for name, passed in result["numerical_checks"].items() if not passed]
    actions = []
    if result["data_kind"] == "synthetic_demo":
        actions.append("先接入真实测量及对应基体性能；合成误差不能支持实际材料改进。")
    for name in failed:
        if name in {"monoscale_density_domain", "hierarchical_within_monoscale_calibration_domain"}:
            action = "补充对应微／宏单尺度密度区间的标定数据，避免向分级结构外推。"
        elif name in {"density_eta_domain", "extra_feature_bounds"}:
            action = "补充分级密度、孔隙份额或选中修正特征的覆盖；当前范围外结果仅供诊断。"
        elif name in {"refinement_beats_baseline", "nondegradation_holdout"}:
            action = "保留原模型对照；修正暂不满足留出比较要求，不根据留出结果另选模型或降低门槛。"
        else:
            action = "核对测量、模型形式与独立条件覆盖；需新数据验证，不改变事先声明的误差门槛。"
        if action not in actions:
            actions.append(action)
    process = result["process_model"]
    if not process["available"] or not process["numerical_gates_passed"]:
        actions.append("工艺到密度关系尚未通过：核对温度／出料倍率设计、密度测量及独立留出覆盖。")
    scale = result["scale_separation"]
    scale_status = "ratio_failed" if not scale["declared_ratio_checks_passed"] else scale["review_status"]
    if scale_status != "reviewed":
        actions.append("先审核实际壁厚和泡孔分布的尺度假设；平均孔径比通过也不是均匀化有效性的证明。")
    actions.append("冻结候选后，用新制备条件做独立确认；打印点还需另行核对设备范围、预算和基准。")
    return {"mechanical_status": "passed" if result["numerical_gates_passed"] else "failed",
            "process_density_status": "unavailable" if not process["available"] else "passed" if process["numerical_gates_passed"] else "failed",
            "scale_assumption_status": scale_status, "failed_numerical_checks": failed,
            "priority_actions": actions, "physical_improvement_confirmed": False}


def analyse(task: dict, rows: list[dict]) -> dict:
    validate_task(task)
    train = [r for r in rows if r["partition"] == "train"]
    hierarchy_train = [r for r in train if r["scale"] == "hierarchical"]
    hierarchy_holdout = [r for r in rows if r["scale"] == "hierarchical" and r["partition"] == "holdout"]
    powerlaw = task["powerlaw"]
    baseline = {"base_property_MPa": task["base_property"]["value"]}
    for scale in ("micro", "macro"):
        baseline[scale] = fit_powerlaw(train, baseline["base_property_MPa"], scale,
                                       powerlaw["coefficient_bounds"], powerlaw["exponent_bounds"])
    alpha = task["refinement"]["ridge_alpha"]
    specs = {"baseline": None, "density_refinement": ["log_micro_density", "log_macro_density"],
             "host_proposed_refinement": task["refinement"]["features"]}
    models = {}
    for name, features in specs.items():
        try:
            state = None if features is None else fit_refinement(hierarchy_train, baseline, features, alpha)
            cv_rows, cv_predictions = [], []
            for fit, test in _folds(hierarchy_train):
                fold_state = None if features is None else fit_refinement(fit, baseline, features, alpha)
                cv_rows.extend(test)
                cv_predictions.extend(model_predict(test, baseline, fold_state))
            models[name] = {"available": True, "state": state, "cv": error_metrics(cv_rows, cv_predictions)}
        except InputError as exc:
            models[name] = {"available": False, "reason": str(exc)}
    need(models["baseline"]["available"], "原始两级模型未完成计算")
    # 到这一行只使用训练响应；冻结选择后才读取留出响应评分。
    selected = min((name for name in specs if models[name]["available"]), key=lambda name: models[name]["cv"]["rmse"])
    frozen_selection = {"selected_model": selected, "baseline": baseline,
                        "refinement_state": models[selected]["state"]}
    selection_hash = hashlib.sha256(json.dumps(frozen_selection, sort_keys=True, allow_nan=False).encode()).hexdigest()
    constant_rows, constant_predictions = [], []
    for fit, test in _folds(hierarchy_train):
        constant = float(np.average([r["response_MPa"] for r in fit], weights=group_weights(fit)))
        constant_rows.extend(test)
        constant_predictions.extend([constant] * len(test))
    constant_cv = error_metrics(constant_rows, constant_predictions)
    points = [[r["total_relative_density"], r["microscale_porosity_fraction"]] for r in hierarchy_train]
    in_domain = [_inside_hull(points, [r["total_relative_density"], r["microscale_porosity_fraction"]]) for r in hierarchy_holdout]
    predictions = []
    for name, model in models.items():
        if not model["available"]:
            continue
        values = model_predict(hierarchy_holdout, baseline, model["state"])
        model["holdout"] = error_metrics(hierarchy_holdout, values)
        for row, prediction, supported in zip(hierarchy_holdout, values, in_domain):
            predictions.append({"sample_id": row["sample_id"], "condition_id": row["condition_id"],
                                "model": name, "actual_MPa": row["response_MPa"], "predicted_MPa": prediction,
                                "inside_density_eta_training_domain": supported})
    # 额外修正变量仅有训练边界检查，不把边界盒宣称为完整联合覆盖。
    context_bounds = {key: [min(r[key] for r in hierarchy_train), max(r[key] for r in hierarchy_train)]
                      for key in ("temperature_C", "wall_thickness_um", "mean_pore_diameter_um")}
    extra_support = []
    feature_names = models[selected]["state"]["feature_names"] if models[selected]["state"] else []
    for row in hierarchy_holdout:
        supported = True
        for feature in feature_names:
            train_values = [feature_value(r, feature) for r in hierarchy_train]
            supported &= min(train_values) - 1e-10 <= feature_value(row, feature) <= max(train_values) + 1e-10
        extra_support.append(bool(supported))
    ratios = [{"sample_id": r["sample_id"],
               "wall_to_mean_pore_ratio": r["wall_thickness_um"] / r["mean_pore_diameter_um"] if r["mean_pore_diameter_um"] else None,
               "passes_declared_ratio": not r["mean_pore_diameter_um"] or
               r["wall_thickness_um"] / r["mean_pore_diameter_um"] >= task["scale_separation"]["min_wall_to_pore_ratio"]}
              for r in hierarchy_train + hierarchy_holdout]
    chosen = models[selected]
    criteria = task["acceptance"]
    numerical_checks = {
        "cv_error": chosen["cv"]["rmse"] <= criteria["max_cv_rmse_MPa"],
        "holdout_error": chosen["holdout"]["rmse"] <= criteria["max_holdout_rmse_MPa"],
        "beats_constant_cv": chosen["cv"]["rmse"] < constant_cv["rmse"],
        "nondegradation_holdout": chosen["holdout"]["rmse"] <= models["baseline"]["holdout"]["rmse"] + criteria["max_degradation_MPa"],
        "density_eta_domain": all(in_domain), "extra_feature_bounds": all(extra_support),
    }
    if criteria["require_beats_baseline"] and selected != "baseline":
        numerical_checks["refinement_beats_baseline"] = chosen["cv"]["rmse"] < models["baseline"]["cv"]["rmse"] \
            and chosen["holdout"]["rmse"] < models["baseline"]["holdout"]["rmse"]
    process = _process_analysis(rows, task["process_model"])
    baseline_validation = {}
    for scale in ("micro", "macro"):
        fitting = [r for r in train if r["scale"] == scale]
        test = [r for r in rows if r["partition"] == "holdout" and r["scale"] == scale]
        cv_rows, cv_predictions = [], []
        for fit, fold_test in _folds(fitting):
            params = fit_powerlaw(fit, baseline["base_property_MPa"], scale,
                                 powerlaw["coefficient_bounds"], powerlaw["exponent_bounds"])
            cv_rows.extend(fold_test)
            cv_predictions.extend([baseline["base_property_MPa"] * params["coefficient"] * r["total_relative_density"] ** params["exponent"] for r in fold_test])
        holdout_predictions = [baseline["base_property_MPa"] * baseline[scale]["coefficient"] * r["total_relative_density"] ** baseline[scale]["exponent"] for r in test]
        bounds = [min(r["total_relative_density"] for r in fitting), max(r["total_relative_density"] for r in fitting)]
        transfer = [{"sample_id": r["sample_id"], "relative_density": r[f"{scale}_relative_density"],
                     "inside_training_density_range": bounds[0] - 1e-10 <= r[f"{scale}_relative_density"] <= bounds[1] + 1e-10}
                    for r in hierarchy_train + hierarchy_holdout]
        baseline_validation[scale] = {"cv": error_metrics(cv_rows, cv_predictions), "holdout": error_metrics(test, holdout_predictions),
                                      "training_density_bounds": bounds,
                                      "holdout_inside_training_density_range": [bounds[0] <= r["total_relative_density"] <= bounds[1] for r in test],
                                      "hierarchical_calibration_transfer": transfer}
    numerical_checks["monoscale_density_domain"] = all(all(v["holdout_inside_training_density_range"]) for v in baseline_validation.values())
    numerical_checks["hierarchical_within_monoscale_calibration_domain"] = all(
        all(item["inside_training_density_range"] for item in v["hierarchical_calibration_transfer"])
        for v in baseline_validation.values())
    result = {
        "schema_version": VERSION, "task_id": task["task_id"], "material_id": task["material_id"], "context_id": task["context_id"],
        "mode": task["mode"], "data_kind": task["data_kind"], "observable": task["observable"], "response_unit": "MPa",
        "status": "synthetic_calculation_complete" if task["mode"] == "offline_demo" else "conditional_calculation_complete",
        "prediction_performed": True, "baseline": baseline, "baseline_validation": baseline_validation,
        "model_form": "Y/Y_s = C_micro*C_macro*rho_micro**n_micro*rho_macro**n_macro",
        "model_source": {"url": SOURCE, "equations": [3, 4, 7, 9],
                         "adaptation": "有界、条件等权的对数最小二乘是项目实现，非原作者 MATLAB 代码复刻"},
        "models": models, "selected_model": selected, "selection_basis": "training_leave_one_condition_out_cv_only",
        "selection_frozen_before_holdout": True, "selection_sha256": selection_hash,
        "selection_cv_is_not_independent_final_performance": True,
        "constant_baseline_cv": constant_cv, "predictions": predictions, "process_model": process,
        "refinement_proposal": copy.deepcopy(task["refinement"]), "numerical_checks": numerical_checks,
        "numerical_gates_passed": all(numerical_checks.values()),
        "scale_separation": {"review_status": task["scale_separation"]["review_status"], "checks": ratios,
                             "declared_ratio_checks_passed": all(r["passes_declared_ratio"] for r in ratios),
                             "mean_pore_ratio_is_not_proof_of_continuum_validity": True},
        "training_domain": {"density_eta_convex_hull_points": points, "extra_marginal_bounds": context_bounds,
                            "extra_bounds_are_not_joint_coverage": True},
        "sensitivity": _sensitivity(hierarchy_train, baseline, chosen["state"]),
        "physical_validation_performed": False, "fresh_confirmation_performed": False,
        "llm_called_by_script": False, "dedicated_simulation_software_called": False, "hardware_commands_sent": False,
        "recommendation_level": "diagnostic_only", "uncertainty": "not_quantified",
        "not_predicted": ["full_stress_strain_curve", "energy_absorption", "cyclic_recovery", "fatigue_life", "biodegradation", "thermal_conductivity"],
        "next_action": "用独立新制备条件验证冻结候选；具体打印点另行核对设备边界、网格、预算和基准，不据此自动执行。",
    }
    result["decision_summary"] = _decision_summary(result)
    return result


def _render_report(result: dict) -> str:
    lines = ["# 分级聚合物泡沫简化计算", "", f"状态：{result['status']}", ""]
    if not result.get("prediction_performed"):
        return "\n".join(lines + ["输入未通过检查：", "", *[f"- {e}" for e in result.get("errors", [])], ""])
    lines += [f"任务：{result['task_id']}；数据类别：{result['data_kind']}；响应：{result['observable']}（MPa）。", "",
              "合成演示只检验软件。研究模式也不认证实验真实性或完整仿真等效性。", "",
              "## 按制备条件留出的模型比较", "", "| 模型 | 条件分组 CV RMSE（MPa） | 留出 RMSE（MPa） |", "|---|---:|---:|"]
    for name, model in result["models"].items():
        if model["available"]:
            lines.append(f"| {name} | {model['cv']['rmse']:.6g} | {model['holdout']['rmse']:.6g} |")
        else:
            lines.append(f"| {name} | 不可识别：{model['reason']} | 未选择 |")
    lines += ["", f"冻结选择：{result['selected_model']}，依据训练条件 CV；没有用留出结果选模型。", "",
              f"数值关口：{'通过' if result['numerical_gates_passed'] else '未通过'}；新实验独立确认：未进行。", "",
              f"分级样品两级密度在对应单尺度标定范围内：{result['numerical_checks']['hierarchical_within_monoscale_calibration_domain']}。",
              "任何一级转移外推都会使数值关口失败；已有分级数据上的小误差不等于单尺度标定域覆盖。", "",
              "## 检查结果与优先补充事项", ""]
    for name, passed in result["numerical_checks"].items():
        lines.append(f"- {CHECK_LABELS.get(name, name)}：{'通过' if passed else '未通过'}。")
    lines += ["", *[f"- {action}" for action in result["decision_summary"]["priority_actions"]], "",
              "## 因素提取与限定范围敏感性", "",
              "方向仅描述受支持的离散扫描点；不保证整个连续区间的趋势，也不表示因果、显著性或最优设备参数。", ""]
    for item in result["sensitivity"]:
        label = FACTOR_LABELS[item["factor"]]
        if not item["available"]:
            lines.append(f"- {label}：暂不可比较（{item['reason']}，支持点 {item['sampled_points_count']} 个）；不能解释为没有影响。")
            continue
        first, last = item["endpoint_predictions"]
        lines.append(f"- {label}：{DIRECTION_LABELS[item['direction']]}；实际支持扫描范围 {item['sampled_supported_range']}，"
                     f"支持点 {item['sampled_points_count']} 个，响应从 {first['predicted_value']:.6g} 到 {last['predicted_value']:.6g} MPa，跨度 {item['response_span_MPa']:.6g} MPa。")
        fixed = "、".join(f"{FACTOR_LABELS.get(k, k)}={v:.6g}" for k, v in item["fixed_reference"].items())
        lines.append(f"  固定参考：{fixed}。同时检查分级凸包、两级标定范围及修正特征边界，边际边界仍不是完整联合覆盖。")
    process = result["process_model"]
    if process["available"]:
        lines += ["", f"温度／出料倍率到内部密度的经验响应面：CV RMSE {process['cv']['rmse']:.6g}，留出 RMSE {process['holdout']['rmse']:.6g}（无量纲）。"]
        lines += [f"工艺密度数值关口：{'通过' if process['numerical_gates_passed'] else '未通过'}；此检查独立于结构到性能模型，未验证端到端预测链。"]
        lines += [f"工艺 CV 误差 {process['cv']['rmse']:.6g}、留出误差 {process['holdout']['rmse']:.6g}；留出条件位于训练工艺凸包：{'是' if all(process['holdout_inside_training_domain']) else '否'}。"]
        for item in process["sensitivity"]:
            label = FACTOR_LABELS[item["factor"]]
            if not item["available"]:
                lines.append(f"- {label}：暂不可比较（{item['reason']}，支持点 {item['sampled_points_count']} 个）；不是零效应。")
                continue
            first, last = item["endpoint_predictions"]
            fixed = "、".join(f"{FACTOR_LABELS[k]}={v:.6g}" for k, v in item["fixed_reference"].items())
            lines.append(f"- {label}：{DIRECTION_LABELS[item['direction']]}；实际支持扫描范围 {item['sampled_supported_range']}，"
                         f"支持点 {item['sampled_points_count']} 个，内部密度从 {first['predicted_value']:.6g} 到 {last['predicted_value']:.6g}，"
                         f"跨度 {item['density_span']:.6g}；固定参考：{fixed}。")
    else:
        lines += ["", f"工艺响应面暂不可用：{process['reason']}"]
    lines += ["", "敏感性是模型在指定范围内的条件变化，不是因果排序；出料倍率不是实际体积流量。",
              "用于模型选择的 CV 分数不是独立最终性能估计；留出集不得反复用于调整模型。", "",
              "## 适用边界与下一步", "",
              f"尺度假设审核：{result['scale_separation']['review_status']}；声明壁厚／平均孔径比检查：{result['scale_separation']['declared_ratio_checks_passed']}。",
              "平均孔径比不足以证明均匀化有效；实际壁厚、泡孔分布、方向和边界条件仍需检查。", "",
              "该模块不预测完整压缩曲线、吸能、循环回弹或寿命，也没有调用 LLM API、商业仿真软件或打印机。", "",
              result["next_action"], ""]
    return "\n".join(lines)


def run_task(task_path: Path, out: Path) -> dict:
    task_path, out = Path(task_path), Path(out)
    need(not out.exists(), "输出目录已存在；请使用新目录，禁止覆盖历史")
    out.mkdir(parents=True)
    try:
        need(task_path.is_file() and task_path.stat().st_size <= 2_000_000, "任务 JSON 不存在或超过 2 MB")
        task_snapshot = out / "input_task.json"
        shutil.copyfile(task_path, task_snapshot)
        task = load_json(task_snapshot)
        validate_task(task)
        dataset_path = safe_child(task_path.parent, task["dataset_file"])
        need(dataset_path.is_file() and dataset_path.stat().st_size <= 10_000_000, "CSV 不存在或超过 10 MB")
        dataset_snapshot = out / "input_measurements.csv"
        shutil.copyfile(dataset_path, dataset_snapshot)
        rows, data_check = load_measurements(task, dataset_snapshot)
        result = analyse(task, rows)
        result["data_check"] = data_check
        result["input_hashes"] = {"task_sha256": file_hash(task_snapshot), "dataset_sha256": file_hash(dataset_snapshot)}
        result["analysis_used_frozen_input_snapshots"] = True
        result["source_hashes"] = {"foam_model.py": file_hash(Path(__file__)),
                                   "_core.py": file_hash(Path(__file__).with_name("_core.py"))}
    except (InputError, OSError, ValueError, TypeError, KeyError, OverflowError, np.linalg.LinAlgError) as exc:
        result = {"schema_version": VERSION, "status": "blocked", "prediction_performed": False,
                  "physical_validation_performed": False, "errors": [str(exc)]}
    if result.get("prediction_performed"):
        model = {key: result[key] for key in ("schema_version", "task_id", "material_id", "context_id", "mode", "data_kind",
                 "observable", "response_unit", "baseline", "models", "process_model", "selected_model", "selection_sha256", "training_domain", "input_hashes", "source_hashes")}
        model["fixed_conditions"] = task["fixed_conditions"]
        model["base_property_source"] = task["base_property"]
        model["status"] = "frozen_numerical_candidate_not_physically_confirmed"
        write_json(out / "model.json", model)
        result["model_artifact_sha256"] = file_hash(out / "model.json")
    result["software"] = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}
    write_json(out / "result.json", result)
    (out / "report.md").write_text(_render_report(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="标定并比较简化模型，不调用设备")
    run.add_argument("--task", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_task(args.task, args.out)
    except InputError as exc:
        parser.error(str(exc))
    print(json.dumps({key: result.get(key) for key in ("status", "data_kind", "selected_model", "numerical_gates_passed", "errors")}, ensure_ascii=False))
    return 0 if result.get("prediction_performed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
