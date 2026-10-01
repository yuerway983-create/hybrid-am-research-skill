"""Bounded stateful tool dispatcher for a host LLM; this is not an LLM itself.

Inputs are snapshotted at session creation, tools are explicit Python functions,
reviewed skills are activated per stage, and outputs are recorded before returning.
No arbitrary shell/Python, network, model editing, approvals or printer commands.
"""
from __future__ import annotations

import copy
import hashlib
import html
import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from _core import file_hash
from calibration_planning import (InputError, need, validate_task, load_measurements,
    safe_child, calibrate, propose, write_csv)
from feedback_tools import (digest, validate_protocol, FrozenModel, import_feedback,
                            compare_feedback)
from review_evidence import validate_packet

ROOT = Path(__file__).resolve().parents[1]
STAGES = ['evidence', 'calibration', 'planning', 'feedback', 'update']
ORIGINS = ['chat_host', 'openai_responses', 'deterministic_demo', 'test']


def save(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(payload, encoding='utf-8')
    os.replace(tmp, path)


def load(path: Path) -> Any:
    need(path.is_file() and path.stat().st_size <= 12_000_000, 'JSON missing or over size limit')
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda s: (_ for _ in ()).throw(InputError('Nonfinite JSON value')))


def tool(name: str, description: str, props: dict | None = None) -> dict:
    props = props or {}
    return {'type': 'function', 'name': name, 'description': description,
            'strict': True, 'parameters': {'type': 'object', 'properties': props,
                'required': list(props), 'additionalProperties': False}}


TOOLS = [
    tool('session_status', 'Read current stage, task summary, available next actions and already saved results.'),
    tool('inspect_task', 'Validate the frozen task and CSV, aggregate technical repeats and expose data quality counts.'),
    tool('find_skills', 'Find suitable candidates from the reviewed registry. A missing capability yields a host GitHub discovery request; never silently install.',
         {'stage': {'type': 'string', 'enum': STAGES}}),
    tool('activate_skill', 'Load a reviewed local SKILL.md for this stage. Record a short evidence-based selection reason, not private reasoning.',
         {'stage': {'type': 'string', 'enum': STAGES}, 'skill_id': {'type': 'string'},
          'rationale': {'type': 'string', 'description': 'Short selection reason; maximum 1200 characters.'}}),
    tool('review_evidence', 'Check the preauthorized frozen evidence packet and return source locations and scope. This is NOT a new literature search.'),
    tool('calibrate_response', 'Fit the response using the activated calibration skill, then evaluate grouped CV and preset holdout gates. Do not change the model or tolerances.'),
    tool('plan_experiments', 'Execute the activated planning skill. Passing models give bounded target/coverage/baseline proposals; failing models give calibration-only proposals.'),
    tool('import_results', 'Import only the operator-attached feedback manifest, actual execution log and measured CSV. Freeze/model predictions are not refit first.'),
    tool('compare_results', 'Compare new independent samples to concurrent baseline, score the frozen model and report descriptive changes, including null/negative outcomes.'),
    tool('prepare_update', 'Export an updated fitting dataset WITHOUT overwriting history. Retire consumed holdout to a separate file and request fresh confirmation data.'),
    tool('refit_update', 'Fit a NEW frozen candidate on exported fit data only; retire consumed holdouts and produce a prospective confirmation plan.'),
    tool('evaluate_update', 'Score frozen updated model on operator-attached fresh confirmation, then apply unchanged validation and non-degradation gates.'),
    tool('start_next_round', 'Create a versioned child round with an accepted updated model, or calibration-only without validated predictions. Never prints or generates data.',
         {'mode': {'type': 'string', 'enum': ['validated_update', 'calibration_only']}}),
    tool('finish_report', 'Write a static evidence-linked progress report from actual results. Does not invent missing stages or execute experiments.'),
]
SCHEMAS = {t['name']: t['parameters'] for t in TOOLS}


