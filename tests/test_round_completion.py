from __future__ import annotations
import copy,csv,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import agent_runtime as ar
from round_tools import (DEFAULT_POLICY,validate_policy,attach_confirmation,confirmation_design,
                         known_ids,validate_confirmation)
from calibration_planning import InputError,write_csv,load_measurements
from feedback_tools import digest,FrozenModel
from synthetic_campaign import feedback_fixture,confirmation_fixture,response
from campaign_demo import run as campaign_run
TASK=ROOT/'examples/width-calibration-demo/task.json'
PROTO=ROOT/'examples/agent-feedback-demo/comparison_protocol.json'
EVID=ROOT/'evidence/delay-evidence-001/evidence_packet.json'

class RoundTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);self.s=self.root/'r1';self.i=0
        ar.init_session(TASK,self.s,protocol_path=PROTO,evidence_path=EVID,origin='test')
    def tearDown(self):self.t.cleanup()
    def c(self,n,a=None,s=None):
        self.i+=1;return ar.dispatch(s or self.s,n,a or {},f'c{self.i}',origin='test')
    def sel(self,st,sid,s=None):
        r=self.c('activate_skill',{'stage':st,'skill_id':sid,'rationale':'Unit test selection'},s)
        self.assertTrue(r['ok']);return r
    def planned(self):
        self.c('inspect_task');self.sel('evidence','hybrid-am-evidence');self.c('review_evidence')
        self.sel('calibration','measured-response-calibration');self.c('calibrate_response')
        self.sel('planning','bounded-experiment-planning');self.c('plan_experiments')
    def refitted(self,scenario='steady'):
        self.planned();m=feedback_fixture(self.s,self.root/'feed',scenario);ar.attach_feedback(self.s,m)
        self.sel('feedback','descriptive-feedback');self.c('import_results');self.c('compare_results')
        self.sel('update','safe-model-update');self.c('prepare_update')
        r=self.c('refit_update');self.assertTrue(r['ok']);return r['result']
    def confirmed(self,scenario='steady'):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf',scenario)
        attach_confirmation(self.s,m);return self.c('evaluate_update')['result']
    def child(self):
        self.assertTrue(self.confirmed()['promotion_allowed'])
        r=self.c('start_next_round',{'mode':'validated_update'});self.assertTrue(r['ok']);return self.s/'next_round'
    def test_new_tools_present(self):
        for name in ('refit_update','evaluate_update','start_next_round'):self.assertIn(name,ar.SCHEMAS)
    def test_synthetic_generator_not_agent_tool(self):
        self.assertNotIn('feedback_fixture',ar.SCHEMAS);self.assertNotIn('attach_confirmation',ar.SCHEMAS)
    def test_round_number(self):self.assertEqual(ar.load(self.s/'state.json')['round_index'],1)
    def test_policy_is_frozen_input(self):self.assertIn('input/update_policy.json',ar.load(self.s/'state.json')['input_hashes'])
    def test_refit_requires_earlier_feedback(self):
        self.sel('update','safe-model-update');self.assertFalse(self.c('refit_update')['ok'])
    def test_check_requires_refit(self):
        self.sel('update','safe-model-update');self.assertFalse(self.c('evaluate_update')['ok'])
    def test_next_requires_refit(self):
        self.sel('update','safe-model-update');self.assertFalse(self.c('start_next_round',{'mode':'validated_update'})['ok'])
    def test_next_mode_whitelist(self):self.assertFalse(self.c('start_next_round',{'mode':'overwrite'})['ok'])
    def test_candidate_has_no_holdout_for_fit(self):
        r=self.refitted();self.assertFalse(r['candidate']['confirmation_used_for_fitting'])
        self.assertFalse(r['candidate']['calibration']['model_usable_for_proposals'])
    def test_old_model_preserved(self):
        self.refitted();h=ar.file_hash(self.s/'artifacts/calibration.json');self.c('refit_update')
        self.assertEqual(h,ar.file_hash(self.s/'artifacts/calibration.json'))
    def test_refit_is_idempotent(self):
        a=self.refitted()['candidate'];b=self.c('refit_update')['result'];self.assertEqual(a,b)
    def test_no_confirmation_returns_request(self):
        self.refitted();r=self.c('evaluate_update');self.assertTrue(r['ok']);self.assertEqual(r['result']['status'],'needs_fresh_confirmation')
    def test_missing_confirmation_cannot_promote(self):
        self.refitted();self.assertFalse(self.c('start_next_round',{'mode':'validated_update'})['ok'])
    def test_missing_confirmation_allows_calibration_next(self):
        self.refitted();r=self.c('start_next_round',{'mode':'calibration_only'});self.assertTrue(r['ok'])
        child=self.s/'next_round';self.sel('planning','calibration-only-planning',child)
        p=self.c('plan_experiments',s=child)['result']['plan'];self.assertTrue(all(t['predicted_response_um'] is None for t in p['trials']))
    def test_bad_model_is_rejected(self):
        r=self.confirmed('severe');self.assertFalse(r['promotion_allowed']);self.assertEqual(r['status'],'updated_model_rejected')
    def test_rejected_model_not_promoted(self):
        self.confirmed('severe');self.assertFalse(self.c('start_next_round',{'mode':'validated_update'})['ok'])
    def test_rejected_model_has_calibration_fallback(self):
        self.confirmed('severe');self.assertTrue(self.c('start_next_round',{'mode':'calibration_only'})['ok'])
    def test_pass_then_next(self):
        child=self.child();self.assertEqual(ar.load(child/'state.json')['round_index'],2)
        self.sel('planning','bounded-experiment-planning',child);self.assertTrue(self.c('plan_experiments',s=child)['ok'])
    def test_child_records_link(self):
        child=self.child();self.assertTrue((child/'artifacts/parent_link.json').is_file())
    def test_consumed_holdout_not_reused(self):
        child=self.child()
        with (child/'input/measurements.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertTrue(all(r['partition']=='fit' for r in rows))
        self.assertFalse(any('CONF' in r['sample_id'] for r in rows))
    def test_child_inherits_calibration_not_refit(self):
        child=self.child();cal=ar.load(child/'artifacts/calibration.json')
        self.sel('calibration','measured-response-calibration',child);r=self.c('calibrate_response',s=child)
        self.assertEqual(r['result'],cal)
    def test_confirmation_ids_in_lineage(self):
        child=self.child();ids=ar.load(child/'state.json')['lineage_ids'];self.assertTrue(any('CONF' in i for i in ids['sample_ids']))
    def test_prior_feedback_not_accepted_in_child(self):
        child=self.child();self.sel('planning','bounded-experiment-planning',child);self.c('plan_experiments',s=child)
        m=feedback_fixture(child,self.root/'feed2')
        with (m.parent/'executions.csv').open() as f:rows=list(csv.DictReader(f))
        for r in rows:r['sample_id']='R01-'+r['sample_id'].split('-',1)[1];r['batch_id']='R01-'+r['batch_id'].split('-',1)[1]
        write_csv(m.parent/'executions.csv',rows)
        with (m.parent/'measurements.csv').open() as f:rows=list(csv.DictReader(f))
        for r in rows:r['sample_id']='R01-'+r['sample_id'].split('-',1)[1];r['batch_id']='R01-'+r['batch_id'].split('-',1)[1]
        write_csv(m.parent/'measurements.csv',rows)
        ar.attach_feedback(child,m);self.sel('feedback','descriptive-feedback',child)
        self.assertFalse(self.c('import_results',s=child)['ok'])
    def test_repeat_confirmation_attachment_blocked(self):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf');attach_confirmation(self.s,m)
        with self.assertRaises(InputError):attach_confirmation(self.s,m)
    def test_confirmation_before_freeze_blocked(self):
        with self.assertRaises((InputError,FileNotFoundError)):attach_confirmation(self.s,self.root/'no.json')
    def mutate_confirmation(self,fn):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf');obj=ar.load(m);fn(obj);ar.save(m,obj)
        with self.assertRaises(InputError):attach_confirmation(self.s,m)
    def test_wrong_model_digest(self):self.mutate_confirmation(lambda o:o.update(candidate_sha256='0'*64))
    def test_wrong_confirmation_plan(self):self.mutate_confirmation(lambda o:o.update(confirmation_plan_sha256='0'*64))
    def test_real_synthetic_mixing(self):self.mutate_confirmation(lambda o:o.update(data_kind='measured'))
    def test_measurement_definition_change(self):self.mutate_confirmation(lambda o:o.update(measurement_definition={}))
    def test_arbitrary_confirmation_path(self):self.mutate_confirmation(lambda o:o.update(dataset_file='../other.csv'))
    def test_unreserved_confirmation(self):self.mutate_confirmation(lambda o:o.update(reserved_after_candidate_freeze=False))
    def test_confirmation_not_generated_after_model_fail(self):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf')
        with (m.parent/'measurements.csv').open() as f:rows=list(csv.DictReader(f))
        for r in rows:r['batch_id']='FIT-00'
        # Use actual historical identifier to test group independence.
        hist=ar.load(self.s/'artifacts/aggregated.json')[0]['batch_id']
        for r in rows:r['batch_id']=hist
        write_csv(m.parent/'measurements.csv',rows)
        with self.assertRaises(InputError):attach_confirmation(self.s,m)
    def test_fit_partition_in_confirmation_blocked(self):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf')
        with (m.parent/'measurements.csv').open() as f:rows=list(csv.DictReader(f))
        for r in rows:r['partition']='fit'
        write_csv(m.parent/'measurements.csv',rows)
        with self.assertRaises(InputError):attach_confirmation(self.s,m)
    def test_confirmation_setting_outside_plan_blocked(self):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf')
        with (m.parent/'measurements.csv').open() as f:rows=list(csv.DictReader(f))
        rows[0]['delay_s']=2.12345
        write_csv(m.parent/'measurements.csv',rows)
        with self.assertRaises(InputError):attach_confirmation(self.s,m)
    def test_confirmation_coverage_incomplete_blocked(self):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf')
        with (m.parent/'measurements.csv').open() as f:rows=list(csv.DictReader(f))
        rows=[r for r in rows if '-S-0-0' not in r['sample_id'] and '-S-1-0' not in r['sample_id']]
        write_csv(m.parent/'measurements.csv',rows)
        with self.assertRaises(InputError):attach_confirmation(self.s,m)
    def test_tamper_confirmation_after_attachment(self):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf');attach_confirmation(self.s,m)
        (self.s/'confirmation_input/measurements.csv').write_text('tampered')
        self.assertFalse(self.c('evaluate_update')['ok'])
    def test_tamper_policy_after_init(self):
        ar.save(self.s/'input/update_policy.json',DEFAULT_POLICY|{'max_rounds':10})
        self.assertFalse(self.c('session_status')['ok'])
    def test_one_confirmation_group_fails_numeric_gate(self):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf')
        with (m.parent/'measurements.csv').open() as f:rows=list(csv.DictReader(f))
        rows=[r for r in rows if '-S-0-' in r['sample_id']];write_csv(m.parent/'measurements.csv',rows)
        attach_confirmation(self.s,m);r=self.c('evaluate_update')['result']
        self.assertFalse(r['promotion_allowed']);self.assertFalse(r['checks']['fresh_independent_groups'])
    def test_non_degradation_gate(self):
        self.refitted();m=confirmation_fixture(self.s,self.root/'conf')
        task=ar.load(TASK);old=ar.load(self.s/'artifacts/calibration.json')
        with (m.parent/'measurements.csv').open() as f:rows=list(csv.DictReader(f))
        # Unit-test oracle, not the external demo: deliberately make old model exact.
        x=np.asarray([[float(r['speed_mm_s']),float(r['delay_s'])] for r in rows])
        y=FrozenModel(old['model'],task['observable']).predict(x)
        for r,z in zip(rows,y):r['response_um']=float(z)
        write_csv(m.parent/'measurements.csv',rows);attach_confirmation(self.s,m)
        result=self.c('evaluate_update')['result'];self.assertFalse(result['checks']['non_degradation_if_comparable'])
    def test_same_next_round_idempotent(self):
        self.child();self.assertTrue(self.c('start_next_round',{'mode':'validated_update'})['ok'])
    def test_cannot_repurpose_existing_child(self):
        self.child();self.assertFalse(self.c('start_next_round',{'mode':'calibration_only'})['ok'])
    def test_update_no_synthetic_generation_dependency(self):
        code=(ROOT/'scripts/round_tools.py').read_text();self.assertNotIn('from synthetic',code)
    def test_confirmation_generator_rejects_real(self):
        self.refitted();t=ar.load(self.s/'update/task.json');t['data_kind']='measured';ar.save(self.s/'update/task.json',t)
        with self.assertRaises(InputError):confirmation_fixture(self.s,self.root/'notreal')
    def test_full_chain_integrity(self):
        child=self.child();self.c('finish_report');ar.verify_integrity(self.s,ar.load(self.s/'state.json'))
        self.assertTrue(ar.verify_audit(self.s)['valid']);ar.verify_integrity(child,ar.load(child/'state.json'))
    def test_round_limit(self):
        # Predeclare limit before creating session; never change it after outcomes.
        p=self.root/'p.json';ar.save(p,DEFAULT_POLICY|{'max_rounds':1})
        self.s=self.root/'limited';ar.init_session(TASK,self.s,protocol_path=PROTO,evidence_path=EVID,origin='test',update_policy_path=p)
        self.refitted();r=self.c('start_next_round',{'mode':'calibration_only'});self.assertFalse(r['ok']);self.assertIn('budget',r['error']['message'])
    def test_confirmation_is_consumed_once(self):
        self.confirmed();a=ar.load(self.s/'artifacts/update_evaluation.json');b=self.c('evaluate_update')['result'];self.assertEqual(a,b)
    def test_no_interval_claims(self):
        r=self.confirmed();self.assertIsNone(r['confidence_interval']);self.assertIsNone(r['p_value'])
    def test_three_round_acceptance(self):
        out=self.root/'campaign';r=campaign_run(out,rounds=3)
        self.assertEqual(len(r['rounds']),3)
        self.assertTrue(all(x['predictive_plan'] for x in r['rounds']))
        self.assertFalse(r['physical_performance_improvement_established'])
    def test_two_round_shift_failure(self):
        r=campaign_run(self.root/'shift',scenario='shifted',rounds=2)
        self.assertEqual(r['rounds'][0]['continuation_mode'],'calibration_only')
        self.assertFalse(r['rounds'][1]['predictive_plan'])
    def test_policy_invalid_max(self):
        with self.assertRaises(InputError):validate_policy(DEFAULT_POLICY|{'max_rounds':11})
    def test_policy_boolean_count(self):
        with self.assertRaises(InputError):validate_policy(DEFAULT_POLICY|{'confirmation_conditions':True})
    def test_policy_negative_margin(self):
        with self.assertRaises(InputError):validate_policy(DEFAULT_POLICY|{'max_rmse_increase_um':-1})
    def test_policy_finite_margin(self):
        with self.assertRaises(InputError):validate_policy(DEFAULT_POLICY|{'max_rmse_increase_um':float('nan')})
    def test_unknown_synthetic_world(self):
        with self.assertRaises(InputError):response({'speed_mm_s':10,'delay_s':3},'geometric_track_width_um','imaginary')


class EvidenceAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.s=self.root/'no_evidence'
        ar.init_session(TASK,self.s,protocol_path=PROTO,origin='test')
    def tearDown(self):self.tmp.cleanup()
    def test_attach_actual_packet(self):
        r=ar.attach_evidence(self.s,EVID);self.assertFalse(r['online_search_performed_by_this_command'])
        self.assertTrue((self.s/'input/evidence.json').is_file())
    def test_no_unapproved_replacement(self):
        ar.attach_evidence(self.s,EVID)
        with self.assertRaises(InputError):ar.attach_evidence(self.s,EVID)
    def test_attachment_not_llm_tool(self):self.assertNotIn('attach_evidence',ar.SCHEMAS)
    def test_invalid_packet_rejected(self):
        p=self.root/'invalid.json';ar.save(p,{})
        with self.assertRaises((InputError,KeyError)):ar.attach_evidence(self.s,p)
    def test_attached_packet_is_hashed(self):
        ar.attach_evidence(self.s,EVID)
        self.assertEqual(ar.file_hash(self.s/'input/evidence.json'),ar.load(self.s/'state.json')['input_hashes']['input/evidence.json'])
    def test_input_tamper_prevents_attachment(self):
        (self.s/'input/task.json').write_text('{}')
        with self.assertRaises(InputError):ar.attach_evidence(self.s,EVID)

class MultiRoundTransportTests(unittest.TestCase):
    def test_responses_loop_switches_child_session(self):
        from llm_agent import run_loop
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);s=root/'api_test'
            ar.init_session(TASK,s,protocol_path=PROTO,evidence_path=EVID,origin='openai_responses')
            i=0
            def c(n,a=None):
                nonlocal i;i+=1
                r=ar.dispatch(s,n,a or {},f'p{i}',origin='openai_responses');self.assertTrue(r['ok']);return r['result']
            def activate(st,sid):c('activate_skill',{'stage':st,'skill_id':sid,'rationale':'Mock transport preparation'})
            c('inspect_task');activate('evidence','hybrid-am-evidence');c('review_evidence')
            activate('calibration','measured-response-calibration');c('calibrate_response')
            activate('planning','bounded-experiment-planning');c('plan_experiments')
            ar.attach_feedback(s,feedback_fixture(s,root/'f'));activate('feedback','descriptive-feedback');c('import_results');c('compare_results')
            activate('update','safe-model-update');c('prepare_update');c('refit_update')
            attach_confirmation(s,confirmation_fixture(s,root/'conf'));c('evaluate_update')
            sequence=[('start_next_round',{'mode':'validated_update'}),('session_status',{}),
                ('find_skills',{'stage':'planning'}),('activate_skill',{'stage':'planning','skill_id':'bounded-experiment-planning','rationale':'Mock response for protocol contract test'}),
                ('plan_experiments',{}),('finish_report',{})]
            turns=iter(sequence)
            def transport(payload):
                try:
                    name,args=next(turns)
                    return {'status':'completed','output':[{'type':'function_call','name':name,'arguments':json.dumps(args),'call_id':name+'-id'}]}
                except StopIteration:
                    return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'Mock: awaiting external data'}]}]}
            result=run_loop(s,'Test transport switching','mock-not-a-real-model',transport,max_turns=12)
            self.assertEqual(result['phase'],'awaiting_external_experiment')
            self.assertTrue((s/'next_round/artifacts/plan.json').exists())
            self.assertTrue((s/result['invocation']/'metadata.json').exists())

if __name__=='__main__':unittest.main()
