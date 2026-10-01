"""Versioned refitting, prospective confirmation and multi-round continuation.

No measurements are generated here. Confirmation is attached by an operator only
AFTER the candidate model is frozen. No changes to objectives, model class,
acceptance thresholds or physical bounds are allowed inside a round.
"""
from __future__ import annotations

import copy
import csv
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from calibration_planning import (need, validate_task, load_measurements, arrays,
    calibrate, error_metrics, in_training_domain, candidate_grid, write_csv, safe_child)
from feedback_tools import digest, FrozenModel, number

DEFAULT_POLICY = {
    'schema_version': '1.0', 'max_rounds': 3,
    'confirmation_conditions': 6, 'min_confirmation_groups': 2,
    'require_non_degradation': True, 'max_rmse_increase_um': 0.0,
    'inference': 'descriptive_only',
    'source_ref': 'Prototype workflow defaults; not a power analysis or validated material limits',
}


def api():
    # Lazy import avoids importing a partially initialised dispatcher.
    import agent_runtime
    return agent_runtime


def validate_policy(obj: Any) -> None:
    need(isinstance(obj, dict) and obj.get('schema_version') == '1.0', 'Update policy schema must be 1.0')
    for key, lo, hi in [('max_rounds', 1, 10), ('confirmation_conditions', 3, 30), ('min_confirmation_groups', 2, 20)]:
        need(type(obj.get(key)) is int and lo <= obj[key] <= hi, f'Invalid update policy {key}')
    need(type(obj.get('require_non_degradation')) is bool, 'require_non_degradation must be boolean')
    need(type(obj.get('max_rmse_increase_um')) in (int, float), 'Numeric degradation tolerance required')
    need(number(obj['max_rmse_increase_um'], 'max_rmse_increase_um') >= 0, 'Degradation tolerance cannot be negative')
    need(obj.get('inference') == 'descriptive_only', 'Only descriptive gates are implemented')
    need(isinstance(obj.get('source_ref'), str) and bool(obj['source_ref'].strip()), 'Policy source required')


def policy(session: Path) -> dict:
    ar = api()
    path = session/'input/update_policy.json'
    return ar.load(path) if path.exists() else copy.deepcopy(DEFAULT_POLICY)


def known_ids(session: Path) -> dict:
    """All prior IDs, including retired checks and excluded setting-deviation rows."""
    ar = api(); s = ar.load(session/'state.json')
    history = s.get('lineage_ids', {})
    ids = {k: set(history.get(k, [])) for k in ('sample_ids', 'batch_ids', 'record_ids')}
    rows, _ = load_measurements(ar.load(session/'input/task.json'), session/'input/measurements.csv')
    for r in rows:
        ids['sample_ids'].add(r['sample_id']); ids['batch_ids'].add(r['batch_id'])
        ids['record_ids'].update(r['record_ids'])
    if s.get('imported'):
        for r in ar.load(session/'artifacts/feedback.json')['samples']:
            ids['sample_ids'].add(r['sample_id']); ids['batch_ids'].add(r['batch_id'])
            ids['record_ids'].update(r.get('record_ids', []))
    if s.get('confirmation_attached'):
        task = ar.load(session/'input/task.json')
        rows, _ = load_measurements(task, session/'confirmation_input/measurements.csv')
        for r in rows:
            ids['sample_ids'].add(r['sample_id']); ids['batch_ids'].add(r['batch_id'])
            ids['record_ids'].update(r['record_ids'])
    return {k: sorted(v) for k, v in ids.items()}


