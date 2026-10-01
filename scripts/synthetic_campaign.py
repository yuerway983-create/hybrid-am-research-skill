"""Explicit synthetic external environment for SOFTWARE acceptance tests only.

This module is NOT in the agent's tool schema or model fitting imports. It reads
parameter coordinates, not fitted coefficients or predicted values. Real mode is
rejected. Statistical test data cannot establish material/printing performance.
"""
from __future__ import annotations
import argparse
import copy
import math
from pathlib import Path
import numpy as np
from agent_runtime import load, save
from calibration_planning import need, write_csv
from feedback_tools import digest
from synthetic_followup import make_fixture as legacy_fixture


def response(parameters: dict, observable: str, scenario: str) -> float:
    need(scenario in {'steady','shifted','severe'}, 'Unknown synthetic environment')
    if observable == 'geometric_track_width_um':
        v, t = parameters['speed_mm_s'], parameters['delay_s']
        value = 470-3*(v-10)+14*(t-3)+.5*(v-10)**2+1.5*(t-3)**2+.4*(v-10)*(t-3)
        if scenario == 'shifted': value += 2*(v-5)
    else:
        value = math.sqrt(2500+80*parameters['elapsed_time_s'])
        if scenario == 'shifted': value += .02*parameters['elapsed_time_s']
    if scenario == 'severe': value += 120
    return value


def feedback_fixture(session: Path, out: Path, scenario: str = 'steady', seed: int = 7026) -> Path:
    task=load(session/'input/task.json'); s=load(session/'state.json')
    need(task['data_kind']=='synthetic_demo', 'Never synthesize reported measurements')
    manpath=legacy_fixture(session,out,scenario='compatible')
    import csv
    with (out/'executions.csv').open() as f: ex=list(csv.DictReader(f))
    with (out/'measurements.csv').open() as f: records=list(csv.DictReader(f))
    prefix=f"R{s.get('round_index',1):02d}-"
    fields=[f['name'] for f in task['factors']]
    rng=np.random.default_rng(seed+s.get('round_index',1)*71)
    y={}
    for r in ex:
        for key in ('execution_id','sample_id','batch_id'):r[key]=prefix+r[key]
        pars={k:float(r['actual_'+k]) for k in fields}
        y[r['sample_id']]=response(pars,task['observable'],scenario)+rng.normal(0,.3)
        r['source_ref']='synthetic_campaign.py external fixture; not an experiment'
    for r in records:
        for key in ('record_id','execution_id','sample_id','batch_id'):r[key]=prefix+r[key]
        r['response_um']=float(y[r['sample_id']]+rng.normal(0,.05))
        r['source_ref']='synthetic campaign, independent artificial response function'
    write_csv(out/'executions.csv',ex);write_csv(out/'measurements.csv',records)
    man=load(manpath);man['feedback_id']=prefix+'feedback-'+scenario
    man['source_ref']='synthetic_campaign.py; scenario='+scenario
    save(manpath,man)
    save(out/'fixture_info.json',{'data_kind':'synthetic_demo','scenario':scenario,'seed':seed,
         'round_index':s.get('round_index',1), 'fitted_coefficients_used':False,
         'predictions_used_as_measurements':False, 'physical_acquisition':False})
    return manpath


def confirmation_fixture(session: Path, out: Path, scenario: str='steady', seed: int=99026) -> Path:
    need(not out.exists(),'New confirmation output directory required')
    task=load(session/'update/task.json');s=load(session/'state.json')
    need(task['data_kind']=='synthetic_demo','Never synthesize real confirmation')
    candidate=load(session/'artifacts/update_candidate.json')
    plan=load(session/'artifacts/confirmation_plan.json')
    need(plan['conditions'],'No prospectively specified confirmation points')
    prefix=f"R{s.get('round_index',1):02d}-CONF-"
    rng=np.random.default_rng(seed+s.get('round_index',1)*97)
    rows=[]
    for b in range(plan['minimum_independent_groups']):
        drift=rng.normal(0,.2)
        for i,c in enumerate(plan['conditions']):
            val=response(c['parameters'],task['observable'],scenario)+drift+rng.normal(0,.08)
            for rep in range(2):
                rows.append({'record_id':f'{prefix}{b}-{i}-{rep}', 'sample_id':f'{prefix}S-{b}-{i}',
                    'batch_id':f'{prefix}B-{b}', **{k:task[k] for k in ('material_pair','context_id','data_kind')},
                    'source_ref':'synthetic_campaign.py held-out artificial environment; no physical experiment',
                    'partition':'holdout', **c['parameters'], 'response_um':val+rng.normal(0,.03)})
    out.mkdir(parents=True);write_csv(out/'measurements.csv',rows)
    manifest={'schema_version':'1.0','candidate_sha256':digest(candidate),'confirmation_plan_sha256':digest(plan),
        'role':'fresh_confirmation','reserved_after_candidate_freeze':True,
        **{k:copy.deepcopy(task[k]) for k in ('material_pair','context_id','data_kind','mode','observable','fixed_conditions','measurement_definition')},
        'acquisition_status':'synthetic_fixture','source_ref':'Independent synthetic test environment, '+scenario,
        'dataset_file':'measurements.csv'}
    save(out/'manifest.json',manifest)
    save(out/'fixture_info.json',{'data_kind':'synthetic_demo','scenario':scenario,'seed':seed,
          'predictions_used_as_measurements':False, 'physical_acquisition':False,
          'note':'Candidate digest binds protocol only; its predicted values/coefficient vector are not used by response().'})
    return out/'manifest.json'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind',choices=['feedback','confirmation']);p.add_argument('--session',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--scenario',choices=['steady','shifted','severe'],default='steady')
    a=p.parse_args();fn=feedback_fixture if a.kind=='feedback' else confirmation_fixture
    print(fn(a.session,a.out,scenario=a.scenario))
if __name__=='__main__':main()
