"""Run a deterministic synthetic acceptance campaign. This is NOT a live LLM.

Same allowlisted tools as a host agent; external fixtures are attached separately
by the test harness. Optional API/host execution is documented in HOST_START.md.
"""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
from agent_runtime import ROOT, init_session, dispatch, attach_feedback, load, save, verify_audit, verify_integrity
from round_tools import attach_confirmation
from synthetic_campaign import feedback_fixture, confirmation_fixture


def run(out: Path, scenario: str='steady', rounds: int=3) -> dict:
    if out.exists(): raise ValueError('Output directory exists; use a new campaign directory')
    out.mkdir(parents=True)
    session=out/'round-01'
    init_session(ROOT/'examples/width-calibration-demo/task.json',session,
        protocol_path=ROOT/'examples/agent-feedback-demo/comparison_protocol.json',
        evidence_path=ROOT/'evidence/delay-evidence-001/evidence_packet.json', origin='deterministic_demo')
    summary=[]
    for r in range(1,rounds+1):
        count=0
        def call(name,args=None):
            nonlocal count
            count+=1
            result=dispatch(session,name,args or {},f'r{r}-{count:02d}',origin='deterministic_demo')
            if not result['ok']: raise RuntimeError(json.dumps(result,ensure_ascii=False))
            return result['result']
        def select(stage,sid):
            call('find_skills',{'stage':stage})
            call('activate_skill',{'stage':stage,'skill_id':sid,'rationale':'Deterministic acceptance test selection; not an LLM invocation.'})
        call('session_status')
        if r==1:
            call('inspect_task');select('evidence','hybrid-am-evidence');call('review_evidence')
            select('calibration','measured-response-calibration');call('calibrate_response')
        cal=load(session/'artifacts/calibration.json')
        select('planning','bounded-experiment-planning' if cal['model_usable_for_proposals'] else 'calibration-only-planning')
        call('plan_experiments');call('finish_report')
        item={'round':r,'session':str(session.relative_to(out)), 'planned':True,
              'predictive_plan':cal['model_usable_for_proposals'], 'data_kind':'synthetic_demo'}
        if r==rounds:
            item['status']='awaiting_external_experiment';summary.append(item);break
        manifest=feedback_fixture(session,session/'test-fixtures/feedback',scenario=scenario)
        attach_feedback(session,manifest)
        select('feedback','descriptive-feedback');call('import_results');comparison=call('compare_results')
        select('update','safe-model-update');call('prepare_update');result=call('refit_update')
        if result['candidate']['calibration']['numerical_fit_performed']:
            cm=confirmation_fixture(session,session/'test-fixtures/confirmation',scenario=scenario)
            attach_confirmation(session,cm)
            assessment=call('evaluate_update')
        else: assessment={'status':'refit_failed','promotion_allowed':False}
        mode='validated_update' if assessment['promotion_allowed'] else 'calibration_only'
        child=call('start_next_round',{'mode':mode});call('finish_report')
        item.update(update_status=assessment['status'], continuation_mode=mode,
                    confirmation=assessment.get('new_model_confirmation'),
                    prior_same_confirmation=assessment.get('previous_model_same_confirmation'),
                    comparison_verdicts=[c['verdict'] for c in comparison['contrasts']],
                    tool_calls=count, audit=verify_audit(session))
        verify_integrity(session,load(session/'state.json'))
        summary.append(item);session=session/child['next_session']
    verify_integrity(session,load(session/'state.json'));summary[-1]['audit']=verify_audit(session)
    result={'version':'1.0.0','origin':'deterministic_demo','scenario':scenario, 'data_kind':'synthetic_demo',
            'rounds':summary,'hardware_commands_sent':False,'live_llm_calls':0,
            'fresh_literature_search_in_demo':False,'dedicated_simulation_software_called':False,
            'physical_performance_improvement_established':False}
    save(out/'campaign.json',result)
    trs=[]
    for rr in summary:
        url=rr['session']+'/index.html'
        e=rr.get('confirmation') or {}
        rmse=e.get('group_weighted_rmse_um')
        trs.append(f"<tr><td>{rr['round']}</td><td>{rr['predictive_plan']}</td><td>{html.escape(rr.get('update_status','等待下一次外部数据'))}</td><td>{'—' if rmse is None else format(rmse,'.5g')}</td><td><a href='{html.escape(url)}'>逐步记录</a></td></tr>")
    page="""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Axiom Research · VPP–DIW v1.0</title><style>body{font:16px/1.7 system-ui,sans-serif;max-width:1060px;margin:36px auto;padding:0 24px;background:#fafafa;color:#17333e}h1{font-size:32px}table{border-collapse:collapse;width:100%;background:white}th,td{padding:12px;text-align:left;border-bottom:1px solid #d5dce0}aside{padding:16px 20px;background:#fff1d5;border-left:4px solid #c19020}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px}a{color:#145475}</style><h1>Axiom Research · VPP–DIW v1.0</h1><p>文献证据 → 轻量建模 → 候选实验 → 结果回传 → 冻结重拟合 → 独立确认 → 下一轮</p><aside><strong>全部数值为合成测试。</strong>这是固定顺序的软件验收演示，不是在线LLM、真实打印或制造性能提升。实验和确认数据由独立测试环境提供，未使用模型预测值充当测量。</aside><h2>多轮执行结果</h2><table><tr><th>轮次</th><th>数值预测已开放</th><th>更新检查</th><th>确认RMSE（μm）</th><th>明细</th></tr>"""+''.join(trs)+"</table><h2>如何看这些结果</h2><p>新数据先评价旧模型，再用于训练候选模型。确认数据在候选冻结后附加；旧holdout和已用确认不会在下一轮再次当作新验证。模型未通过则转标定计划，预测栏为空。</p><h2>可复现记录</h2><pre>"+html.escape(json.dumps(result,ensure_ascii=False,indent=2))+"</pre></html>"
    (out/'index.html').write_text(page,encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--scenario',choices=['steady','shifted','severe'],default='steady');p.add_argument('--rounds',type=int,choices=[2,3],default=3)
    a=p.parse_args();print(json.dumps(run(a.out,a.scenario,a.rounds),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
