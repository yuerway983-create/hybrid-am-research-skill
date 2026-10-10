from __future__ import annotations
import copy,csv,json,math,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import agent_runtime as ar
from feedback_tools import (import_feedback,compare_feedback,validate_protocol,FrozenModel,
                           predict_frozen,number,timestamp,digest,read_table)
from calibration_planning import (load_measurements,calibrate,propose,write_csv,InputError,predict)
from synthetic_followup import make_fixture
from llm_agent import run_loop,OpenAITransport

TASK=ROOT/'examples/width-calibration-demo/task.json'
PROTO=ROOT/'examples/agent-feedback-demo/comparison_protocol.json'
EVID=ROOT/'evidence/delay-evidence-001/evidence_packet.json'

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.s=self.root/'session';self.i=0
        ar.init_session(TASK,self.s,protocol_path=PROTO,evidence_path=EVID,origin='test')
    def tearDown(self):self.tmp.cleanup()
    def call(self,name,args=None):
        self.i+=1
        return ar.dispatch(self.s,name,args or {},f't{self.i}',origin='test')
    def activate(self,stage,sid):
        return self.call('activate_skill',{'stage':stage,'skill_id':sid,'rationale':'test selection'})
    def through_plan(self):
        self.assertTrue(self.call('inspect_task')['ok']);self.activate('evidence','hybrid-am-evidence')
        self.assertTrue(self.call('review_evidence')['ok']);self.activate('calibration','measured-response-calibration')
        self.assertTrue(self.call('calibrate_response')['ok']);self.activate('planning','bounded-experiment-planning')
        self.assertTrue(self.call('plan_experiments')['ok'])
    def feedback(self):
        self.through_plan();m=make_fixture(self.s,self.root/'f');ar.attach_feedback(self.s,m)
        self.activate('feedback','descriptive-feedback');self.assertTrue(self.call('import_results')['ok'])
    def test_initial_state(self):
        r=self.call('session_status');self.assertEqual(r['result']['next_actions'],['inspect_task'])
    def test_no_network_permissions(self):
        s=ar.load(self.s/'state.json');self.assertFalse(s['upstream_auto_install']);self.assertFalse(s['hardware_execution_allowed'])
    def test_registry_candidates(self):
        r=self.call('find_skills',{'stage':'planning'});self.assertGreaterEqual(len(r['result']['candidates']),3)
    def test_unknown_tool_blocked(self):self.assertFalse(self.call('os.system')['ok'])
    def test_shell_argument_blocked(self):self.assertFalse(self.call('inspect_task',{'command':'rm -rf /'})['ok'])
    def test_missing_arguments(self):self.assertFalse(self.call('activate_skill',{'stage':'planning'})['ok'])
    def test_invalid_stage(self):self.assertFalse(self.call('find_skills',{'stage':'hardware'})['ok'])
    def test_disabled_skill_blocked(self):self.assertFalse(self.activate('planning','pymoo-multiobjective')['ok'])
    def test_wrong_stage_skill_blocked(self):self.assertFalse(self.activate('feedback','measured-response-calibration')['ok'])
    def test_returns_skill_instructions(self):
        r=self.activate('feedback','descriptive-feedback');self.assertIn('same-batch',r['result']['instructions'])
    def test_requires_activation(self):self.assertFalse(self.call('calibrate_response')['ok'])
    def test_requires_inspection(self):
        self.activate('calibration','measured-response-calibration');self.assertFalse(self.call('calibrate_response')['ok'])
    def test_feedback_not_invented(self):
        self.through_plan();self.activate('feedback','descriptive-feedback');self.assertFalse(self.call('import_results')['ok'])
    def test_update_requires_compare(self):
        self.feedback();self.activate('update','safe-model-update');self.assertFalse(self.call('prepare_update')['ok'])
    def test_duplicate_call_id_idempotent(self):
        a=ar.dispatch(self.s,'inspect_task',{},'same',origin='test')
        b=ar.dispatch(self.s,'inspect_task',{},'same',origin='test')
        self.assertTrue(b['idempotent_replay']);self.assertEqual(len(ar.load(self.s/'state.json')['call_ids']),1)
    def test_call_id_collision(self):
        ar.dispatch(self.s,'inspect_task',{},'same',origin='test')
        with self.assertRaises(InputError):ar.dispatch(self.s,'session_status',{},'same',origin='test')
    def test_invalid_call_id_path(self):
        with self.assertRaises(InputError):ar.dispatch(self.s,'inspect_task',{},'../escape',origin='test')
    def test_origin_mismatch(self):
        with self.assertRaises(InputError):ar.dispatch(self.s,'inspect_task',{},'x',origin='chat_host')
    def test_input_tampering(self):
        (self.s/'input/measurements.csv').write_text('tampered')
        self.assertFalse(self.call('inspect_task')['ok'])
    def test_output_tampering(self):
        self.call('inspect_task');(self.s/'artifacts/data_check.json').write_text('{}')
        self.assertFalse(self.call('session_status')['ok'])
    def test_active_lock(self):
        (self.s/'.call.lock').touch()
        with self.assertRaises(InputError):self.call('inspect_task')
    def test_session_not_overwritten(self):
        with self.assertRaises(InputError):ar.init_session(TASK,self.s,protocol_path=PROTO,origin='test')
    def test_log_chain(self):
        self.call('inspect_task');self.call('session_status');self.assertTrue(ar.verify_audit(self.s)['valid'])
    def test_log_detects_tampering(self):
        self.call('inspect_task');f=self.s/'events.jsonl';s=f.read_text().replace('inspect_task','evil_task');f.write_text(s)
        with self.assertRaises(InputError):ar.verify_audit(self.s)
    def test_no_current_evidence(self):
        s=self.root/'noe';ar.init_session(TASK,s,protocol_path=PROTO,origin='test')
        ar.dispatch(s,'inspect_task',{},'1',origin='test')
        ar.dispatch(s,'activate_skill',{'stage':'evidence','skill_id':'hybrid-am-evidence','rationale':'test'},'2',origin='test')
        r=ar.dispatch(s,'review_evidence',{},'3',origin='test');self.assertIn('needs_host_retrieval',r['error']['message'])
    def test_full_feedback_chain(self):
        self.feedback();r=self.call('compare_results');self.assertTrue(r['ok'])
        self.assertFalse(r['result']['real_printing_improvement_established_by_this_demo'])
    def test_update_freezes_original(self):
        self.feedback();self.call('compare_results');h=ar.file_hash(self.s/'artifacts/calibration.json')
        self.activate('update','safe-model-update');r=self.call('prepare_update')
        self.assertTrue(r['ok']);self.assertEqual(h,ar.file_hash(self.s/'artifacts/calibration.json'))
        with (self.s/'update/measurements.csv').open() as f: rows=list(csv.DictReader(f))
        self.assertTrue(all(x['partition']=='fit' for x in rows));self.assertTrue((self.s/'update/retired_holdout.csv').exists())
    def test_repeat_import_idempotent(self):
        self.feedback();a=self.call('import_results');self.assertTrue(a['ok'])
    def test_attach_not_model_tool(self):self.assertNotIn('attach_feedback',ar.SCHEMAS)
    def test_report_is_static(self):
        self.call('inspect_task');self.call('finish_report');page=(self.s/'index.html').read_text(encoding='utf-8')
        self.assertNotIn('<script',page);self.assertIn('synthetic_demo',page)
        self.assertIn('<title>Axiom Research · VPP–DIW v1.0</title>',page)
        self.assertIn('# Axiom Research · VPP–DIW v1.0 执行与回传报告',(self.s/'report.md').read_text(encoding='utf-8'))
    def test_sparse_routing(self):
        s=self.root/'sparse';ar.init_session(ROOT/'examples/insufficient-data-demo/task.json',s,protocol_path=PROTO,evidence_path=EVID,origin='test')
        def c(n,a={}):self.i+=1;return ar.dispatch(s,n,a,f's{self.i}',origin='test')
        c('inspect_task');c('activate_skill',{'stage':'evidence','skill_id':'hybrid-am-evidence','rationale':'test'});c('review_evidence')
        c('activate_skill',{'stage':'calibration','skill_id':'measured-response-calibration','rationale':'test'});r=c('calibrate_response')
        self.assertEqual(r['result']['status'],'needs_calibration_design')
        c('activate_skill',{'stage':'planning','skill_id':'bounded-experiment-planning','rationale':'test'})
        self.assertFalse(c('plan_experiments')['ok'])
        c('activate_skill',{'stage':'planning','skill_id':'calibration-only-planning','rationale':'test'})
        result=c('plan_experiments');self.assertTrue(result['ok'])
        self.assertTrue(all(t['predicted_response_um'] is None for t in result['result']['plan']['trials']))
    def test_tool_schemas(self):
        for t in ar.TOOLS:
            self.assertTrue(t['strict']);self.assertFalse(t['parameters']['additionalProperties'])
            self.assertEqual(set(t['parameters']['required']),set(t['parameters']['properties']))


class FeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.s=cls.root/'s'
        ar.init_session(TASK,cls.s,protocol_path=PROTO,evidence_path=EVID,origin='test')
        cls.task=ar.load(TASK);cls.proto=ar.load(PROTO)
        cls.rows,_=load_measurements(cls.task,TASK.parent/'measurements.csv')
        cls.cal,cls.model=calibrate(cls.task,cls.rows);cls.plan=propose(cls.task,cls.rows,cls.cal,cls.model);cls.plan.pop('candidate_rows')
        ar.save(cls.s/'artifacts/plan.json',cls.plan)
        cls.path=make_fixture(cls.s,cls.root/'fixture');cls.manifest=ar.load(cls.path)
        with (cls.path.parent/'executions.csv').open() as f: cls.exe=list(csv.DictReader(f))
        with (cls.path.parent/'measurements.csv').open() as f: cls.meas=list(csv.DictReader(f))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.local=tempfile.TemporaryDirectory();self.folder=Path(self.local.name)
        self.man=copy.deepcopy(self.manifest);self.e=copy.deepcopy(self.exe);self.m=copy.deepcopy(self.meas)
    def tearDown(self):self.local.cleanup()
    def imp(self):
        write_csv(self.folder/'executions.csv',self.e,list(self.exe[0]));write_csv(self.folder/'measurements.csv',self.m,list(self.meas[0]))
        return import_feedback(self.task,self.rows,self.cal,self.plan,self.man,self.folder,self.proto)
    def bad(self):
        with self.assertRaises(InputError):self.imp()
    def test_technical_repeats(self):
        r=self.imp();self.assertEqual(r['n_raw_measurements'],36);self.assertEqual(r['n_new_samples'],18)
    def test_setting_deviation_retained(self):
        r=self.imp();self.assertEqual(r['n_samples_with_setting_deviations'],1)
    def test_true_negative_not_success(self):
        c=compare_feedback(self.task,self.imp(),self.plan,self.proto)
        target=next(t for t in self.plan['trials'] if t['purpose']=='predicted_target_candidate')['trial_id']
        self.assertEqual(next(x for x in c['contrasts'] if x['trial_id']==target)['verdict'],'descriptive_worsening')
    def test_independent_batches(self):
        c=compare_feedback(self.task,self.imp(),self.plan,self.proto)
        self.assertTrue(all(x['n_independent_units']==3 for x in c['per_trial']))
    def test_no_confidence_or_pvalue(self):
        c=compare_feedback(self.task,self.imp(),self.plan,self.proto)
        self.assertTrue(all(x['p_value'] is None and x['confidence_interval'] is None for x in c['contrasts']))
    def test_no_baseline_inconclusive(self):
        ids={e['execution_id'] for e in self.e if next(t for t in self.plan['trials'] if t['trial_id']==e['trial_id'])['purpose']=='baseline_replication'}
        self.e=[e for e in self.e if e['execution_id'] not in ids];self.m=[m for m in self.m if m['execution_id'] not in ids]
        c=compare_feedback(self.task,self.imp(),self.plan,self.proto)
        self.assertTrue(all(x['verdict']=='inconclusive_no_concurrent_baseline' for x in c['contrasts']))
    def test_wrong_plan(self):self.man['plan_sha256']='x';self.bad()
    def test_wrong_protocol(self):self.man['comparison_protocol_sha256']='x';self.bad()
    def test_wrong_observable(self):self.man['observable']='interface_strength';self.bad()
    def test_wrong_unit(self):self.m[0]['response_unit']='mm';self.bad()
    def test_synthetic_to_real(self):self.man['data_kind']='measured';self.bad()
    def test_wrong_acquisition(self):self.man['acquisition_status']='reported_measurements';self.bad()
    def test_wrong_context(self):self.e[0]['context_id']='other';self.bad()
    def test_wrong_material(self):self.m[0]['material_pair']='other';self.bad()
    def test_fixed_conditions(self):self.man['fixed_conditions']={'exposure':'changed'};self.bad()
    def test_measurement_definition(self):self.man['measurement_definition']['method']='changed';self.bad()
    def test_duplicate_record(self):self.m.append(self.m[0].copy());self.bad()
    def test_historical_record(self):self.m[0]['record_id']=self.rows[0]['record_ids'][0];self.bad()
    def test_duplicate_sample(self):self.e[1]['sample_id']=self.e[0]['sample_id'];self.bad()
    def test_historical_sample(self):self.e[0]['sample_id']=self.rows[0]['sample_id'];self.bad()
    def test_historical_batch(self):self.e[0]['batch_id']=self.rows[0]['batch_id'];self.bad()
    def test_unknown_trial(self):self.e[0]['trial_id']='NO';self.bad()
    def test_unknown_execution(self):self.m[0]['execution_id']='NO';self.bad()
    def test_wrong_approval(self):self.e[0]['approval_status']='approved';self.bad()
    def test_wrong_execution_state(self):self.e[0]['execution_status']='suggested';self.bad()
    def test_timestamp_order(self):self.m[0]['measured_at']='2020-01-01T00:00:00+00:00';self.bad()
    def test_timezone_required(self):self.e[0]['executed_at']='2026-10-01T12:00:00';self.bad()
    def test_nan_response(self):self.m[0]['response_um']='nan';self.bad()
    def test_negative_response(self):self.m[0]['response_um']='-1';self.bad()
    def test_bounds_violation(self):self.e[0]['actual_speed_mm_s']='900';self.bad()
    def test_no_rows(self):self.m=[];self.bad()
    def test_path_escape(self):self.man['dataset_file']='../out.csv';self.bad()
    def test_boolean_number(self):
        with self.assertRaises(InputError):number(True,'bad')
    def test_protocol_numeric(self):
        p=copy.deepcopy(self.proto);p['target_tolerance_um']='8'
        with self.assertRaises(InputError):validate_protocol(p,self.task)
    def test_protocol_group(self):
        p=copy.deepcopy(self.proto);p['independent_unit']='sample_id'
        with self.assertRaises(InputError):validate_protocol(p,self.task)
    def test_frozen_json_matches_sklearn(self):
        x=np.asarray([[7.5,2.0],[10,3],[14,4]])
        np.testing.assert_allclose(FrozenModel(self.cal['model'],self.task['observable']).predict(x),predict(self.model,x,self.task),atol=1e-9)
    def test_outside_hull_not_predicted(self):
        value,inside=predict_frozen(self.task,self.cal,self.rows,{'speed_mm_s':20,'delay_s':4})
        self.assertFalse(inside);self.assertIsNone(value)
    def test_failure_model_no_prediction(self):
        c=copy.deepcopy(self.cal);c['model_usable_for_proposals']=False
        value,inside=predict_frozen(self.task,c,self.rows,{'speed_mm_s':10,'delay_s':3})
        self.assertTrue(inside);self.assertIsNone(value)
    def test_comparison_hash_guard(self):
        imported=self.imp();other=copy.deepcopy(self.plan);other['status']='changed'
        with self.assertRaises(InputError):compare_feedback(self.task,imported,other,self.proto)
    def test_zero_baseline_ratio(self):
        imported=self.imp();base=next(t['trial_id'] for t in self.plan['trials'] if t['purpose']=='baseline_replication')
        for r in imported['samples']:
            if r['trial_id']==base:r['absolute_target_error_um']=0
        c=compare_feedback(self.task,imported,self.plan,self.proto)
        self.assertTrue(all(r['relative_reduction_percent'] is None for r in c['contrasts']))


class AgentTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Path(self.tmp.name)/'s'
        ar.init_session(TASK,self.s,protocol_path=PROTO,evidence_path=EVID,origin='openai_responses')
    def tearDown(self):self.tmp.cleanup()
    def test_explicit_external_consent(self):
        with self.assertRaises(ValueError):OpenAITransport(allow_external=False)
    def test_missing_key(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):OpenAITransport(allow_external=True)
    def test_real_dispatch_from_mock_transport(self):
        seen=[]
        def tr(payload):
            seen.append(copy.deepcopy(payload))
            if len(seen)==1:return {'id':'MOCK1','model':'mock','status':'completed','output':[
                {'type':'reasoning','id':'mock-reason','encrypted_content':'opaque-test-sentinel'},
                {'type':'function_call','call_id':'call1','name':'inspect_task','arguments':'{}'}]}
            return {'id':'MOCK2','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'Contract test only.'}]}]}
        result=run_loop(self.s,'inspect','mock-not-a-real-model',tr,max_turns=2)
        self.assertTrue(ar.load(self.s/'state.json')['inspected']);self.assertEqual(result['turns'],2)
        self.assertTrue(any(x.get('encrypted_content')=='opaque-test-sentinel' for x in seen[1]['input']))
        self.assertTrue(any(x.get('type')=='function_call_output' for x in seen[1]['input']))
        self.assertNotIn('opaque-test-sentinel',(self.s/'events.jsonl').read_text())
    def test_invalid_json_arguments(self):
        def tr(p):return {'status':'completed','output':[{'type':'function_call','call_id':'x','name':'inspect_task','arguments':'bad'}]}
        result=run_loop(self.s,'test','mock',tr,max_turns=5);self.assertEqual(result['status'],'three_consecutive_tool_errors')
    def test_unauthorized_tool(self):
        def tr(p):return {'status':'completed','output':[{'type':'function_call','call_id':'x','name':'execute_python','arguments':'{}'}]}
        r=run_loop(self.s,'test','mock',tr,max_turns=3);self.assertEqual(r['status'],'three_consecutive_tool_errors')
    def test_noncompleted_response(self):
        r=run_loop(self.s,'test','mock',lambda p:{'status':'incomplete','output':[]});self.assertEqual(r['status'],'api_response_not_completed')
    def test_parallel_mutation_guard(self):
        calls=[{'type':'function_call','call_id':str(i),'name':'inspect_task','arguments':'{}'} for i in range(2)]
        r=run_loop(self.s,'test','mock',lambda p:{'status':'completed','output':calls});self.assertEqual(r['status'],'unexpected_parallel_calls')
    def test_max_turns_guard(self):
        with self.assertRaises(ValueError):run_loop(self.s,'test','mock',lambda p:{},max_turns=200)
    def test_model_required(self):
        with self.assertRaises(ValueError):run_loop(self.s,'test','',lambda p:{})

if __name__=='__main__':unittest.main()