def check_args(name: str, args: Any) -> None:
    need(name in SCHEMAS, 'Unknown tool; arbitrary execution is not allowed')
    schema = SCHEMAS[name]
    need(isinstance(args, dict) and set(args) == set(schema['properties']), 'Tool arguments must match exactly')
    for k, spec in schema['properties'].items():
        value = args[k]
        need(isinstance(value, str) and 0 < len(value.strip()) <= 1200, f'Invalid {k}')
        if 'enum' in spec: need(value in spec['enum'], f'Unsupported {k}')


def registry() -> list[dict]:
    return load(ROOT/'registry/runtime-skills.json')['skills']


def source_hashes() -> dict:
    paths = [ROOT/'scripts'/s for s in ('agent_runtime.py', 'feedback_tools.py', 'calibration_planning.py', '_core.py', 'review_evidence.py', 'round_tools.py')]
    paths += [ROOT/'registry/runtime-skills.json']
    paths += [ROOT/r['local_path'] for r in registry() if r.get('implemented')]
    return {str(p.relative_to(ROOT)): file_hash(p) for p in paths}


@contextmanager
def locked(session: Path):
    lock = session/'.call.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as e:
        raise InputError('Session busy/stale lock. Verify no call is running before manually removing .call.lock') from e
    try:
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def init_session(task_path: Path, session: Path, *, protocol_path: Path, origin: str,
                 evidence_path: Path | None = None, update_policy_path: Path | None = None) -> dict:
    need(origin in ORIGINS, 'Explicit supported origin required')
    need(not session.exists(), 'Session exists: resume it or choose a new directory')
    task = load(task_path); validate_task(task)
    dataset = safe_child(task_path.parent, task['dataset_file'])
    load_measurements(task, dataset)  # reject invalid data before creating outputs
    protocol = load(protocol_path); validate_protocol(protocol, task)
    if evidence_path is not None:
        need(validate_packet(load(evidence_path))['valid'], 'Evidence packet failed structure checks')
    from round_tools import DEFAULT_POLICY, validate_policy
    update_policy = load(update_policy_path) if update_policy_path else copy.deepcopy(DEFAULT_POLICY)
    validate_policy(update_policy)
    session.mkdir(parents=True)
    inp = session/'input'; inp.mkdir()
    snap = copy.deepcopy(task); snap['dataset_file'] = 'measurements.csv'
    save(inp/'task.json', snap); shutil.copyfile(dataset, inp/'measurements.csv')
    save(inp/'comparison_protocol.json', protocol)
    save(inp/'update_policy.json', update_policy)
    if evidence_path: shutil.copyfile(evidence_path, inp/'evidence.json')
    state = {'version': '1.0.0', 'origin': origin, 'session_id': session.name,
        'task_id': task['task_id'], 'phase': 'ready_for_inspection', 'data_kind': task['data_kind'],
        'observable': task['observable'], 'active_skills': {}, 'inspected': False,
        'evidence_checked': False, 'calibrated': False, 'planned': False,
        'feedback_attached': False, 'imported': False, 'compared': False, 'update_prepared': False,
        'artifacts': {}, 'call_ids': {}, 'blocked_calls': 0, 'max_calls': 80,
        'source_hashes': source_hashes(),
        'input_hashes': {str(p.relative_to(session)): file_hash(p) for p in inp.iterdir()},
        'round_index': 1, 'campaign_id': session.name, 'lineage_ids': {},
        'update_refitted': False, 'confirmation_attached': False, 'update_evaluated': False,
        'next_round_started': False, 'upstream_auto_install': False, 'hardware_execution_allowed': False,
        'dedicated_simulation_software_allowed': False,
        'origin_is_operator_declared_not_independent_attestation': True}
    save(session/'state.json', state)
    return {'session': str(session), 'status': state['phase'], 'data_kind': task['data_kind']}