def confirmation_design(task: dict, fit_rows: list[dict], n: int) -> list[dict]:
    """Fixed, bounded coverage plan; generated without seeing new confirmation y."""
    x, _, _ = arrays(fit_rows, task)
    grid = candidate_grid(task)
    grid = grid[in_training_domain(x, grid)]
    if not len(grid):
        return []
    span = np.asarray([f['bounds'][1]-f['bounds'][0] for f in task['factors']])
    center = np.mean(x, axis=0)
    selected = [int(np.argmin(np.linalg.norm((grid-center)/span, axis=1)))]
    while len(selected) < min(n, len(grid)):
        distances = np.min(np.linalg.norm((grid[:, None, :]-grid[selected][None, :, :])/span, axis=2), axis=1)
        distances[selected] = -1
        selected.append(int(np.argmax(distances)))
    return [{'condition_id': f'C{i+1:02d}',
             'parameters': {f['name']: float(v) for f, v in zip(task['factors'], grid[j])},
             'state': 'suggested', 'human_approval_required': True}
            for i, j in enumerate(selected)]


def refit_update(session: Path, s: dict) -> dict:
    ar = api(); ar.required_skill(s, 'update')
    need(s['compared'] and s['update_prepared'], 'Compare original model and prepare update first')
    if s.get('update_refitted'):
        return ar.load(session/'artifacts/update_candidate.json')
    task = ar.load(session/'update/task.json'); validate_task(task)
    rows, checks = load_measurements(task, session/'update/measurements.csv')
    need(all(r['partition'] == 'fit' for r in rows), 'Updated training file must not recycle holdout')
    cal, _ = calibrate(task, rows)
    p = policy(session)
    candidate = {
        'schema_version': '1.0', 'round_index': s.get('round_index', 1),
        'data_kind': task['data_kind'], 'calibration': cal,
        'fit_data_sha256': ar.file_hash(session/'update/measurements.csv'),
        'fit_task_sha256': ar.file_hash(session/'update/task.json'),
        'original_model_sha256': digest(ar.load(session/'artifacts/calibration.json')),
        'update_policy_sha256': digest(p), 'confirmation_used_for_fitting': False,
        'status': 'frozen_candidate_needs_fresh_confirmation' if cal['numerical_fit_performed'] else 'refit_failed_calibration_only',
        'data_check': checks, 'same_objective_model_and_acceptance': True,
        'physical_validation': False,
    }
    ar.artifact(session, s, 'update_candidate.json', candidate)
    ar.artifact(session, s, 'update_aggregated.json', rows)
    conditions = confirmation_design(task, rows, p['confirmation_conditions']) if cal['numerical_fit_performed'] else []
    design = {
        'schema_version': '1.0', 'candidate_sha256': digest(candidate),
        'data_kind': task['data_kind'], 'observable': task['observable'],
        'conditions': conditions, 'minimum_independent_groups': p['min_confirmation_groups'],
        'purpose': 'Check frozen candidate on new held-out groups; not fit or select hyperparameters',
        'budget_note': 'Additional confirmation measurements, not included in next_trials. No formal power calculation.',
        'freshness_note': 'IDs/context must be new; record identity checks cannot authenticate physical acquisition.',
        'uncertainty': 'No confidence or prediction interval estimated',
    }
    ar.artifact(session, s, 'confirmation_plan.json', design)
    s['update_refitted'] = True
    s['phase'] = candidate['status']
    return {'candidate': candidate, 'confirmation_plan': design,
            'next': 'Operator may attach fresh confirmation; otherwise choose calibration-only next round.'}


