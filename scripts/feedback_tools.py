"""Import reported follow-up measurements against a FROZEN plan and model.

No hardware, network, invented measurements, significance tests or confidence intervals.
The comparison is descriptive, uses concurrent controls, and never refits before scoring.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.preprocessing import PolynomialFeatures

from calibration_planning import InputError, need, text, safe_child, in_training_domain


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def read_table(path: Path, required: set[str]) -> list[dict]:
    need(path.is_file() and path.stat().st_size <= 10_000_000, 'CSV missing or exceeds 10 MB')
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        need(len(headers) == len(set(headers)), 'Duplicate CSV headers')
        need(required.issubset(headers), 'Missing CSV columns: ' + ', '.join(sorted(required-set(headers))))
        rows = list(reader)
    need(0 < len(rows) <= 10000, 'CSV must contain 1..10000 actual rows, not just a template header')
    for i, r in enumerate(rows, 2):
        need(None not in r and all(text(r.get(k)) for k in required), f'Incomplete/extra CSV fields at row {i}')
    return rows


def number(value: Any, label: str, positive: bool = False) -> float:
    need(not isinstance(value, bool), f'{label}: boolean is not numeric')
    try:
        v = float(value)
    except (ValueError, TypeError) as e:
        raise InputError(f'{label}: invalid number') from e
    need(math.isfinite(v) and (not positive or v > 0), f'{label}: nonfinite/nonpositive value')
    return v


def timestamp(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError) as e:
        raise InputError('Timestamps must be ISO-8601 with timezone') from e
    need(dt.tzinfo is not None and dt.utcoffset() is not None, 'Timestamp timezone required')
    return dt


def validate_protocol(protocol: dict, task: dict) -> None:
    need(isinstance(protocol, dict) and protocol.get('schema_version') == '0.4', 'Comparison protocol schema must be 0.4')
    need(protocol.get('inference') == 'descriptive_only', 'v0.4 supports descriptive comparison only')
    need(protocol.get('independent_unit') == task['group_column'], 'Protocol independent_unit must match task grouping')
    need(protocol.get('baseline') == 'concurrent_same_batch', 'Concurrent same-batch baseline required')
    need(protocol.get('observable') == task['observable'], 'Protocol observable mismatch')
    need(type(protocol.get('target_tolerance_um')) in (int,float), 'target_tolerance_um must be numeric')
    need(type(protocol.get('min_practical_reduction_um')) in (int,float), 'min_practical_reduction_um must be numeric')
    number(protocol.get('target_tolerance_um'), 'target_tolerance_um', positive=True)
    need(number(protocol.get('min_practical_reduction_um'), 'min_practical_reduction_um') >= 0,
         'Practical reduction must be nonnegative')
    need(text(protocol.get('source_ref')), 'Protocol source_ref required')
    tolerances = protocol.get('actual_setting_tolerances', {})
    need(isinstance(tolerances, dict) and set(tolerances) == {f['name'] for f in task['factors']}, 'Setting tolerances must name all factors')
    for key, val in tolerances.items():
        need(type(val) in (int,float), 'Setting tolerance must be numeric')
        need(number(val, key) >= 0, 'Setting tolerance must be nonnegative')


class FrozenModel:
    """Numerical reconstruction from plain JSON. No pickle, eval or dynamic imports."""
    def __init__(self, spec: dict, observable: str):
        self.spec, self.observable = spec, observable

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self.observable == 'concentration_sigma_um':
            return np.sqrt(self.spec['a_um2'] + self.spec['b_um2_s']*x[:, 0])
        phi = PolynomialFeatures(degree=self.spec['degree'], include_bias=False).fit_transform(x)
        out = ((phi - np.asarray(self.spec['scaler_mean'])) / np.asarray(self.spec['scaler_scale'])) @ np.asarray(self.spec['coef_standardized']) + self.spec['intercept']
        need(np.isfinite(out).all(), 'Frozen model produced nonfinite values')
        return out


def predict_frozen(task: dict, calibration: dict, training_rows: list[dict], parameters: dict) -> tuple[float | None, bool]:
    fields = [f['name'] for f in task['factors']]
    x = np.asarray([[r[k] for k in fields] for r in training_rows if r['partition'] == 'fit'], dtype=float).reshape(-1, len(fields))
    q = np.asarray([[parameters[k] for k in fields]], dtype=float)
    inside = bool(in_training_domain(x, q)[0])
    if not inside or not calibration.get('model_usable_for_proposals'):
        return None, inside
    v = float(FrozenModel(calibration['model'], task['observable']).predict(q)[0])
    return (v if v > 0 else None), inside


def import_feedback(task: dict, historical_rows: list[dict], calibration: dict, plan: dict,
                    manifest: dict, folder: Path, protocol: dict) -> dict:
    validate_protocol(protocol, task)
    need(isinstance(manifest, dict) and manifest.get('schema_version') == '0.4', 'Feedback manifest schema must be 0.4')
    for key in ('task_id', 'material_pair', 'context_id', 'data_kind', 'mode', 'observable'):
        need(manifest.get(key) == task[key], f'Feedback {key} mismatch')
    need(text(manifest.get('feedback_id')) and text(manifest.get('source_ref')), 'Feedback identity and provenance required')
    need(manifest.get('plan_sha256') == digest(plan), 'Feedback plan hash mismatch: stale/wrong plan')
    need(manifest.get('comparison_protocol_sha256') == digest(protocol), 'Comparison protocol changed after planning')
    need(manifest.get('measurement_definition') == task['measurement_definition'], 'Measurement definition changed; create a separate context')
    need(manifest.get('fixed_conditions') == task['fixed_conditions'], 'Fixed conditions mismatch')
    synthetic = task['data_kind'] == 'synthetic_demo'
    need(manifest.get('acquisition_status') == ('synthetic_fixture' if synthetic else 'reported_measurements'), 'Feedback acquisition status mismatches provenance')
    fields = [f['name'] for f in task['factors']]
    trials = {r['trial_id']: r for r in plan['trials']}
    ereq = {'execution_id', 'trial_id', 'sample_id', 'batch_id', 'material_pair', 'context_id', 'data_kind', 'source_ref',
            'approval_status', 'approval_source_ref', 'execution_status', 'executed_at', *('actual_'+k for k in fields)}
    mreq = {'record_id', 'execution_id', 'sample_id', 'batch_id', 'material_pair', 'context_id', 'data_kind',
            'source_ref', 'observable', 'response_unit', 'response_um', 'measured_at'}
    executions = read_table(safe_child(folder, manifest.get('execution_file')), ereq)
    measurements = read_table(safe_child(folder, manifest.get('dataset_file')), mreq)
    history_samples = {r['sample_id'] for r in historical_rows}
    history_records = {i for r in historical_rows for i in r['record_ids']}
    history_batches = {r['batch_id'] for r in historical_rows}
    by_execution, sample_ids = {}, set()
    for r in executions:
        eid, sid = r['execution_id'], r['sample_id']
        need(eid not in by_execution and sid not in sample_ids, 'Duplicate execution/sample id in follow-up log')
        need(sid not in history_samples, 'Follow-up must use new independent specimens, not historical sample ids')
        need(r['batch_id'] not in history_batches, 'Follow-up batch overlaps historical data; review independence')
        need(r['trial_id'] in trials, 'Unknown trial_id')
        for k in ('material_pair', 'context_id', 'data_kind'):
            need(r[k] == task[k], f'Execution {k} mismatch')
        need(r['approval_status'] == ('demo_only' if synthetic else 'reported_approved'), 'Missing approval evidence; LLM cannot approve hardware')
        need(r['execution_status'] == ('synthetic_execution' if synthetic else 'reported_completed'), 'Execution not reported completed')
        timestamp(r['executed_at'])
        actual, deviations = {}, {}
        for f in task['factors']:
            key = f['name']; v = number(r['actual_'+key], 'actual_'+key)
            need(f['bounds'][0] <= v <= f['bounds'][1], 'Actual setting outside reviewed task bounds; stop and review')
            actual[key] = v
            delta = v - trials[r['trial_id']]['parameters'][key]
            if abs(delta) > protocol['actual_setting_tolerances'][key] + 1e-10:
                deviations[key] = delta
        by_execution[eid] = {**r, 'actual_parameters': actual, 'setting_deviations': deviations}
        sample_ids.add(sid)
    mids, grouped = set(), defaultdict(list)
    for r in measurements:
        need(r['record_id'] not in mids and r['record_id'] not in history_records, 'Duplicate or historical measurement record_id')
        mids.add(r['record_id'])
        need(r['execution_id'] in by_execution, 'Measurement has no matching execution log')
        e = by_execution[r['execution_id']]
        for k in ('sample_id', 'batch_id', 'material_pair', 'context_id', 'data_kind'):
            need(r[k] == e[k], f'Measurement {k} mismatches execution')
        need(r['observable'] == task['observable'] and r['response_unit'] == 'um', 'Wrong response observable/unit')
        need(timestamp(r['measured_at']) >= timestamp(e['executed_at']), 'Measurement predates execution')
        value = number(r['response_um'], 'response_um', positive=True)
        grouped[r['execution_id']].append((value, r))
    aggregated = []
    for eid, vals in grouped.items():
        e = by_execution[eid]; trial = trials[e['trial_id']]
        pv, inside = predict_frozen(task, calibration, historical_rows, e['actual_parameters'])
        mean = float(np.mean([v for v, _ in vals]))
        aggregated.append({'execution_id': eid, 'sample_id': e['sample_id'], 'batch_id': e['batch_id'],
            'trial_id': e['trial_id'], 'purpose': trial['purpose'], 'data_kind': task['data_kind'],
            'actual_parameters': e['actual_parameters'], 'planned_parameters': trial['parameters'],
            'setting_deviations': e['setting_deviations'], 'eligible_intended_comparison': not e['setting_deviations'],
            'response_um': mean, 'technical_measurements': len(vals), 'record_ids': [r['record_id'] for _, r in vals],
            'source_refs': sorted({e['source_ref'], *[r['source_ref'] for _, r in vals]}),
            'frozen_prediction_at_actual_um': pv, 'original_planned_prediction_um': trial['predicted_response_um'],
            'inside_training_domain': inside, 'prediction_error_um': (pv - mean) if pv is not None else None,
            'absolute_target_error_um': abs(mean-task['target_um'])})
    return {'status': 'feedback_imported_not_yet_compared', 'feedback_id': manifest['feedback_id'],
        'data_kind': task['data_kind'], 'acquisition_status': manifest['acquisition_status'],
        'plan_sha256': digest(plan), 'comparison_protocol_sha256': digest(protocol),
        'model_sha256': digest(calibration), 'n_raw_measurements': len(measurements),
        'n_new_samples': len(aggregated), 'n_batches': len({r['batch_id'] for r in aggregated}),
        'n_executions_without_measurement': len(set(by_execution)-set(grouped)),
        'missing_trial_ids': sorted(set(trials)-{r['trial_id'] for r in aggregated}),
        'n_samples_with_setting_deviations': sum(bool(r['setting_deviations']) for r in aggregated),
        'n_samples_without_supported_prediction': sum(r['frozen_prediction_at_actual_um'] is None for r in aggregated),
        'samples': aggregated, 'physical_printing_performed_by_software': False,
        'measurement_authenticity_verified': False,
        'note': 'Imports declared records only. Settings deviations retained but excluded from intended-arm comparisons. No automatic material/property inference.'}


def compare_feedback(task: dict, imported: dict, plan: dict, protocol: dict) -> dict:
    need(imported.get('plan_sha256') == digest(plan), 'Cannot compare against a different plan')
    need(imported.get('comparison_protocol_sha256') == digest(protocol), 'Protocol mismatch')
    need(imported.get('data_kind') == task['data_kind'], 'Provenance mismatch')
    baseline_ids = {t['trial_id'] for t in plan['trials'] if t['purpose'] == 'baseline_replication'}
    need(len(baseline_ids) == 1, 'Exactly one concurrent baseline condition is required')
    baseline_id = next(iter(baseline_ids))
    eligible = [r for r in imported['samples'] if r['eligible_intended_comparison']]
    groups = defaultdict(list)
    for r in eligible:
        groups[r['trial_id']].append(r)
    by_batch = lambda rs: {b: [r for r in rs if r['batch_id'] == b] for b in sorted({r['batch_id'] for r in rs})}
    baseline = by_batch(groups.get(baseline_id, []))
    summaries, contrasts = [], []
    for trial in plan['trials']:
        tid = trial['trial_id']; rows = groups.get(tid, [])
        batches = by_batch(rows)
        if rows:
            # Equal-batch weighting if the declared independent group is batch_id.
            units = list(batches.values()) if protocol['independent_unit'] == 'batch_id' else [[r] for r in rows]
            means = [float(np.mean([r['response_um'] for r in u])) for u in units]
            errors = [float(np.mean([r['absolute_target_error_um'] for r in u])) for u in units]
            success = [float(np.mean([r['absolute_target_error_um'] <= protocol['target_tolerance_um'] for r in u])) for u in units]
            paired = [r for r in rows if r['prediction_error_um'] is not None]
            residual_units = by_batch(paired).values() if protocol['independent_unit'] == 'batch_id' else [[r] for r in paired]
            residual_means = [float(np.mean([r['prediction_error_um']**2 for r in u])) for u in residual_units]
            info = {'n_samples': len(rows), 'n_independent_units': len(units), 'n_batches': len(batches),
                    'mean_response_um': float(np.mean(means)), 'mean_absolute_target_error_um': float(np.mean(errors)),
                    'target_pass_fraction': float(np.mean(success)),
                    'frozen_prediction_rmse_um': math.sqrt(float(np.mean(residual_means))) if residual_means else None}
        else:
            info = {'n_samples': 0, 'n_independent_units': 0, 'n_batches': 0,
                    'mean_response_um': None, 'mean_absolute_target_error_um': None,
                    'target_pass_fraction': None, 'frozen_prediction_rmse_um': None}
        summaries.append({'trial_id': tid, 'purpose': trial['purpose'], **info})
        if tid == baseline_id:
            continue
        common = sorted(set(batches) & set(baseline))
        diffs = []
        for b in common:
            be = float(np.mean([r['absolute_target_error_um'] for r in baseline[b]]))
            ce = float(np.mean([r['absolute_target_error_um'] for r in batches[b]]))
            diffs.append({'batch_id': b, 'baseline_error_um': be, 'candidate_error_um': ce,
                          'reduction_um': be-ce})
        if not diffs:
            verdict, delta, percent = 'inconclusive_no_concurrent_baseline', None, None
        else:
            delta = float(np.mean([r['reduction_um'] for r in diffs]))
            ref = float(np.mean([r['baseline_error_um'] for r in diffs]))
            percent = 100*delta/ref if ref > 1e-12 else None
            margin = protocol['min_practical_reduction_um']
            verdict = 'descriptive_improvement' if delta > margin else ('descriptive_worsening' if delta < -margin else 'no_practical_difference_in_observed_data')
        contrasts.append({'trial_id': tid, 'baseline_trial_id': baseline_id,
                          'n_matched_batches': len(common), 'matched_batch_differences': diffs,
                          'mean_absolute_error_reduction_um': delta, 'relative_reduction_percent': percent,
                          'verdict': verdict, 'confidence_interval': None, 'p_value': None,
                          'causal_effect_established': False, 'generalisation_established': False})
    return {'version': '0.4.0', 'task_id': task['task_id'], 'data_kind': task['data_kind'],
        'status': 'synthetic_feedback_evaluated' if task['data_kind'] == 'synthetic_demo' else 'reported_measurements_descriptively_evaluated',
        'observable': task['observable'], 'target_um': task['target_um'], 'protocol': protocol,
        'frozen_model_scored_before_update': True, 'per_trial': summaries, 'contrasts': contrasts,
        'excluded_settings_deviation_samples': [r['sample_id'] for r in imported['samples'] if not r['eligible_intended_comparison']],
        'missing_trial_ids': imported['missing_trial_ids'], 'performance_claim_scope': task['observable'],
        'real_printing_improvement_established_by_this_demo': False,
        'statistical_significance_test_performed': False,
        'cautions': ['Descriptive comparison only; no confidence interval or hypothesis test.',
                     'Repeated measurements are aggregated before counting samples.',
                     'Contemporaneous same-batch controls used; missing controls give no improvement verdict.',
                     'No inference of cure conversion, interface strength, fatigue or device performance.',
                     'Declared provenance and context cannot authenticate the laboratory records.',
                     'Once used for model development, follow-up results are not a new independent validation set.']}
