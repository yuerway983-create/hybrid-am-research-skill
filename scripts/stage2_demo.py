"""Replay the frozen evidence pass and run a synthetic diffusion kernel; no live retrieval."""
from __future__ import annotations
import argparse
import csv
import json
import platform
from pathlib import Path
from datetime import datetime, timezone
from _core import load_json, write_json, file_hash
from review_evidence import validate_packet, render_summary
from diffusion_model import evaluate_case

ROOT=Path(__file__).resolve().parents[1]


def run(out: Path, symbolic: bool=False) -> dict:
    if out.exists(): raise ValueError('Output exists; select a new run directory')
    packet_file=ROOT/'evidence/delay-evidence-001/evidence_packet.json'
    case_file=ROOT/'examples/diffusion-demo/case.json'
    packet=load_json(packet_file)
    checks=validate_packet(packet)
    if not checks['valid']: raise ValueError('Evidence structure invalid: '+ '; '.join(checks['errors']))
    # Require a recorded distinction between the paper equation and the project extension.
    claims={c['claim_id']:c for c in packet['claims']}
    if claims.get('C2',{}).get('status')!='project_inference':
        raise ValueError('Finite initial-width extension must retain its project-inference label')
    numeric=evaluate_case(load_json(case_file),case_file.parent)
    if not numeric['prediction_performed']: raise ValueError('Synthetic kernel failed input checks')
    missing=evaluate_case(load_json(ROOT/'examples/diffusion-demo/missing-calibration.json'))
    unsupported=evaluate_case(load_json(ROOT/'examples/diffusion-demo/wrong-observable.json'))
    if missing['prediction_performed'] or unsupported['prediction_performed']:
        raise ValueError('Expected stop condition failed')
    out.mkdir(parents=True)
    write_json(out/'evidence_check.json',checks)
    (out/'evidence_summary.md').write_text(render_summary(packet,checks),encoding='utf-8')
    write_json(out/'synthetic_result.json',numeric)
    write_json(out/'missing_calibration_result.json',missing)
    write_json(out/'unsupported_observable_result.json',unsupported)
    write_json(out/'calibration_request.json',load_json(ROOT/'evidence/delay-evidence-001/calibration_request.json'))
    with (out/'synthetic_moments.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(numeric['rows'][0]));w.writeheader();w.writerows(numeric['rows'])
    actions=[('evidence','cached_packet_structure_checked'),('numeric','synthetic_moments_computed'),
             ('negative_case','missing_parameter_correctly_blocked'),('negative_case','geometric_width_correctly_blocked')]
    sym={'status':'not_requested','physical_validation_performed':False}
    if symbolic:
        try:
            from verify_diffusion_symbolic import verify
            sym=verify()
        except ImportError:
            sym={'status':'dependency_missing','required':'sympy','physical_validation_performed':False}
        write_json(out/'symbolic_checks.json',sym)
        actions.append(('symbolic',sym['status']))
    now=lambda:datetime.now(timezone.utc).isoformat()
    with (out/'events.jsonl').open('w',encoding='utf-8') as f:
        for stage,action in actions:
            f.write(json.dumps({'time_utc':now(),'stage':stage,'action':action,'run_mode':'offline_replay_and_synthetic_calculation'},ensure_ascii=False)+'\n')
    state={
      'version':'0.2.0','run_mode':'offline_replay_and_synthetic_calculation',
      'status':'evidence_and_kernel_ready_real_calibration_pending',
      'current_stage':'lightweight_model_kernel',
      'literature_original_creation_mode':packet['creation_mode'],
      'live_literature_search_in_this_run':False,'live_github_search_in_this_run':False,
      'automatic_skill_routing_in_this_script':False,'external_llm_api_called':False,
      'upstream_provider_runner_executed':False,
      'numeric_demo_performed':True,'symbolic_check_status':sym['status'],
      'parameter_optimisation_performed':False,'geometric_width_predicted':False,
      'physical_printing_performed':False,'physical_validation_performed':False,
      'dedicated_simulation_software_called':False,
      'negative_cases_correctly_blocked':2,
      'evidence_sha256':file_hash(packet_file),'case_sha256':file_hash(case_file),
      'python_version':platform.python_version(),'timestamp_utc':now(),
      'next_action':'Obtain same-material concentration calibration or geometric-width data with a defined observation model. Do not claim manufacturing improvement.'}
    write_json(out/'run_state.json',state)
    for name in ('literature-001','model-001'):
        write_json(out/(name+'.json'),load_json(ROOT/f'registry/reviews/{name}.json'))
    lines=['# v0.2 离线演示结果','','**这是已完成文献工作的离线回放＋合成参数计算，不是新一次联网运行。**','',
           f"文献结构检查：通过，{checks['source_count']}个来源，{checks['claim_count']}条判断。",
           f"合成计算：{len(numeric['rows'])}个时间点；缺参数与不支持的输出两个案例均停止。",
           f"符号检查：{sym['status']}。",'',
           '当前输出是浓度分布标准差/方差/高斯半高全宽，不是打印轨迹几何宽度。',
           '情景上下界只传播给定 D 的范围，不是有统计覆盖率的置信区间。','',
           '下一步需要材料标定或明确的几何观测关系。尚未优化打印参数，未打印或测试真实样品。']
    (out/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return state


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--symbolic',action='store_true',help='Also use installed SymPy; never install dependencies automatically')
    a=ap.parse_args()
    try:state=run(a.out,a.symbolic)
    except (ValueError,OSError,TypeError) as e:ap.error(str(e))
    print(json.dumps(state,ensure_ascii=False,indent=2))
    return 2 if state['symbolic_check_status'] in {'failed','dependency_missing'} else 0

if __name__=='__main__':raise SystemExit(main())