def validate_confirmation(session: Path, manifest: dict, base: Path) -> tuple[list[dict], dict]:
    ar = api(); s = ar.load(session/'state.json')
    need(s.get('update_refitted'), 'Freeze candidate model before attaching confirmation')
    candidate = ar.load(session/'artifacts/update_candidate.json')
    need(candidate['calibration']['numerical_fit_performed'], 'No fitted candidate to confirm')
    task = ar.load(session/'update/task.json')
    need(manifest.get('schema_version') == '1.0', 'Confirmation manifest schema must be 1.0')
    need(manifest.get('candidate_sha256') == digest(candidate), 'Confirmation is for a different frozen candidate')
    need(manifest.get('confirmation_plan_sha256') == digest(ar.load(session/'artifacts/confirmation_plan.json')), 'Confirmation plan mismatch')
    need(manifest.get('role') == 'fresh_confirmation', 'Declare fresh_confirmation role')
    for key in ('material_pair', 'context_id', 'data_kind', 'mode', 'observable', 'fixed_conditions', 'measurement_definition'):
        need(manifest.get(key) == task[key], f'Confirmation {key} mismatch')
    need(manifest.get('reserved_after_candidate_freeze') is True, 'Confirmation must be prospectively reserved after freezing the candidate')
    expected = 'synthetic_fixture' if task['data_kind'] == 'synthetic_demo' else 'reported_measurements'
    need(manifest.get('acquisition_status') == expected, 'Confirmation acquisition/provenance mismatch')
    need(isinstance(manifest.get('source_ref'), str) and bool(manifest['source_ref'].strip()), 'Confirmation source required')
    path = safe_child(base, manifest.get('dataset_file'))
    rows, checks = load_measurements(task, path)
    need(len(rows) > 0 and all(r['partition'] == 'holdout' for r in rows), 'Confirmation file must contain only holdout rows')
    prior = known_ids(session)
    for r in rows:
        need(r['sample_id'] not in prior['sample_ids'], 'Confirmation sample already used in this lineage')
        need(r['batch_id'] not in prior['batch_ids'], 'Confirmation batch already used in this lineage')
        need(not set(r['record_ids']) & set(prior['record_ids']), 'Confirmation record already used')
    plan = ar.load(session/'artifacts/confirmation_plan.json')
    protocol = ar.load(session/'input/comparison_protocol.json')
    fields = [f['name'] for f in task['factors']]
    # Require the declared coverage conditions; actual settings can differ within predeclared tolerances.
    used = set()
    for r in rows:
        matches = [c for c in plan['conditions'] if all(abs(r[k]-c['parameters'][k]) <= protocol['actual_setting_tolerances'][k]+1e-12 for k in fields)]
        need(bool(matches), 'Confirmation setting outside predeclared confirmation plan')
        used.add(matches[0]['condition_id'])
    need(used == {c['condition_id'] for c in plan['conditions']}, 'Confirmation coverage conditions are incomplete')
    return rows, checks


def attach_confirmation(session: Path, manifest_path: Path) -> dict:
    """Operator command; deliberately not in the LLM tool list."""
    ar = api()
    with ar.locked(session):
        s = ar.load(session/'state.json'); ar.verify_integrity(session, s)
        need(not s.get('confirmation_attached') and not s.get('next_round_started'), 'Confirmation already attached or next round started')
        man = ar.load(manifest_path); rows, checks = validate_confirmation(session, man, manifest_path.parent)
        dest = session/'confirmation_input'
        need(not dest.exists(), 'Confirmation input directory exists')
        tmp = session/'.confirmation_staging'; need(not tmp.exists(), 'Stale confirmation staging directory')
        tmp.mkdir()
        try:
            copied = copy.deepcopy(man); copied['dataset_file'] = 'measurements.csv'
            ar.save(tmp/'manifest.json', copied)
            shutil.copyfile(safe_child(manifest_path.parent, man['dataset_file']), tmp/'measurements.csv')
            tmp.rename(dest)
        finally:
            if tmp.exists(): shutil.rmtree(tmp)
        s['input_hashes'].update({str(p.relative_to(session)): ar.file_hash(p) for p in dest.iterdir()})
        s['confirmation_attached'] = True; s['phase'] = 'fresh_confirmation_attached'
        ar.save(session/'state.json', s)
        return {'status': s['phase'], 'n_rows': len(rows), 'check': checks,
                'operator_attached': True, 'used_for_fit': False, 'authenticity_verified': False}


