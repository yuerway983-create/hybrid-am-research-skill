"""Tests of v0.2 bookkeeping and math; never evidence of physical manufacturing performance."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from _core import load_json, write_json
from review_evidence import validate_packet
from diffusion_model import evaluate_case, moments, scalar
from stage2_demo import run


class EvidenceTests(unittest.TestCase):
    def setUp(self):self.p=load_json(ROOT/'evidence/delay-evidence-001/evidence_packet.json')
    def test_valid_packet(self):
        r=validate_packet(self.p);self.assertTrue(r['valid'],r['errors']);self.assertEqual(r['source_count'],4)
        self.assertFalse(r['scientific_truth_verified_by_program']);self.assertFalse(r['live_retrieval_performed'])
    def test_locator_required(self):
        self.p['sources'][0]['source_locator']='';self.assertFalse(validate_packet(self.p)['valid'])
    def test_duplicate_identifier(self):
        self.p['sources'][1]['doi_or_identifier']=self.p['sources'][0]['doi_or_identifier'];self.assertFalse(validate_packet(self.p)['valid'])
    def test_unknown_claim_reference(self):
        self.p['claims'][0]['source_ids']=['not-read'];self.assertFalse(validate_packet(self.p)['valid'])
    def test_abstract_cannot_supply_checked_equation(self):
        self.p['sources'][0]['access_level']='abstract_only';self.assertFalse(validate_packet(self.p)['valid'])
    def test_inference_not_source_result(self):
        self.p['claims'][1]['status']='source_supported';self.assertFalse(validate_packet(self.p)['valid'])
    def test_literature_not_local_data(self):
        self.p['sources'][0]['local_data_claim']=True;self.assertFalse(validate_packet(self.p)['valid'])
    def test_missing_read_location(self):
        self.p['sources'][0]['actual_read_locations']=[];self.assertFalse(validate_packet(self.p)['valid'])
    def test_no_sources_is_invalid(self):
        self.p['sources']=[];self.assertFalse(validate_packet(self.p)['valid'])
    def test_nonobject_is_invalid(self):self.assertFalse(validate_packet(None)['valid'])
    def test_duplicate_claim_is_invalid(self):
        self.p['claims'].append(copy.deepcopy(self.p['claims'][0]));self.assertFalse(validate_packet(self.p)['valid'])
    def test_evidence_cli_offline(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'check'
            cp=subprocess.run([sys.executable,str(ROOT/'scripts/review_evidence.py'),'--packet',str(ROOT/'evidence/delay-evidence-001/evidence_packet.json'),'--out',str(out)],capture_output=True,text=True)
            self.assertEqual(cp.returncode,0,cp.stderr)
            self.assertTrue((out/'summary.md').exists())
            self.assertFalse(load_json(out/'evidence_check.json')['scientific_truth_verified_by_program'])


class ModelTests(unittest.TestCase):
    def setUp(self):self.c=load_json(ROOT/'examples/diffusion-demo/case.json')
    def test_known_moments(self):
        r=moments(3,2,4);self.assertEqual(r['concentration_variance_um2'],25);self.assertEqual(r['concentration_sigma_um'],5)
        self.assertAlmostEqual(r['concentration_fwhm_um'],2*math.sqrt(2*math.log(2))*5)
    def test_no_diffusion(self):self.assertEqual(moments(3,0,100)['concentration_sigma_um'],3)
    def test_initial_condition(self):self.assertEqual(moments(3,10,0)['concentration_variance_um2'],9)
    def test_line_source_limit(self):self.assertEqual(moments(0,2,4)['concentration_variance_um2'],16)
    def test_boolean_rejected(self):
        with self.assertRaises(ValueError):moments(True,1,1)
    def test_nonfinite_rejected(self):
        for v in (float('nan'),float('inf'),-1):
            with self.subTest(value=v),self.assertRaises(ValueError):moments(1,v,1)
    def test_overflow_rejected(self):
        with self.assertRaises(ValueError):moments(1e308,1,1)
    def test_unit_conversion(self):
        self.assertAlmostEqual(scalar({'value':4e-11,'unit':'m2/s','source_ref':'fixture'},'diffusivity'),40)
        self.assertEqual(scalar({'value':0.05,'unit':'mm','source_ref':'fixture'},'length'),50)
    def test_scalar_source_required(self):
        with self.assertRaises(ValueError):scalar({'value':1,'unit':'um'},'length')
    def test_scalar_unknown_units(self):
        with self.assertRaises(ValueError):scalar({'value':1,'unit':'pixels','source_ref':'fixture'},'length')
    def test_synthetic_case(self):
        r=evaluate_case(self.c);self.assertTrue(r['prediction_performed'],r['errors'])
        self.assertEqual(len(r['rows']),5);self.assertFalse(r['physical_validation_performed']);self.assertFalse(r['geometric_width_predicted'])
        self.assertEqual(r['mode'],'offline_demo');self.assertEqual(r['data_kind'],'synthetic_demo')
    def test_missing_diffusivity(self):
        self.c['parameters']['diffusivity']['value']=None;r=evaluate_case(self.c)
        self.assertFalse(r['prediction_performed']);self.assertEqual(r['rows'],[])
    def test_unsupported_observable(self):
        self.c['observable']='interface_strength_mpa';self.assertFalse(evaluate_case(self.c)['prediction_performed'])
    def test_fixed_conditions_required(self):
        self.c['fixed_conditions']={};self.assertFalse(evaluate_case(self.c)['prediction_performed'])
    def test_no_silent_extrapolation(self):
        self.c['evaluation_times']['values']=[9];self.assertFalse(evaluate_case(self.c)['prediction_performed'])
    def test_millisecond_conversion(self):
        self.c['evaluation_times']={'values':[1000],'unit':'ms'}
        r=evaluate_case(self.c);self.assertEqual(r['rows'][0]['elapsed_time_s'],1)
    def test_assumption_explicit(self):
        self.c['assumptions']['pre_gel_only']=False;self.assertFalse(evaluate_case(self.c)['prediction_performed'])
    def test_hardware_permission_forbidden(self):
        self.c['allow']['hardware_commands']=True;self.assertFalse(evaluate_case(self.c)['prediction_performed'])
    def test_dedicated_solver_forbidden(self):
        self.c['allow']['dedicated_simulation_software']=True;self.assertFalse(evaluate_case(self.c)['prediction_performed'])
    def test_negative_times(self):
        self.c['evaluation_times']['values']=[-1];self.assertFalse(evaluate_case(self.c)['prediction_performed'])
    def test_invalid_scenario_interval(self):
        self.c['diffusivity_scenario_bounds']['values']=[50,30];self.assertFalse(evaluate_case(self.c)['prediction_performed'])
    def test_scenario_not_ci(self):
        r=evaluate_case(self.c);self.assertIsNone(r['uncertainty']['coverage_probability'])
        self.assertIn('not_confidence_interval',r['uncertainty']['type'])
    def test_unquantified_uncertainty(self):
        del self.c['diffusivity_scenario_bounds'];self.assertEqual(evaluate_case(self.c)['uncertainty']['type'],'not_quantified')
    def test_synthetic_not_real(self):
        self.c['mode']='research';self.assertFalse(evaluate_case(self.c)['prediction_performed'])
    def test_real_requires_calibration(self):
        self.c['mode']='research';self.c['data_kind']='measured'
        for p in self.c['parameters'].values():p['origin']='user_calibration'
        with tempfile.TemporaryDirectory() as td:self.assertFalse(evaluate_case(self.c,Path(td))['prediction_performed'])
    def test_calibration_path_traversal(self):
        self.c.update(mode='research',data_kind='measured',calibration_file='../outside.json')
        for p in self.c['parameters'].values():p['origin']='user_calibration'
        with tempfile.TemporaryDirectory() as td:
            r=evaluate_case(self.c,Path(td));self.assertTrue(any('within case folder' in s for s in r['errors']))
    def test_calibration_context_mismatch(self):
        self.c.update(mode='research',data_kind='measured',calibration_file='cal.json')
        for p in self.c['parameters'].values():p['origin']='user_calibration'
        cal={k:copy.deepcopy(self.c[k]) for k in ('material_pair','fixed_conditions','data_kind','parameters','time_domain_s')}
        cal.update(material_pair='DIFFERENT',review_status='reviewed',observable='concentration_sigma_um',evidence_refs=['test fixture'])
        with tempfile.TemporaryDirectory() as td:
            write_json(Path(td)/'cal.json',cal);r=evaluate_case(self.c,Path(td))
            self.assertTrue(any('Calibration context mismatch' in s for s in r['errors']))
    def test_research_template_blocks(self):
        r=evaluate_case(load_json(ROOT/'templates/diffusion_case.json'))
        self.assertFalse(r['prediction_performed']);self.assertEqual(r['rows'],[])
    def test_case_nonobject(self):self.assertFalse(evaluate_case(None)['prediction_performed'])
    def test_missing_task_id(self):
        self.c['task_id']='';self.assertFalse(evaluate_case(self.c)['prediction_performed'])


class IntegrationTests(unittest.TestCase):
    def test_replay_and_guard_cases(self):
        with tempfile.TemporaryDirectory() as td:
            r=run(Path(td)/'run')
            for k in ('live_literature_search_in_this_run','live_github_search_in_this_run','automatic_skill_routing_in_this_script','physical_validation_performed','geometric_width_predicted','parameter_optimisation_performed'):
                self.assertFalse(r[k],k)
            self.assertEqual(r['negative_cases_correctly_blocked'],2)
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):run(Path(td))
    def test_numeric_cli(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'run'
            p=subprocess.run([sys.executable,str(ROOT/'scripts/diffusion_model.py'),'--case',str(ROOT/'examples/diffusion-demo/case.json'),'--out',str(out)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr);self.assertTrue((out/'moments.csv').exists())
    def test_missing_case_cli_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'run'
            p=subprocess.run([sys.executable,str(ROOT/'scripts/diffusion_model.py'),'--case',str(ROOT/'examples/diffusion-demo/missing-calibration.json'),'--out',str(out)],capture_output=True,text=True)
            self.assertEqual(p.returncode,2,p.stderr);self.assertFalse((out/'moments.csv').exists())

if __name__=='__main__':unittest.main()