def attach_feedback(session: Path, manifest_path: Path) -> dict:
    """OPERATOR operation, not available to the model as a tool."""
    with locked(session):
        state = load(session/'state.json')
        verify_integrity(session, state)
        need(state['planned'] and not state['feedback_attached'], 'Need a frozen plan and no previous feedback attachment')
        obj = load(manifest_path)
        task = load(session/'input/task.json'); protocol = load(session/'input/comparison_protocol.json')
        need(obj.get('plan_sha256') == digest(load(session/'artifacts/plan.json')), 'Attachment plan hash mismatch')
        need(obj.get('comparison_protocol_sha256') == digest(protocol), 'Attachment protocol hash mismatch')
        need(obj.get('data_kind') == task['data_kind'], 'Synthetic/measured attachment mismatch')
        paths = [safe_child(manifest_path.parent, obj.get(k)) for k in ('dataset_file', 'execution_file')]
        for p in paths: need(p.is_file() and p.stat().st_size <= 10_000_000, 'Feedback file missing or too large')
        dest = session/'feedback_input'; need(not dest.exists(), 'Feedback directory exists')
        dest.mkdir()
        new = copy.deepcopy(obj); new['dataset_file'] = 'measurements.csv'; new['execution_file'] = 'executions.csv'
        save(dest/'manifest.json', new)
        for p, name in zip(paths, ('measurements.csv', 'executions.csv')): shutil.copyfile(p, dest/name)
        state['input_hashes'].update({str(p.relative_to(session)): file_hash(p) for p in dest.iterdir()})
        state['feedback_attached'] = True; state['phase'] = 'feedback_ready_for_import'
        save(session/'state.json', state)
        return {'status': state['phase'], 'operator_attached': True, 'measurements_validated': False}


def attach_evidence(session: Path, packet_path: Path) -> dict:
    """Attach host-retrieved evidence; this operator operation does not perform search."""
    with locked(session):
        s = load(session/'state.json'); verify_integrity(session, s)
        need(not s['evidence_checked'] and not (session/'input/evidence.json').exists(),
             'Evidence already attached/consumed; use a new reviewed session for replacements')
        packet = load(packet_path); check = validate_packet(packet)
        need(check['valid'], 'Evidence packet failed structural validation')
        save(session/'input/evidence.json', packet)
        s['input_hashes']['input/evidence.json'] = file_hash(session/'input/evidence.json')
        save(session/'state.json', s)
        return {'status':'evidence_attached_needs_skill_review', 'source_count': len(packet.get('sources',[])),
                'online_search_performed_by_this_command':False, 'semantic_claims_certified':False}


def verify_integrity(session: Path, state: dict) -> None:
    for rel, expected in state['input_hashes'].items():
        p = safe_child(session, rel)
        need(p.is_file() and file_hash(p) == expected, f'Frozen input changed: {rel}')
    for rel, expected in state['source_hashes'].items():
        p = safe_child(ROOT, rel)
        need(p.is_file() and file_hash(p) == expected, f'Approved code/skill changed: {rel}; create a reviewed new session')
    for rel, expected in state['artifacts'].items():
        p = safe_child(session, rel)
        need(p.is_file() and file_hash(p) == expected, f'Frozen artifact changed: {rel}')


def artifact(session: Path, state: dict, name: str, obj: Any) -> None:
    rel = 'artifacts/'+name
    need(rel not in state['artifacts'] and not (session/rel).exists(), 'Artifact already exists; immutable results are not overwritten')
    save(session/rel, obj); state['artifacts'][rel] = file_hash(session/rel)


def required_skill(state: dict, stage: str) -> str:
    sid = state['active_skills'].get(stage)
    need(sid is not None, f'Select and activate a {stage} skill before execution')
    return sid


def next_actions(s: dict) -> list[str]:
    if not s['inspected']: return ['inspect_task']
    if not s['evidence_checked']: return ['find_skills(evidence)', 'activate_skill', 'review_evidence']
    if not s['calibrated']: return ['find_skills(calibration)', 'activate_skill', 'calibrate_response']
    if not s['planned']: return ['find_skills(planning)', 'activate_skill', 'plan_experiments']
    if not s['feedback_attached']: return ['finish_report', 'WAIT: operator must attach new reported measurements; never invent them']
    if not s['imported']: return ['find_skills(feedback)', 'activate_skill', 'import_results']
    if not s['compared']: return ['compare_results']
    if not s['update_prepared']: return ['find_skills(update)', 'activate_skill', 'prepare_update', 'finish_report']
    if s.get('next_round_started'): return ['finish_report', 'SWITCH_SESSION: next_round; select the planning skill there']
    if not s.get('update_refitted'): return ['find_skills(update)', 'activate_skill', 'refit_update']
    if not s.get('confirmation_attached'): return ['finish_report', 'WAIT: operator may attach fresh confirmation; or start_next_round(calibration_only)']
    if not s.get('update_evaluated'): return ['evaluate_update']
    return ['start_next_round(validated_update) only when promotion_allowed; otherwise start_next_round(calibration_only)', 'finish_report']


