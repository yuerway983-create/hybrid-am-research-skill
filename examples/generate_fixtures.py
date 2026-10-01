from pathlib import Path
import json, csv, math, numpy as np
import argparse
ap=argparse.ArgumentParser(description='Generate synthetic fixtures only; not physical data')
ap.add_argument('--out',required=True,type=Path)
args=ap.parse_args()
R=args.out
if R.exists():ap.error('Output exists; choose a new directory')
R.mkdir(parents=True)
def js(p,obj):
 p=R/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def tx(p,s):
 p=R/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
def csvout(p,rows,fields=None):
 p=R/p;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='',encoding='utf-8') as h:
  w=csv.DictWriter(h,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

common={'schema_version':'0.3','task_id':'','mode':'offline_demo','data_kind':'synthetic_demo','process':'hybrid-vpp-diw',
        'material_pair':'SYNTHETIC-A / SYNTHETIC-B','context_id':'synthetic-context-003',
        'fixed_conditions':{'material_and_exposure':'Synthetic software fixture only, not a physical resin or approved exposure'},
        'dataset_file':'measurements.csv','group_column':'batch_id',
        'measurement_definition':{'quantity':'','method':'synthetic scalar generator; NOT image metrology','scale_source_ref':'synthetic units','unit':'um'},
        'factors':[],'target_um':500.,'next_trials':3,'seed':32026,'bounds_review_status':'needs_review',
        'acceptance':{'max_cv_rmse_um':8.,'max_holdout_rmse_um':8.,'require_beats_constant':True},
        'allow':{'hardware_commands':False,'dedicated_simulation_software':False},
        'notes':'All ranges, targets, measurements and noise are artificial test fixtures. No real material validation or printing.'}
# Empirical two-factor route. Independent batches plus within-sample technical repeats.
a=json.loads(json.dumps(common));a.update(task_id='synthetic-geometric-width-003',observable='geometric_track_width_um',
 empirical_model={'degree':2,'ridge_alpha':0.01},baseline_parameters={'speed_mm_s':5.,'delay_s':3.})
a['measurement_definition']['quantity']=a['observable']
a['factors']=[{'name':'speed_mm_s','unit':'mm/s','bounds':[5.,15.],'step':.5,'source_ref':'synthetic fixture'},
              {'name':'delay_s','unit':'s','bounds':[1.,5.],'step':.25,'source_ref':'synthetic fixture'}]
js(Path('examples/width-calibration-demo/task.json'),a)
rng=np.random.default_rng(32026);rows=[]
for b in range(7):
 fit=b<5
 combos=[(v,t) for v in (5.,10.,15.) for t in (1.,3.,5.)] if fit else [(7.5,2.),(7.5,4.),(12.5,2.),(12.5,4.)]
 drift=rng.normal(0,1.)
 for j,(v,t) in enumerate(combos):
  # Arbitrary response surface constructed solely to test regression and selection.
  z=470.-3*(v-10)+14*(t-3)+.5*(v-10)**2+1.5*(t-3)**2+.4*(v-10)*(t-3)
  specimen_noise=rng.normal(0,.7)
  for k in range(2):
   rows.append({'record_id':f'W-{b}-{j}-{k}','sample_id':f'W-{b}-{j}','batch_id':f'WB-{b}','material_pair':a['material_pair'],
                'context_id':a['context_id'],'data_kind':'synthetic_demo','source_ref':'synthetic fixture; equation in generate_fixtures.py',
                'partition':'fit' if fit else 'holdout','speed_mm_s':v,'delay_s':t,'response_um':round(z+drift+specimen_noise+rng.normal(0,.3),8)})
csvout(Path('examples/width-calibration-demo/measurements.csv'),rows)
js(Path('examples/width-calibration-demo/fixture_truth.json'),{'data_kind':'synthetic_demo','generator':'470-3*(v-10)+14*(t-3)+0.5*(v-10)^2+1.5*(t-3)^2+0.4*(v-10)*(t-3)+batch/sample/measurement noise',
 'purpose':'test fixture, NEVER read by fitter or candidate selection','seed':32026})
# Same valid task, fewer independent batches -> a real non-predictive branch.
c=json.loads(json.dumps(a));c.update(task_id='synthetic-insufficient-data-003')
js(Path('examples/insufficient-data-demo/task.json'),c)
csvout(Path('examples/insufficient-data-demo/measurements.csv'),[r for r in rows if r['batch_id']=='WB-0'][:6])
# Concentration-sigma route: no geometric data interpretation.
d=json.loads(json.dumps(common));d.update(task_id='synthetic-diffusion-calibration-003',observable='concentration_sigma_um',target_um=55.,baseline_parameters={'elapsed_time_s':0.},time_reference='elapsed_since_reference_profile',
 assumptions={k:True for k in ['homogeneous_1d','unbounded_domain','constant_diffusivity','pre_gel_only','advection_ignored']})
d['measurement_definition']['quantity']=d['observable']
d['factors']=[{'name':'elapsed_time_s','unit':'s','bounds':[0.,8.],'step':.5,'source_ref':'synthetic fixture'}]
d['acceptance']={'max_cv_rmse_um':.8,'max_holdout_rmse_um':.8,'require_beats_constant':True}
js(Path('examples/sigma-calibration-demo/task.json'),d)
rng=np.random.default_rng(72026);rows=[]
for b in range(7):
 fit=b<5; times=[0.,2.,4.,6.,8.] if fit else [1.,3.,5.,7.]
 drift=rng.normal(0,.06)
 for j,t in enumerate(times):
  s=math.sqrt(2500.+80*t)
  for k in range(2):
   rows.append({'record_id':f'S-{b}-{j}-{k}','sample_id':f'S-{b}','batch_id':f'SB-{b}','material_pair':d['material_pair'],
      'context_id':d['context_id'],'data_kind':'synthetic_demo','source_ref':'synthetic Gaussian moment fixture',
      'partition':'fit' if fit else 'holdout','elapsed_time_s':t,'response_um':round(s+drift+rng.normal(0,.035),8)})
csvout(Path('examples/sigma-calibration-demo/measurements.csv'),rows)
js(Path('examples/sigma-calibration-demo/fixture_truth.json'),{'sigma0_um':50.,'diffusivity_um2_s':40.,'data_kind':'synthetic_demo','purpose':'Only for checking synthetic recovery; never fit from this file','seed':72026})

