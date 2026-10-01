"""Deterministic offline regression demo. Not an LLM-driven or online GitHub run."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from agent_runtime import ROOT,init_session,dispatch,attach_feedback,load,verify_audit
from synthetic_followup import make_fixture


def run_demo(out: Path, *, sparse: bool=False) -> dict:
    task=ROOT/'examples'/('insufficient-data-demo' if sparse else 'width-calibration-demo')/'task.json'
    init_session(task,out,protocol_path=ROOT/'examples/agent-feedback-demo/comparison_protocol.json',
                 evidence_path=ROOT/'evidence/delay-evidence-001/evidence_packet.json',origin='deterministic_demo')
    counter=0
    def call(name,args=None):
        nonlocal counter;counter+=1
        result=dispatch(out,name,args or {},f'demo-{counter:02d}',origin='deterministic_demo')
        if not result['ok']:raise RuntimeError(result)
        return result['result']
    def activate(stage,sid):
        call('find_skills',{'stage':stage})
        call('activate_skill',{'stage':stage,'skill_id':sid,'rationale':'Deterministic regression scenario; not an LLM selection.'})
    call('inspect_task');activate('evidence','hybrid-am-evidence');call('review_evidence')
    activate('calibration','measured-response-calibration');cal=call('calibrate_response')['calibration']
    activate('planning','bounded-experiment-planning' if cal['model_usable_for_proposals'] else 'calibration-only-planning')
    call('plan_experiments')
    if not sparse:
        manifest=make_fixture(out,out/'synthetic_fixture',scenario='shifted')
        attach_feedback(out,manifest)
        activate('feedback','descriptive-feedback');call('import_results');call('compare_results')
        activate('update','safe-model-update');call('prepare_update')
    call('finish_report')
    return {'status':load(out/'state.json')['phase'],'audit':verify_audit(out),'origin':'deterministic_demo',
            'data_kind':'synthetic_demo','out':str(out)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--sparse',action='store_true')
    a=p.parse_args();print(json.dumps(run_demo(a.out,sparse=a.sparse),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