def evaluate_update(session: Path, s: dict) -> dict:
    ar = api(); ar.required_skill(s, 'update')
    need(s.get('update_refitted'), 'Refit and freeze candidate first')
    if s.get('update_evaluated'): return ar.load(session/'artifacts/update_evaluation.json')
    candidate = ar.load(session/'artifacts/update_candidate.json')
    cal = copy.deepcopy(candidate['calibration']); p = policy(session)
    if not cal['numerical_fit_performed'] or not s.get('confirmation_attached'):
        return {'status': 'needs_fresh_confirmation' if cal['numerical_fit_performed'] else 'refit_failed',
                'promotion_allowed': False, 'calibration_only_next_round_allowed': True,
                'note': 'No fabricated holdout, automatic threshold relaxation or data recycling.'}
    task = ar.load(session/'update/task.json')
    confirm, checks = load_measurements(task, session/'confirmation_input/measurements.csv')
    train = ar.load(session/'artifacts/update_aggregated.json')
    x, y, g = arrays(confirm, task); tx, _, _ = arrays(train, task)
    model = FrozenModel(cal['model'], task['observable']); prediction = model.predict(x)
    scores = error_metrics(y, prediction, g)
    base = ar.load(session/'artifacts/calibration.json')
    previous_metrics = None
    if base.get('numerical_fit_performed'):
        oldx, _, _ = arrays([r for r in ar.load(session/'artifacts/aggregated.json') if r['partition'] == 'fit'], task)
        if in_training_domain(oldx, x).all():
            previous_metrics = error_metrics(y, FrozenModel(base['model'], task['observable']).predict(x), g)
    gates = {
        'cv_within_preset_tolerance': bool(cal.get('checks', {}).get('cv_within_preset_tolerance')),
        'cv_beats_constant_if_required': bool(cal.get('checks', {}).get('cv_beats_constant_if_required')),
        'positive_fit_and_cv_predictions': bool(cal.get('checks', {}).get('positive_fit_and_cv_predictions')),
        'fresh_independent_groups': len(set(g)) >= p['min_confirmation_groups'],
        'confirmation_inside_training_domain': bool(in_training_domain(tx, x).all()),
        'positive_confirmation_predictions': bool(np.all(prediction > 0)),
        'confirmation_within_preset_tolerance': scores['group_weighted_rmse_um'] <= task['acceptance']['max_holdout_rmse_um'],
        'non_degradation_if_comparable': (not p['require_non_degradation'] or previous_metrics is None or
             scores['group_weighted_rmse_um'] <= previous_metrics['group_weighted_rmse_um'] + p['max_rmse_increase_um']),
    }
    passed = all(gates.values())
    report = {
        'schema_version': '1.0', 'data_kind': task['data_kind'],
        'status': 'updated_model_passed_numeric_gates' if passed else 'updated_model_rejected',
        'promotion_allowed': passed, 'checks': gates, 'reasons': [k for k, v in gates.items() if not v],
        'new_model_confirmation': scores, 'previous_model_same_confirmation': previous_metrics,
        'candidate_sha256': digest(candidate), 'confirmation_sha256': ar.file_hash(session/'confirmation_input/measurements.csv'),
        'confirmation_was_used_for_fitting': False, 'hyperparameters_changed': False,
        'old_model_overwritten': False, 'confidence_interval': None, 'p_value': None,
        'fresh_confirmation_now_consumed': True, 'physical_validation_established': False,
        'sample_predictions': [{'sample_id': r['sample_id'], 'batch_id': r['batch_id'], 'measured_um': float(v),
                              'prediction_um': float(q), 'inside_domain': bool(ok)}
                for r, v, q, ok in zip(confirm, y, prediction, in_training_domain(tx, x))],
        'note': 'A predeclared development gate, not an unbiased estimate after model selection; final independent performance confirmation still needed.',
    }
    ar.artifact(session, s, 'update_evaluation.json', report)
    if passed:
        cal['holdout'] = scores; cal['holdout_groups'] = sorted(set(g))
        cal['model_usable_for_proposals'] = True; cal['status'] = 'numerical_gates_passed_not_physical_validation'
        cal['reasons'] = []; cal['checks'] = gates
        cal['holdout_rows'] = report['sample_predictions']
        cal['provenance'] = {'candidate_sha256': digest(candidate), 'confirmation_used_for_fit': False,
                             'fresh_confirmation_now_consumed': True}
        ar.artifact(session, s, 'accepted_update_calibration.json', cal)
    s['update_evaluated'] = True; s['phase'] = report['status']
    return report


