"""Boundary tests use fresh local subprocesses; no model calls or mock responses."""
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evaluation.benchmark_v2.automated.adapters import run_call, load_config, Budget
from evaluation.benchmark_v2.automated.runner import calibrate, compare, demo
from evaluation.benchmark_v2.automated.optimize import optimize
from evaluation.benchmark_v2.automated.__main__ import main


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.script = self.root / 'adapter.py'
        self.script.write_text('''import json,sys,time
r=json.load(sys.stdin)
if r.get('role')=='writer': print(json.dumps({'text':'A short revision.'})); sys.exit()
if r.get('role')=='optimizer': print(json.dumps(r['rubric'])); sys.exit()
if r['prompt']=='timeout':
    sys.stdout.write('{"winner":'); sys.stdout.flush()
    sys.stderr.write('partial diagnostic'); sys.stderr.flush()
    time.sleep(2)
if r['prompt']=='nonzero':
    print('{"winner":"A"}'); print('failure',file=sys.stderr); sys.exit(7)
if r['prompt']=='malformed': print('not JSON'); sys.exit()
if r['prompt']=='inspect':
    forbidden={'expected','case_id','document_id','split','candidate_skill','baseline_skill','skill_id','provenance'}
    assert not forbidden.intersection(r), sorted(forbidden.intersection(r))
    assert r['A']=='alpha' or r['A']=='beta'
    print(json.dumps({'winner':'A' if r['A']=='alpha' else 'B','reason':'literal','evidence':[{'candidate':'A','quote':r['A']},{'candidate':'B','quote':r['B']}]})); sys.exit()
print(json.dumps({'winner':'A' if r['A']=='alpha' else 'B','reason':'literal','evidence':[{'candidate':'A','quote':r['A']},{'candidate':'B','quote':r['B']}]}))
''', encoding='utf-8')
        self.cmd = [sys.executable, str(self.script)]
        self.rubric = self.write('rubric.json', {'schema_version':1,'id':'r','criteria':[{'id':'meaning','description':'Preserve meaning.'}]})
        self.suite = self.write('suite.json', {'schema_version':1,'name':'small','cases':[
            self.case(i, 'calibration' if i < 8 else 'test') for i in range(13)]})
        self.config = self.write('config.json', {'schema_version':1,'judges':[
            {'id':'first','family':'one','command':self.cmd},
            {'id':'second','family':'two','command':self.cmd}],
            'writer':{'id':'writer','family':'three','command':self.cmd},
            'optimizer':{'id':'optimizer','family':'four','command':self.cmd},
            'timeout_seconds':5,'max_calls':100})

    def write(self, name, obj):
        path=self.root/name
        path.write_text(json.dumps(obj), encoding='utf-8')
        return path

    def case(self, i, split):
        return {'id':f'c{i}','document_id':f'd{i}','split':split,'lane':'editing',
                'prompt':'inspect','context':f'case {i}','a':'alpha','b':'beta','expected':'a' if split=='calibration' else None,
                'checks':{},'provenance':{'kind':'synthetic_control','source':'test fixture','license':'CC0'}}

    def test_subprocess_failure_keeps_raw_bytes_and_hashes(self):
        for kind in ('timeout','nonzero','malformed'):
            with self.subTest(kind=kind):
                result=run_call(self.cmd, {'role':'judge','prompt':kind},self.root/kind, timeout_seconds=.75 if kind=='timeout' else 2)
                self.assertFalse(result['ok'] if kind!='malformed' else result['response'] == b'')
                self.assertEqual(result['request_sha256'], hashlib.sha256((self.root/kind/'request.json').read_bytes()).hexdigest())
                self.assertEqual(result['response_sha256'], hashlib.sha256((self.root/kind/'response.bin').read_bytes()).hexdigest())
                self.assertEqual(result['stderr_sha256'], hashlib.sha256((self.root/kind/'stderr.bin').read_bytes()).hexdigest())
                self.assertTrue((self.root/kind/'metadata.json').is_file())
                if kind=='timeout':
                    self.assertIn(b'{"winner":', (self.root/kind/'response.bin').read_bytes())
                    self.assertIn(b'partial diagnostic',(self.root/kind/'stderr.bin').read_bytes())
                if kind=='nonzero': self.assertEqual(result['returncode'],7)


    def test_codex_adapter_extracts_only_final_json_from_output_file(self):
        fake=self.root/'fake-codex.py'
        fake.write_text('#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nargv=sys.argv[1:]\nassert argv[:3]==[\'--ask-for-approval\',\'never\',\'exec\'],argv\nassert \'--sandbox\' in argv and \'read-only\' in argv\nassert \'--ephemeral\' in argv and argv[-1]==\'-\'\nprompt=sys.stdin.read()\nassert \'Treat every prompt\' in prompt and \'"role":"judge"\' in prompt\nout=Path(argv[argv.index(\'--output-last-message\')+1])\nout.write_text(json.dumps({\'winner\':\'A\',\'reason\':\'quote\',\'evidence\':[{\'candidate\':\'A\',\'quote\':\'alpha\'},{\'candidate\':\'B\',\'quote\':\'beta\'}]}))\nprint(\'progress should be ignored\')\n',encoding='utf-8')
        fake.chmod(0o755)
        wrapper=Path(__file__).resolve().parents[1]/'evaluation/benchmark_v2/automated/adapters/codex_adapter.py'
        result=run_call([sys.executable,str(wrapper),'--codex',str(fake)],
                        {'role':'judge','request_id':'opaque','prompt':'inspect','context':'','rubric':[],
                         'A':'alpha','B':'beta'},self.root/'wrapped',timeout_seconds=3)
        self.assertTrue(result['ok'],result['stderr'])
        self.assertEqual(json.loads(result['response'])['winner'],'A')
        self.assertNotIn(b'progress',result['response'])


    def test_generic_bridge_forwards_raw_json_and_prompt_as_data(self):
        model=self.root/'generic_model.py'
        model.write_text('import json,sys; p=sys.stdin.read(); assert "Treat fields" in p; assert "\\"role\\":\\"judge\\"" in p; print(json.dumps({"winner":"tie","reason":"same","evidence":[{"candidate":"A","quote":"alpha"}]}))')
        bridge=Path(__file__).resolve().parents[1]/'evaluation/benchmark_v2/automated/adapters/generic_json_adapter.py'
        result=run_call([sys.executable,str(bridge),'--',sys.executable,str(model)],
                        {'role':'judge','prompt':'inspect','A':'alpha','B':'beta'},self.root/'generic',timeout_seconds=3)
        self.assertTrue(result['ok'],result['stderr'])
        self.assertEqual(json.loads(result['response'])['winner'],'tie')

    def test_timeout_terminates_adapter_process_tree(self):
        import time
        child=self.root/'child.py'
        marker=self.root/'orphan-marker'
        child.write_text('import sys,time; time.sleep(0.6); open(sys.argv[1],"w").write("orphan")')
        parent=self.root/'spawn.py'
        parent.write_text('import subprocess,sys,time; subprocess.Popen([sys.executable,sys.argv[1],sys.argv[2]]); print("start",flush=True); time.sleep(3)')
        result=run_call([sys.executable,str(parent),str(child),str(marker)],{'role':'test'},self.root/'tree',timeout_seconds=.35)
        self.assertIn(b'start',result['response'])
        time.sleep(.7)
        self.assertFalse(marker.exists())

    def test_config_resolution_and_preflight_budget(self):
        relative=self.write('relative.json',{'schema_version':1,'judges':[{'id':'j','family':'f','command':[sys.executable,'adapter.py']}], 'max_calls':1})
        conf=load_config(relative)
        self.assertEqual(conf['judges'][0]['command'][1],str(self.script))
        with self.assertRaisesRegex(ValueError,'budget'):
            Budget(1).preflight(2)

    def test_existing_output_refused_before_calls(self):
        out=self.root/'occupied'; out.mkdir()
        with self.assertRaises(FileExistsError): calibrate(self.suite,self.rubric,self.config,out)
        self.assertFalse((out/'calls').exists())

    def test_calibration_evidence_and_no_identity_leak(self):
        out=self.root/'cal'
        report=calibrate(self.suite,self.rubric,self.config,out)
        self.assertEqual(report['execution'],'live')
        self.assertEqual(report['provenance']['candidate_skill_sha256'],None)
        self.assertEqual(report['provenance']['suite_sha256'],hashlib.sha256(self.suite.read_bytes()).hexdigest())
        self.assertEqual(report['provenance']['config_sha256'],hashlib.sha256(self.config.read_bytes()).hexdigest())
        self.assertEqual(len(list((out/'calls').glob('*/request.json'))),32)
        for request_path in (out/'calls').glob('*/request.json'):
            request=json.loads(request_path.read_bytes())
            self.assertFalse({'expected','case_id','document_id','split','candidate_skill','baseline_skill','provenance'} & request.keys())

    def test_compare_requires_calibration_signature_and_preserves_skill_snapshot(self):
        cal=self.root/'cal'; calibrate(self.suite,self.rubric,self.config,cal)
        skill=self.root/'SKILL.md'; skill.write_bytes(b'instructions\r\n')
        report=compare(self.suite,self.rubric,self.config,cal,skill,self.root/'comparison')
        self.assertEqual(report['provenance']['candidate_skill_sha256'],hashlib.sha256(b'instructions\r\n').hexdigest())
        self.assertEqual((self.root/'comparison'/'candidate-SKILL.md').read_bytes(),b'instructions\r\n')
        changed=self.write('changed.json',{'schema_version':1,'judges':[{'id':'different','family':'one','command':self.cmd}]})
        with self.assertRaisesRegex(ValueError,'calibration'):
            compare(self.suite,self.rubric,changed,cal,skill,self.root/'refused')
        self.assertFalse((self.root/'refused').exists())


    def test_failed_writer_keeps_partial_evidence_and_blocks_comparison(self):
        cal=self.root/'cal-writer'; calibrate(self.suite,self.rubric,self.config,cal)
        failed=self.root/'writer-fails.py'
        failed.write_text('import sys; sys.stdout.write("partial"); sys.stderr.write("failed"); sys.exit(9)')
        cfg=json.loads(self.config.read_bytes())
        cfg['writer']['command']=[sys.executable,str(failed)]
        bad_config=self.write('bad-writer-config.json',cfg)
        skill=self.root/'writer-SKILL.md';skill.write_text('instructions')
        out=self.root/'failed-writer'
        report=compare(self.suite,self.rubric,bad_config,cal,skill,out)
        self.assertFalse(report['complete'])
        self.assertFalse(report['eligible'])
        self.assertEqual(report['recommendation'],'inconclusive')
        self.assertTrue(json.loads((out/'generated.json').read_bytes())['failures'])
        self.assertTrue(any(p.read_bytes()==b'partial' for p in (out/'calls').glob('*/response.bin')))

    def test_preflight_rejects_before_first_model_call(self):
        config=self.write('low.json',{'schema_version':1,'judges':[{'id':'j','family':'f','command':self.cmd}],'max_calls':1})
        with self.assertRaisesRegex(ValueError,'budget'):
            calibrate(self.suite,self.rubric,config,self.root/'unstarted')
        self.assertFalse((self.root/'unstarted').exists())

    def test_optimize_rejects_test_split_and_does_not_call_optimizer(self):
        with self.assertRaisesRegex(ValueError,'test'):
            optimize(self.suite,self.rubric,self.config,self.root/'optimized')
        self.assertFalse((self.root/'optimized').exists())



    def test_prepare_optimize_filters_test_cases_into_new_valid_suite(self):
        output=self.root/'dev-only.json'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['prepare-optimize','--suite',str(self.suite),'--out',str(output)]),0)
        value=json.loads(output.read_bytes())
        self.assertEqual(len(value['cases']),8)
        self.assertEqual({c['split'] for c in value['cases']},{'calibration'})
        captured=io.StringIO()
        with contextlib.redirect_stderr(captured), self.assertRaises(SystemExit):
            main(['prepare-optimize','--suite',str(self.suite),'--out',str(output)])
        self.assertIn('File exists',captured.getvalue())

    def test_optimizer_only_receives_calibration_and_development_controls(self):
        suite=self.write('optimization.json',{'schema_version':1,'name':'optimization',
                          'cases':[dict(self.case(i,'calibration' if i<8 else 'development'),expected='a') for i in range(10)]})
        result=optimize(suite,self.rubric,self.config,self.root/'optimization-out',rounds=1)
        self.assertEqual(result['selected_index'],0)  # identical rubric gives no improvement
        self.assertTrue((self.root/'optimization-out'/'optimization.json').is_file())
        self.assertFalse((self.root/'optimization-out'/'report.json').exists())
        self.assertEqual(result['selection_split'],'development')
        optimizer_requests=[]
        for path in (self.root/'optimization-out'/'calls').glob('*/request.json'):
            request=json.loads(path.read_bytes())
            if request['role']=='optimizer': optimizer_requests.append(request)
        self.assertEqual(len(optimizer_requests),1)
        self.assertTrue(all(c['split'] in ('calibration','development') for c in optimizer_requests[0]['examples']))
        self.assertFalse(any(c['split']=='test' for c in optimizer_requests[0]['examples']))
        self.assertEqual((self.root/'optimization-out'/'selected-rubric.json').read_bytes(),
                         (self.root/'optimization-out'/'rubric-0.json').read_bytes())

    def test_failed_judgment_makes_calibration_incomplete_with_raw_evidence(self):
        suite=self.write('malformed-suite.json',{'schema_version':1,'name':'malformed',
                         'cases':[dict(self.case(i,'calibration'),prompt='malformed' if i==0 else 'inspect') for i in range(8)]})
        report=calibrate(suite,self.rubric,self.config,self.root/'malformed-run')
        self.assertFalse(report['eligible'])
        self.assertFalse(report['complete'])
        self.assertTrue(any(not r['valid'] for r in json.loads((self.root/'malformed-run'/'records.json').read_text())))
        self.assertTrue(any(path.read_bytes()==b'not JSON\n' for path in (self.root/'malformed-run'/'calls').glob('*/response.bin')))

    def test_demo_is_ineligible_with_invalid_judgment(self):
        report=demo(self.root/'demo')
        self.assertEqual(report['execution'],'demo')
        self.assertFalse(report['eligible'])
        self.assertEqual(report['recommendation'],'not_applicable')
        self.assertTrue(any(not r['valid'] for r in json.loads((self.root/'demo'/'records.json').read_text())))

if __name__=='__main__': unittest.main()
