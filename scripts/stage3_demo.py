"""Offline stage-3 replay: inherited evidence + two calibration routes + stop cases."""
from __future__ import annotations
import argparse
import copy
import html
import json
from pathlib import Path
from _core import load_json, write_json, file_hash
from review_evidence import validate_packet
from calibration_planning import run, validate_task, InputError
ROOT=Path(__file__).resolve().parents[1]


def main_run(out: Path) -> dict:
    if out.exists():raise ValueError('Output exists; use a new directory')
    packet=ROOT/'evidence/delay-evidence-001/evidence_packet.json'
    evidence=validate_packet(load_json(packet))
    if not evidence['valid']:raise ValueError('Inherited evidence packet structure failed')
    out.mkdir(parents=True)
    write_json(out/'evidence_check.json',evidence)
    cases={}
    for name,folder in [('geometric_width','width-calibration-demo'),('concentration_sigma','sigma-calibration-demo'),('insufficient_data','insufficient-data-demo')]:
        cases[name]=run(ROOT/'examples'/folder/'task.json',out/name)
    invalid=copy.deepcopy(load_json(ROOT/'examples/width-calibration-demo/task.json'))
    invalid['measurement_definition']['quantity']='concentration_sigma_um'
    try:
        validate_task(invalid)
        raise RuntimeError('Expected observable mismatch to be blocked')
    except InputError as exc:
        mismatch={'status':'blocked','reason':str(exc),'calculation_performed':False}
    write_json(out/'observable_mismatch.json',mismatch)
    state={'version':'0.3.0','mode':'offline_replay_and_synthetic_calibration',
           'status':'calibration_and_candidate_planning_implemented_real_validation_pending',
           'live_literature_search_in_this_run':False,'live_github_search_in_this_run':False,
           'external_llm_api_called':False,'dedicated_simulation_software_called':False,
           'hardware_commands_sent':False,'physical_validation_performed':False,
           'inherited_evidence_sha256':file_hash(packet),
           'case_statuses':{k:v['status'] for k,v in cases.items()},
           'observable_mismatch_blocked':True,
           'no_numeric_prediction_when_data_insufficient':all(r['predicted_response_um'] is None for r in cases['insufficient_data']['experiment_plan']['trials']),
           'skill_selection':'recorded host-assisted GitHub review; local deterministic adapter routing during replay',
           'next_action':'Use real traceable measurements or connect an authorized LLM host; do not claim physical improvement from these fixtures.'}
    write_json(out/'run_state.json',state)
    for filename in ['calibration-002.json','planning-001.json','stage3-upstream.json']:
        write_json(out/filename,load_json(ROOT/'registry/reviews'/filename))
    width=cases['geometric_width'];sigma=cases['concentration_sigma']
    lines=['# v0.3 综合演示','','**全部数值为合成测试数据，不是老师、论文或用户的真实打印实验。**','',
           '本轮读取上阶段冻结文献包，不重新联网检索。执行的是本项目适配后的子工具，不是原版上游脚本。','',
           '## 实际完成','',
           '- 浓度标准差：独立的扩散方差标定与留出检查。',
           '- 几何轨迹宽度：独立的二因素经验回归，明确不推断扩散系数。',
           '- 验证通过后，在可达参数网格及训练域内筛选目标候选；否则输出标定计划。',
           '- 保留基准重复、随机运行次序与空白新测量模板。','',
           f"经验宽度合成示例：CV RMSE = {width['calibration']['cv']['group_weighted_rmse_um']:.4f} μm；留出 RMSE = {width['calibration']['holdout']['group_weighted_rmse_um']:.4f} μm。",
           f"浓度合成示例：估计 σ₀ = {sigma['calibration']['model']['sigma0_um']:.4f} μm；估计 D = {sigma['calibration']['model']['diffusivity_um2_s']:.4f} μm²/s。",
           '这些数值只说明程序在指定测试夹具上的表现；不代表实际制造精度。','',
           '## 检查失败时','',
           '数据不足：仍可给出有界标定/覆盖试验，但所有结果预测为 null。',
           '观测量不一致：停止，不把几何轨迹宽度代入浓度扩散模型。',
           '未实现点位预测区间：不把CV误差写成±置信区间。','',
           '当前没有设备操作、新实测回传的自动评价器或完整自主GitHub技能路由。']
    (out/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Standalone, no-script HTML: opens offline, no services or credentials.
    sections=[]
    for name,data in cases.items():
        cs=data['calibration'];trialrows=[]
        for row in data['experiment_plan']['trials']:
            p=row['predicted_response_um']
            trialrows.append('<tr><td>'+str(row['run_order'])+'</td><td>'+html.escape(row['purpose'])+'</td><td>'+html.escape(json.dumps(row['parameters'],ensure_ascii=False))+'</td><td>'+('不提供' if p is None else f'{p:.3f}')+'</td></tr>')
        sections.append('<section><h2>'+html.escape(name)+'</h2><p>'+html.escape(cs['status'])+'</p><table><tr><th>次序</th><th>目的</th><th>参数</th><th>预测值 / μm</th></tr>'+''.join(trialrows)+'</table><p>候选方案尚未执行；真实可行性未知。</p></section>')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Hybrid-AM v0.3</title><style>body{font:17px/1.75 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px}h1{font-size:32px}section{margin:28px 0;padding:16px;border:1px solid #bbb}table{border-collapse:collapse;width:100%;font-size:15px}th,td{text-align:left;padding:10px;border-bottom:1px solid #ddd}.note{border:2px solid #555;padding:16px}code{font-size:14px}</style><h1>Hybrid-AM Research Skill · v0.3</h1><p class="note"><strong>合成数据演示 / Synthetic demonstration</strong><br>真实执行了标定、验证和候选筛选代码；没有真实打印、设备控制或制造性能提升结论。下载后离线运行，不重新联网、不调用LLM API。</p>'''+''.join(sections)+'''<section><h2>本版能力边界</h2><p>文献证据包继承自v0.2。两种观测量分开建模。留出组不用于拟合；训练域外不提供数值预测。小样本或检验失败时转为标定计划。没有点位置信区间，也不是贝叶斯优化。</p><p>详细输入、参数、分组、误差和工具记录见各子文件夹result.json、events.jsonl与summary.md。</p></section></html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    return state


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    try:r=main_run(a.out)
    except (OSError,ValueError,TypeError) as e:ap.error(str(e))
    print(json.dumps(r,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