def _execute(session: Path, s: dict, name: str, args: dict) -> dict:
    task = load(session/'input/task.json')
    if name in {'refit_update', 'evaluate_update', 'start_next_round'}:
        from round_tools import execute
        return execute(session, s, name, args)
    if name == 'session_status':
        return {'phase': s['phase'], 'data_kind': s['data_kind'], 'observable': s['observable'],
                'next_actions': next_actions(s), 'active_skills': s['active_skills'], 'artifacts': s['artifacts'],
                'feedback_attached': s['feedback_attached'], 'round_index': s.get('round_index', 1),
                'confirmation_attached': s.get('confirmation_attached', False),
                'next_session': 'next_round' if s.get('next_round_started') else None,
                'inherited_model': s.get('inherited_model')}
    if name == 'find_skills':
        matches = [r for r in registry() if args['stage'] in r['stages']]
        return {'stage': args['stage'], 'candidates': matches, 'selection_made': False,
                'discovery_mode': 'reviewed_registry_not_new_GitHub_search',
                'missing_capability_action': 'Ask host to search GitHub, inspect source and register an approved adapter; do not run fetched code'}
    if name == 'activate_skill':
        sid = args['skill_id']; stage = args['stage']
        rs = [r for r in registry() if r['skill_id'] == sid and stage in r['stages']]
        need(len(rs) == 1 and rs[0]['implemented'], 'Skill not implemented/reviewed for this stage')
        spec = rs[0]; content = (ROOT/spec['local_path']).read_text(encoding='utf-8')
        need(len(content) < 16000, 'Skill content too long')
        s['active_skills'][stage] = sid
        return {'activated': sid, 'stage': stage, 'rationale': args['rationale'], 'instructions': content,
                'instructions_sha256': file_hash(ROOT/spec['local_path']), 'upstream': spec['upstream'],
                'upstream_original_script_executed': False}
    if name == 'inspect_task':
        if s['inspected']: return {'status': 'already_inspected', **load(session/'artifacts/data_check.json')}
        rows, check = load_measurements(task, session/'input/measurements.csv')
        artifact(session,s,'aggregated.json',rows); artifact(session,s,'data_check.json',check)
        s['inspected'] = True; s['phase'] = 'data_inspected_needs_evidence'
        return {'status': s['phase'], 'task': task, 'check': check}
    if name == 'review_evidence':
        required_skill(s,'evidence'); need(s['inspected'], 'Inspect task first')
        path = session/'input/evidence.json'
        need(path.exists(), 'needs_host_retrieval: no approved evidence packet attached; perform actual retrieval externally')
        if s['evidence_checked']: return load(session/'artifacts/evidence_check.json')
        packet = load(path); check = validate_packet(packet); need(check['valid'], 'Evidence packet failed checks')
        artifact(session,s,'evidence_check.json',check)
        s['evidence_checked'] = True; s['phase'] = 'evidence_checked_needs_calibration'
        return {'status': s['phase'], 'check': check, 'question': packet['question'],
                'claims': packet['claims'], 'unresolved_gaps': packet.get('unresolved_gaps',[]),
                'note': 'Frozen evidence replay only; no live literature retrieval performed by this tool'}
    if name == 'calibrate_response':
        required_skill(s,'calibration'); need(s['inspected'] and s['evidence_checked'], 'Inspect task and review evidence first')
        if s['calibrated']: return load(session/'artifacts/calibration.json')
        cal, _ = calibrate(task,load(session/'artifacts/aggregated.json'))
        artifact(session,s,'calibration.json',cal)
        s['calibrated'] = True; s['phase'] = 'calibrated' if cal['model_usable_for_proposals'] else 'needs_calibration_design'
        return {'status': s['phase'], 'calibration': cal, 'next_actions': next_actions(s)}
    if name == 'plan_experiments':
        required_skill(s,'planning'); need(s['calibrated'], 'Calibrate or assess insufficient data first')
        if s['planned']: return load(session/'artifacts/plan.json')
        cal = load(session/'artifacts/calibration.json'); model = None
        if s['active_skills']['planning'] == 'bounded-experiment-planning':
            need(cal['model_usable_for_proposals'], 'Predictive gates failed: activate calibration-only-planning')
        else:
            cal = copy.deepcopy(cal); cal['model_usable_for_proposals'] = False
        if cal['numerical_fit_performed']:
            model = (cal['model']['a_um2'],cal['model']['b_um2_s']) if task['observable']=='concentration_sigma_um' else FrozenModel(cal['model'],task['observable'])
        plan = propose(task,load(session/'artifacts/aggregated.json'),cal,model)
        candidates = plan.pop('candidate_rows'); artifact(session,s,'candidate_results.json',candidates)
        artifact(session,s,'plan.json',plan)
        fields = [f['name'] for f in task['factors']]
        write_csv(session/'artifacts/next_experiments.csv',[{'trial_id':t['trial_id'],'purpose':t['purpose'], 'run_order':t['run_order'],
            **t['parameters'],'predicted_response_um':t['predicted_response_um'],'data_kind':task['data_kind'],'state':'suggested'} for t in plan['trials']])
        s['artifacts']['artifacts/next_experiments.csv'] = file_hash(session/'artifacts/next_experiments.csv')
        s['planned'] = True; s['phase'] = 'awaiting_external_experiment'
        return {'status': s['phase'], 'plan': plan, 'plan_sha256':digest(plan),
                'comparison_protocol_sha256':digest(load(session/'input/comparison_protocol.json')),
                'note':'Parameters are suggested, not approved/executed. Await operator-attached data.'}
    if name == 'import_results':
        required_skill(s,'feedback'); need(s['planned'] and s['feedback_attached'], 'No attached feedback: wait for operator; do not invent new measurements')
        if s['imported']: return load(session/'artifacts/feedback.json')
        result = import_feedback(task,load(session/'artifacts/aggregated.json'),load(session/'artifacts/calibration.json'),
            load(session/'artifacts/plan.json'),load(session/'feedback_input/manifest.json'),session/'feedback_input',load(session/'input/comparison_protocol.json'))
        for item in result['samples']:
            prior = s.get('lineage_ids', {})
            need(item['sample_id'] not in prior.get('sample_ids', []), 'Feedback sample already consumed by an earlier round')
            need(item['batch_id'] not in prior.get('batch_ids', []), 'Feedback batch already consumed by an earlier round')
        artifact(session,s,'feedback.json',result); s['imported']=True; s['phase']='feedback_imported'
        return result
    if name == 'compare_results':
        required_skill(s,'feedback'); need(s['imported'], 'Import actual/report-labelled feedback first')
        if s['compared']: return load(session/'artifacts/comparison.json')
        result=compare_feedback(task,load(session/'artifacts/feedback.json'),load(session/'artifacts/plan.json'),load(session/'input/comparison_protocol.json'))
        artifact(session,s,'comparison.json',result); s['compared']=True; s['phase']='feedback_evaluated'
        return result
    if name == 'prepare_update':
        required_skill(s,'update'); need(s['compared'], 'Score frozen predictions and compare before any update')
        if s['update_prepared']: return load(session/'artifacts/update_manifest.json')
        hist=load(session/'artifacts/aggregated.json'); new=load(session/'artifacts/feedback.json')['samples']
        folder=session/'update'; folder.mkdir()
        fields=[f['name'] for f in task['factors']]
        columns=['record_id','sample_id','batch_id','material_pair','context_id','data_kind','source_ref','partition',*fields,'response_um']
        def row(r, idx, part, prefix):
            pars=r.get('actual_parameters') or {k:r[k] for k in fields}
            return {'record_id':f'{prefix}-{idx}','sample_id':r['sample_id'],'batch_id':r['batch_id'],
                **{k:task[k] for k in ('material_pair','context_id','data_kind')},'source_ref':'; '.join(r['source_refs']),
                'partition':part,**pars,'response_um':r['response_um']}
        # Former holdout is retired, not quietly recycled as independent validation.
        fitting=[row(r,i,'fit','historical') for i,r in enumerate(hist) if r['partition']=='fit']
        fitting += [row(r,i,'fit','followup') for i,r in enumerate(new) if r['eligible_intended_comparison']]
        retired=[row(r,i,'holdout','retired') for i,r in enumerate(hist) if r['partition']=='holdout']
        write_csv(folder/'measurements.csv',fitting,columns); write_csv(folder/'retired_holdout.csv',retired,columns)
        update=copy.deepcopy(task);update['task_id'] += '-update-01';update['dataset_file']='measurements.csv'
        update['holdout_policy']='No new independent holdout attached. Prior holdout retired; follow-up now development data.'
        save(folder/'task.json',update)
        manifest={'status':'update_dataset_prepared_fresh_confirmation_required','new_fit_rows':len(fitting),
            'retired_holdout_rows':len(retired),'excluded_deviation_samples':[r['sample_id'] for r in new if not r['eligible_intended_comparison']],
            'original_data_modified':False,'automatic_refit_performed':False,'fresh_independent_validation_required':True,
            'prior_comparison_sha256':digest(load(session/'artifacts/comparison.json')),
            'data_kind':task['data_kind'],'task':'update/task.json','dataset':'update/measurements.csv'}
        artifact(session,s,'update_manifest.json',manifest)
        for p in folder.iterdir():s['artifacts'][str(p.relative_to(session))]=file_hash(p)
        s['update_prepared']=True;s['phase']='update_prepared_waiting_fresh_confirmation'
        return manifest
    if name == 'finish_report':
        return make_report(session,s)
    raise InputError('Unhandled tool')


