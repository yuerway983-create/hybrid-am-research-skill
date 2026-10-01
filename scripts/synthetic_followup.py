"""Explicit synthetic follow-up fixture generator. NOT a tool available to the LLM.
Reads planned parameter coordinates, NEVER the predicted response or fitted coefficients.
The shifted-width scenario intentionally violates the old response surface to test
that a worse candidate is reported as worse, not relabelled as optimisation success.
"""
from __future__ import annotations
import argparse,math
from pathlib import Path
import numpy as np
from agent_runtime import load,save
from feedback_tools import digest
from calibration_planning import need,write_csv


def make_fixture(session: Path, out: Path, *, scenario: str='shifted', setting_deviation: bool=True) -> Path:
    need(not out.exists(),'Fixture output must be new')
    task=load(session/'input/task.json');plan=load(session/'artifacts/plan.json')
    protocol=load(session/'input/comparison_protocol.json')
    need(task['data_kind']=='synthetic_demo','Never generate a synthetic follow-up for a measured task')
    need(scenario in {'compatible','shifted'},'Unknown synthetic scenario')
    out.mkdir(parents=True);rng=np.random.default_rng(4102026)
    ex,meas=[],[]
    for b in range(3):
        drift=rng.normal(0,.3)
        for trial in plan['trials']:
            for rep in range(2):
                tid=trial['trial_id'];pars=dict(trial['parameters'])
                deviation=setting_deviation and trial['purpose']=='coverage_or_calibration' and b==0 and rep==0
                if deviation and 'speed_mm_s' in pars:
                    pars['speed_mm_s'] += .2 if pars['speed_mm_s']<14.8 else -.2
                eid=f'EX-{b}-{tid}-{rep}';sid=f'NEW-{b}-{tid}-{rep}';bid=f'FOLLOWUP-{b}'
                sec=10+trial['run_order']*3+rep
                execution={'execution_id':eid,'trial_id':tid,'sample_id':sid,'batch_id':bid,
                  **{k:task[k] for k in ('material_pair','context_id','data_kind')},
                  'source_ref':'synthetic_followup.py independent test function, not model output',
                  'approval_status':'demo_only','approval_source_ref':'synthetic test authorization, not hardware approval',
                  'execution_status':'synthetic_execution','executed_at':f'2026-10-01T12:00:{sec:02d}+00:00',
                  **{'actual_'+k:v for k,v in pars.items()}}
                ex.append(execution)
                if task['observable']=='geometric_track_width_um':
                    v,t=pars['speed_mm_s'],pars['delay_s']
                    mean=470-3*(v-10)+14*(t-3)+.5*(v-10)**2+1.5*(t-3)**2+.4*(v-10)*(t-3)
                    if scenario=='shifted':mean += 2*(v-5)  # deliberate distribution shift, not a material claim
                else:
                    mean=math.sqrt(2500+80*pars['elapsed_time_s'])
                    if scenario=='shifted':mean += .02*pars['elapsed_time_s']
                specimen=mean+drift+rng.normal(0,.2)
                for k in range(2):
                    meas.append({'record_id':f'NEWREC-{b}-{tid}-{rep}-{k}','execution_id':eid,
                        'sample_id':sid,'batch_id':bid,**{key:task[key] for key in ('material_pair','context_id','data_kind')},
                        'source_ref':'synthetic follow-up fixture; not a physical measurement',
                        'observable':task['observable'],'response_unit':'um','response_um':round(specimen+rng.normal(0,.06),8),
                        'measured_at':f'2026-10-01T12:01:{sec+k:02d}+00:00'})
    write_csv(out/'executions.csv',ex);write_csv(out/'measurements.csv',meas)
    manifest={'schema_version':'0.4','feedback_id':'synthetic-followup-'+scenario,
        **{k:task[k] for k in ('task_id','material_pair','context_id','data_kind','mode','observable','fixed_conditions','measurement_definition')},
        'plan_sha256':digest(plan),'comparison_protocol_sha256':digest(protocol),
        'source_ref':'synthetic_followup.py; scenario '+scenario,'acquisition_status':'synthetic_fixture',
        'dataset_file':'measurements.csv','execution_file':'executions.csv'}
    save(out/'manifest.json',manifest)
    save(out/'fixture_info.json',{'data_kind':'synthetic_demo','seed':4102026,'scenario':scenario,
         'model_coefficients_read':False,'prediction_values_used_as_measurements':False,
         'purpose':'Test frozen-model error, concurrent comparison and settings-deviation handling, not physical improvement'})
    return out/'manifest.json'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--scenario',choices=['compatible','shifted'],default='shifted')
    a=p.parse_args();print(make_fixture(a.session,a.out,scenario=a.scenario))
if __name__=='__main__':main()
