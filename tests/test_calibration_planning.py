"""v0.3 tests verify code contracts and synthetic fixtures, not a physical process."""
from __future__ import annotations
import copy
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from calibration_planning import (InputError, validate_task, load_measurements, arrays, group_weights,
    error_metrics, fit_model, predict, in_training_domain, calibrate, candidate_grid, propose, run, safe_child)
from _core import load_json


def bundle(name='width-calibration-demo'):
    path=ROOT/'examples'/name/'task.json'
    task=load_json(path)
    rows,check=load_measurements(task,path.parent/task['dataset_file'])
    return task,rows,check


class TaskTests(unittest.TestCase):
    def setUp(self): self.t,self.rows,_=bundle()
    def test_valid_width(self): validate_task(self.t)
    def test_valid_sigma(self): validate_task(bundle('sigma-calibration-demo')[0])
    def test_unsupported_response(self):
        self.t['observable']='interface_strength'
        with self.assertRaises(InputError):validate_task(self.t)
    def test_no_sigma_width_alias(self):
        self.t['measurement_definition']['quantity']='concentration_sigma_um'
        with self.assertRaises(InputError):validate_task(self.t)
    def test_units_required(self):
        self.t['measurement_definition']['unit']='mm'
        with self.assertRaises(InputError):validate_task(self.t)
    def test_scale_source_required(self):
        self.t['measurement_definition']['scale_source_ref']=''
        with self.assertRaises(InputError):validate_task(self.t)
    def test_hardware_denied(self):
        self.t['allow']['hardware_commands']=True
        with self.assertRaises(InputError):validate_task(self.t)
    def test_solver_denied(self):
        self.t['allow']['dedicated_simulation_software']=True
        with self.assertRaises(InputError):validate_task(self.t)
    def test_no_synthetic_relabelling(self):
        self.t['mode']='research'
        with self.assertRaises(InputError):validate_task(self.t)
    def test_nan_target(self):
        self.t['target_um']=float('nan')
        with self.assertRaises(InputError):validate_task(self.t)
    def test_boolean_target(self):
        self.t['target_um']=True
        with self.assertRaises(InputError):validate_task(self.t)
    def test_no_unstated_threshold(self):
        self.t['acceptance'].pop('max_cv_rmse_um')
        with self.assertRaises(InputError):validate_task(self.t)
    def test_factor_order(self):
        self.t['factors'].reverse()
        with self.assertRaises(InputError):validate_task(self.t)
    def test_invalid_step(self):
        self.t['factors'][0]['step']=0
        with self.assertRaises(InputError):validate_task(self.t)
    def test_baseline_off_grid(self):
        self.t['baseline_parameters']['speed_mm_s']=5.11
        with self.assertRaises(InputError):validate_task(self.t)
    def test_model_config_prespecified(self):
        self.t['empirical_model']['degree']=3
        with self.assertRaises(InputError):validate_task(self.t)
    def test_real_templates_intentionally_invalid(self):
        for p in ROOT.glob('templates/task_*_v0.3.json'):
            with self.subTest(path=p):
                with self.assertRaises(InputError):validate_task(load_json(p))
    def test_path_traversal(self):
        with self.assertRaises(InputError):safe_child(ROOT,'../secret.csv')
    def test_absolute_path(self):
        with self.assertRaises(InputError):safe_child(ROOT,'/tmp/file.csv')


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.t,self.rows,self.check=bundle()
        p=ROOT/'examples/width-calibration-demo/measurements.csv'
        with p.open(newline='') as h:
            reader=csv.DictReader(h);self.headers=reader.fieldnames;self.raw=list(reader)
    def load_modified(self, rows,headers=None):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.csv'
            with p.open('w',newline='') as h:
                w=csv.DictWriter(h,fieldnames=headers or self.headers);w.writeheader();w.writerows(rows)
            return load_measurements(self.t,p)
    def test_technical_repeats_aggregated(self):
        self.assertEqual(self.check['n_raw_rows'],106)
        self.assertEqual(self.check['n_aggregated_rows'],53)
    def test_batch_holdout_disjoint(self):
        self.assertFalse(set(self.check['partitions']['fit']['groups']) & set(self.check['partitions']['holdout']['groups']))
    def test_duplicate_records_blocked(self):
        with self.assertRaises(InputError):self.load_modified(self.raw+[self.raw[0]])
    def test_missing_measurement(self):
        self.raw[0]['response_um']=''
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_nonfinite_measurement(self):
        self.raw[0]['response_um']='nan'
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_infinite_factor(self):
        self.raw[0]['speed_mm_s']='inf'
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_material_mismatch(self):
        self.raw[0]['material_pair']='other'
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_context_mismatch(self):
        self.raw[0]['context_id']='other'
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_mixed_provenance(self):
        self.raw[0]['data_kind']='measured'
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_sample_leakage(self):
        self.raw[1]['partition']='holdout'
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_batch_leakage(self):
        self.raw[-1]['batch_id']='WB-0'; self.raw[-2]['batch_id']='WB-0'
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_empty_file_is_calibration_only(self):
        rows,_=self.load_modified([])
        c,m=calibrate(self.t,rows);p=propose(self.t,rows,c,m)
        self.assertFalse(c['numerical_fit_performed'])
        self.assertTrue(all(r['predicted_response_um'] is None for r in p['trials']))
    def test_empty_source(self):
        self.raw[0]['source_ref']=''
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_off_bounds_measurements(self):
        self.raw[0]['delay_s']='500'
        with self.assertRaises(InputError):self.load_modified(self.raw)
    def test_positive_response(self):
        self.raw[0]['response_um']='-2'
        with self.assertRaises(InputError):self.load_modified(self.raw)


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task,cls.rows,_=bundle();cls.c,cls.m=calibrate(cls.task,cls.rows)
        cls.st,cls.sr,_=bundle('sigma-calibration-demo');cls.sc,cls.sm=calibrate(cls.st,cls.sr)
    def test_width_gates_pass(self):self.assertTrue(self.c['model_usable_for_proposals'])
    def test_sigma_gates_pass(self):self.assertTrue(self.sc['model_usable_for_proposals'])
    def test_sigma_recovers_fixture(self):
        self.assertAlmostEqual(self.sc['model']['sigma0_um'],50,delta=.3)
        self.assertAlmostEqual(self.sc['model']['diffusivity_um2_s'],40,delta=2)
    def test_empirical_not_diffusion(self):self.assertFalse(self.c['model']['diffusivity_inferred'])
    def test_fold_groups_disjoint(self):
        for f in self.c['folds']:self.assertFalse(set(f['fit_groups']) & set(f['validation_groups']))
    def test_fold_indices_partition(self):
        indices=[i for f in self.c['folds'] for i in f['validation_row_indices']]
        self.assertEqual(sorted(indices),list(range(45)))
    def test_holdout_not_used_in_fit(self):
        other=copy.deepcopy(self.rows)
        for r in other:
            if r['partition']=='holdout':r['response_um']+=1000
        c,m=calibrate(self.task,other)
        np.testing.assert_array_equal(self.c['model']['coef_standardized'],c['model']['coef_standardized'])
        self.assertEqual(self.c['cv'],c['cv'])
        self.assertFalse(c['model_usable_for_proposals'])
    def test_missing_holdout_cannot_pass(self):
        c,_=calibrate(self.task,[r for r in self.rows if r['partition']=='fit'])
        self.assertFalse(c['model_usable_for_proposals'])
    def test_constant_baseline_reported(self):self.assertIn('constant_baseline_cv',self.c)
    def test_no_fake_intervals(self):self.assertEqual(self.c['uncertainty']['type'],'not_quantified')
    def test_low_data_fallback(self):
        t,r,_=bundle('insufficient-data-demo');c,m=calibrate(t,r)
        self.assertFalse(c['model_usable_for_proposals']);self.assertIsNone(m)
    def test_rank_deficiency(self):
        bad=copy.deepcopy(self.rows)
        for r in bad:r['delay_s']=r['speed_mm_s']/3
        c,_=calibrate(self.task,bad)
        self.assertFalse(c['model_usable_for_proposals'])
    def test_negative_diffusion_slope_rejected(self):
        bad=copy.deepcopy(self.sr)
        for r in bad:r['response_um']=60-r['elapsed_time_s']
        c,m=calibrate(self.st,bad)
        self.assertFalse(c['model_usable_for_proposals']);self.assertIn('decreases',c['reasons'][0])
    def test_group_balanced_metrics(self):
        y=np.zeros(4);p=np.array([2,2,2,4]);g=np.array(['A','A','A','B'])
        self.assertAlmostEqual(error_metrics(y,p,g)['group_weighted_mae_um'],3)
    def test_group_weights_equal_total(self):
        g=np.array(['a','a','a','b']);w=group_weights(g)
        self.assertAlmostEqual(w[g=='a'].sum(),w[g=='b'].sum())
    def test_too_strict_acceptance_routes_to_calibration(self):
        t=copy.deepcopy(self.task);t['acceptance']['max_cv_rmse_um']=1e-12
        c,m=calibrate(t,self.rows);p=propose(t,self.rows,c,m)
        self.assertFalse(p['predicted_target_selection_performed'])
        self.assertTrue(all(r['predicted_response_um'] is None for r in p['trials']))
    def test_one_holdout_group_insufficient(self):
        rows=[r for r in self.rows if r['partition']=='fit' or r['batch_id']=='WB-5']
        c,_=calibrate(self.task,rows);self.assertFalse(c['model_usable_for_proposals'])


class ProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.t,cls.r,_=bundle();cls.c,cls.m=calibrate(cls.t,cls.r);cls.p=propose(cls.t,cls.r,cls.c,cls.m)
    def test_budget(self):self.assertEqual(len(self.p['trials']),3)
    def test_baseline_reserved(self):self.assertEqual(sum(r['purpose']=='baseline_replication' for r in self.p['trials']),1)
    def test_each_trial_needs_approval(self):self.assertTrue(all(r['human_approval_required'] for r in self.p['trials']))
    def test_no_physical_feasibility_claim(self):self.assertTrue(all(r['physical_feasibility']=='not_verified' for r in self.p['trials']))
    def test_deterministic(self):self.assertEqual(self.p,propose(self.t,self.r,self.c,self.m))
    def test_bounds(self):
        for r in self.p['trials']:
            for f in self.t['factors']:self.assertTrue(f['bounds'][0]<=r['parameters'][f['name']]<=f['bounds'][1])
    def test_attainable_grid(self):
        for r in self.p['trials']:
            for f in self.t['factors']:
                q=(r['parameters'][f['name']]-f['bounds'][0])/f['step'];self.assertAlmostEqual(q,round(q))
    def test_no_duplicate_points(self):
        pts=[tuple(r['parameters'].values()) for r in self.p['trials']];self.assertEqual(len(pts),len(set(pts)))
    def test_triangle_hull_not_box(self):
        x=np.array([[0.,0.],[1.,0.],[0.,1.]]);q=np.array([[.2,.2],[.9,.9],[2,0]])
        self.assertEqual(in_training_domain(x,q).tolist(),[True,False,False])
    def test_time_domain(self):
        x=np.array([[1.],[3.]]);self.assertEqual(in_training_domain(x,np.array([[0.],[2.],[4.]])).tolist(),[False,True,False])
    def test_no_domain_on_empty_fit(self):self.assertFalse(in_training_domain(np.empty((0,2)),np.zeros((2,2))).any())
    def test_one_trial_budget(self):
        t=copy.deepcopy(self.t);t['next_trials']=1
        p=propose(t,self.r,self.c,self.m);self.assertEqual(p['trials'][0]['purpose'],'baseline_replication')
    def test_outside_hull_no_predictions(self):
        t=copy.deepcopy(self.t);t['factors'][0]['bounds'][1]=20
        p=propose(t,self.r,self.c,self.m)
        outside=[r for r in p['candidate_rows'] if not r['inside_training_domain']]
        self.assertTrue(outside);self.assertTrue(all(r['predicted_response_um'] is None for r in outside))
    def test_large_grid_lhs_bounded(self):
        t=copy.deepcopy(self.t);t['factors'][0]['step']=.05;t['factors'][1]['step']=.02
        pts=candidate_grid(t);self.assertLessEqual(len(pts),2048)
        for j,f in enumerate(t['factors']):
            self.assertTrue(np.all((pts[:,j]>=f['bounds'][0])&(pts[:,j]<=f['bounds'][1])))
    def test_json_no_nan(self):json.dumps(self.p,allow_nan=False)


class RunTests(unittest.TestCase):
    def test_end_to_end_files_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run'
            result=run(ROOT/'examples/width-calibration-demo/task.json',out)
            self.assertTrue((out/'result.json').is_file());self.assertTrue((out/'next_experiments.csv').is_file())
            self.assertTrue((out/'events.jsonl').is_file())
            self.assertFalse(result['physical_validation_performed'])
            self.assertFalse(result['external_llm_api_called'])
            with (out/'measurement_import_template.csv').open() as h:self.assertEqual(len(list(csv.reader(h))),1)
            with self.assertRaises(InputError):run(ROOT/'examples/width-calibration-demo/task.json',out)
    def test_prior_stage_unchanged(self):
        self.assertTrue((ROOT/'scripts/diffusion_model.py').exists())
    def test_model_json_no_pickle(self):
        t,r,_=bundle();c,m=calibrate(t,r);json.dumps(c,allow_nan=False)

if __name__=='__main__':unittest.main()