def make_report(session: Path, state: dict) -> dict:
    task=load(session/'input/task.json')
    lines=['# Hybrid-AM v1.0 执行与回传报告','',f"数据标记：**{state['data_kind']}**；执行来源：`{state['origin']}`。",
        f"当前状态：`{state['phase']}`。",'本程序没有打印、没有运行专用模拟软件。来源标记由操作者声明，不是独立真实性认证。','',
        '## 实际完成阶段',json.dumps({k:state[k] for k in ('inspected','evidence_checked','calibrated','planned','feedback_attached','imported','compared','update_prepared')},ensure_ascii=False,indent=2)]
    if state['planned']:
        lines += ['','## 候选实验（未由软件批准或执行）','| 编号 | 目的 | 参数 | 冻结预测 μm |','|---|---|---|---|']
        for t in load(session/'artifacts/plan.json')['trials']:
            lines.append(f"| {t['trial_id']} | {t['purpose']} | {json.dumps(t['parameters'])} | {t['predicted_response_um']} |")
    if state['compared']:
        c=load(session/'artifacts/comparison.json')
        lines += ['','## 回传数据的描述性对照','不是统计显著性结论。合成数据的任何改善或变差都不是实际制造成果。',
            '| 编号 | 独立组数 | 平均目标绝对误差 μm | 冻结模型RMSE μm |','|---|---|---|---|']
        for t in c['per_trial']:
            lines.append(f"| {t['trial_id']} | {t['n_independent_units']} | {t['mean_absolute_target_error_um']} | {t['frozen_prediction_rmse_um']} |")
        for r in c['contrasts']:
            lines.append(f"\n{r['trial_id']}: {r['verdict']}；同批基准误差减去候选误差={r['mean_absolute_error_reduction_um']} μm；共享批次={r['n_matched_batches']}。")
        lines += ['','不推断界面强度、疲劳或器件性能；没有置信区间与p值。']
    if state.get('update_refitted'):
        u=load(session/'artifacts/update_candidate.json')
        lines += ['', '## 冻结候选模型', f"状态：{u['status']}；只拟合update/measurements.csv，未使用确认数据。"]
    if state.get('update_evaluated'):
        u=load(session/'artifacts/update_evaluation.json')
        lines += ['', '## 新模型验收', f"状态：{u['status']}；允许用于下一轮候选预测：{u['promotion_allowed']}。",
                  json.dumps(u['checks'],ensure_ascii=False), '确认数据验收后即成为已使用数据，不再算独立测试。']
    if state.get('next_round_started'):
        lines += ['', '## 下一轮已创建', '进入next_round/，继续由主控选择规划Skill。没有执行真实打印。']
    lines += ['','## 下一步']+next_actions(state)+['','## 审计','events.jsonl 记录实际请求、响应、调用来源、哈希与错误；calls/保留结构化结果。',
        '程序日志证明代码执行，不证明实验真实性；固定回放不是在线LLM运行。']
    report=session/'report.md';report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    title='Hybrid-AM · v1.0'
    body=f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title><style>body{{font-family:system-ui,sans-serif;max-width:1000px;margin:36px auto;padding:0 20px;line-height:1.65}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}h1{{font-size:28px}}</style><h1>{title}</h1><p>实际工具执行记录 · {html.escape(state['data_kind'])} · {html.escape(state['origin'])}</p><pre>{html.escape(report.read_text())}</pre></html>"
    (session/'index.html').write_text(body,encoding='utf-8')
    return {'status':'report_written','phase':state['phase'],'files':['report.md','index.html'],
            'report_sha256':file_hash(report),'data_kind':state['data_kind']}