def start_next_round(session: Path, s: dict, mode: str) -> dict:
    ar = api(); ar.required_skill(s, 'update')
    need(s.get('update_refitted'), 'Prepare and refit update before starting the next round')
    if s.get('next_round_started'):
        old = ar.load(session/'artifacts/next_round.json')
        need(old['mode'] == mode, 'Next round already created with a different mode')
        return old
    p = policy(session); idx = s.get('round_index', 1)
    need(idx < p['max_rounds'], 'Declared round budget exhausted; finish_report instead of silently extending')
    need(mode in {'validated_update', 'calibration_only'}, 'Unknown continuation mode')
    if mode == 'validated_update':
        need(s.get('update_evaluated'), 'Evaluate the candidate on fresh confirmation first')
        evaluation = ar.load(session/'artifacts/update_evaluation.json')
        need(evaluation['promotion_allowed'], 'Updated model failed gates; use calibration_only')
        accepted = ar.load(session/'artifacts/accepted_update_calibration.json')
    else:
        accepted = copy.deepcopy(ar.load(session/'artifacts/update_candidate.json')['calibration'])
        accepted['model_usable_for_proposals'] = False
        accepted['status'] = 'calibration_only_continuation_no_validated_predictions'
    target = session/'next_round'; need(not target.exists(), 'Next-round folder already exists')
    evidence = session/'input/evidence.json'
    ar.init_session(session/'update/task.json', target, protocol_path=session/'input/comparison_protocol.json',
        evidence_path=evidence if evidence.exists() else None, origin=s['origin'], update_policy_path=session/'input/update_policy.json')
    child = ar.load(target/'state.json'); child['round_index'] = idx+1; child['parent_round_id'] = s['session_id']
    child['session_id'] = f"{s.get('campaign_id', s['session_id'])}-round-{idx+1:02d}"
    child['campaign_id'] = s.get('campaign_id', s['session_id']); child['lineage_ids'] = known_ids(session)
    child['inherited_model'] = {'mode': mode, 'parent_candidate_sha256': digest(ar.load(session/'artifacts/update_candidate.json')),
                               'new_confirmation_not_claimed_for_child': True}
    rows, check = load_measurements(ar.load(target/'input/task.json'), target/'input/measurements.csv')
    ar.artifact(target, child, 'aggregated.json', rows); ar.artifact(target, child, 'data_check.json', check)
    ar.artifact(target, child, 'calibration.json', accepted)
    child['inspected'] = True; child['calibrated'] = True
    if evidence.exists():
        ar.artifact(target, child, 'evidence_check.json', ar.load(session/'artifacts/evidence_check.json'))
        child['evidence_checked'] = True
    child['phase'] = 'calibrated' if mode == 'validated_update' else 'needs_calibration_design'
    link = {'parent_candidate_sha256': digest(ar.load(session/'artifacts/update_candidate.json')),
            'parent_update_dataset_sha256': ar.file_hash(session/'update/measurements.csv'),
            'mode': mode, 'round_index': idx+1, 'data_kind': s['data_kind']}
    ar.artifact(target, child, 'parent_link.json', link)
    ar.save(target/'state.json', child)
    result = {'status': 'next_round_ready', 'round_index': idx+1, 'mode': mode,
              'next_session': 'next_round', 'data_kind': s['data_kind'],
              'parent_model_and_results_preserved': True, 'fresh_holdout_reused': False,
              'next': 'Switch host to the next_round session; select planning skill and generate a new proposal. No experiments are executed.'}
    ar.artifact(session, s, 'next_round.json', result); s['next_round_started'] = True; s['phase'] = 'next_round_ready'
    return result


def execute(session: Path, state: dict, name: str, args: dict) -> dict:
    if name == 'refit_update': return refit_update(session, state)
    if name == 'evaluate_update': return evaluate_update(session, state)
    if name == 'start_next_round': return start_next_round(session, state, args['mode'])
    raise ValueError('Unknown round tool')