def dispatch(session: Path, name: str, args: Any, call_id: str, *, origin: str) -> dict:
    need(re.fullmatch(r'[A-Za-z0-9_-]{1,96}',call_id) is not None,'Invalid call id')
    need(origin in ORIGINS,'Explicit call origin required')
    with locked(session):
        s=load(session/'state.json'); signature=digest({'tool':name,'args':args})
        need(s['origin']==origin, 'Call origin differs from session origin')
        if call_id in s['call_ids']:
            need(s['call_ids'][call_id]==signature,'Call-id collision: arguments changed')
            old=load(session/'calls'/f'{call_id}.json');return {**old,'idempotent_replay':True}
        need(len(s['call_ids'])<s['max_calls'],'Tool call budget exhausted')
        started=time.time(); working=copy.deepcopy(s)
        try:
            verify_integrity(session,s);check_args(name,args)
            value=_execute(session,working,name,args)
            envelope={'ok':True,'call_id':call_id,'tool':name,'result':value,'idempotent_replay':False}
            s=working
        except (InputError,ValueError,TypeError,KeyError,OSError) as exc:
            # Scientific/input errors preserve prior state. No automatic threshold changes.
            envelope={'ok':False,'call_id':call_id,'tool':name,'error':{'code':type(exc).__name__,'message':str(exc)},
                      'next_actions':next_actions(s),'idempotent_replay':False}
            s['blocked_calls']+=1
        save(session/'calls'/f'{call_id}.json',envelope)
        eventfile=session/'events.jsonl'
        prior='0'*64
        if eventfile.exists():
            oldlines=eventfile.read_text(encoding='utf-8').splitlines()
            if oldlines:prior=json.loads(oldlines[-1])['event_sha256']
        event={'sequence':len(s['call_ids'])+1,'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'call_id':call_id,'origin':origin,'tool':name,'arguments':args,'ok':envelope['ok'],
            'elapsed_seconds':round(time.time()-started,6),'response_sha256':digest(envelope),
            'previous_event_sha256':prior,'phase_after':s['phase'],'data_kind':s['data_kind']}
        event['event_sha256']=digest(event)
        with eventfile.open('a',encoding='utf-8') as f:f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
        s['call_ids'][call_id]=signature;save(session/'state.json',s)
        return envelope


def verify_audit(session: Path) -> dict:
    prior='0'*64;count=0
    for line in (session/'events.jsonl').read_text(encoding='utf-8').splitlines():
        e=json.loads(line);sha=e.pop('event_sha256')
        need(e['previous_event_sha256']==prior and digest(e)==sha,'Event chain mismatch')
        response=load(session/'calls'/f"{e['call_id']}.json")
        need(digest(response)==e['response_sha256'],'Stored tool response mismatch')
        prior=sha;count+=1
    return {'valid':True,'events':count,'note':'Local integrity checks, not an externally signed attestation.'}
