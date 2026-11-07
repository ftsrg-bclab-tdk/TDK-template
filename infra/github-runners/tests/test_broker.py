import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'session/broker.py'
spec=importlib.util.spec_from_file_location('broker',PATH);broker=importlib.util.module_from_spec(spec);spec.loader.exec_module(broker)
REPO='test/pilot';LABEL='bme-isolated-native-v1'


class GitHub:
    def __init__(self):
        self.jobs=[{'id':4,'run_id':2,'status':'queued','labels':[LABEL],'runner_id':None}]
        self.registrations=[];self.created=0;self.deleted=[];self.fail_response=False
    def pages(self,path,key):
        if key=='runners':return copy.deepcopy(self.registrations)
        if key=='jobs':return copy.deepcopy(self.jobs)
        return [{'id':2}] if 'status=queued' in path else []
    def request(self,path,method='GET',data=None):
        if 'generate-jitconfig' in path:
            self.created+=1;value={'id':self.created,'name':data['name'],'busy':False}
            self.registrations.append(value)
            if self.fail_response:self.fail_response=False;raise broker.APIError(0)
            return {'runner':value,'encoded_jit_config':'SENSITIVE_JIT'}
        if method=='DELETE':self.deleted.append(int(path.rsplit('/',1)[1]));return None
        if '/actions/jobs/' in path:return copy.deepcopy(self.jobs[0])
        return {'status':'completed' if self.jobs[0]['status']=='completed' else 'in_progress'}


class Engine:
    def __init__(self):self.sessions=[];self.stopped=[];self.calls=[];self.fail_after_start=False;self.clean=True;self.preparing=False
    def call(self,action,identifier=None,data=None,seconds=None,disk_gib=8,paper=False):
        self.calls.append((action,identifier))
        if action=='list':return copy.deepcopy(self.sessions)
        if action=='start':
            item={k:v for k,v in data.items() if k!='jit'};item.update(id=identifier,started_at=100000000000,disk_gib=disk_gib)
            self.sessions.append(item)
            if self.fail_after_start:self.fail_after_start=False;raise RuntimeError('lost response')
            return item
        if action=='status':
            return {'ActiveState':'activating','phase':'preparing'} if self.preparing else {'ActiveState':'active'}
        if action=='stop':
            self.stopped.append(identifier)
            if self.clean:self.sessions=[s for s in self.sessions if s['id']!=identifier]
            return {'receipt':{'disk_removed':self.clean,'cgroup_removed':self.clean,'account_removed':self.clean}}


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'state.json'
        self.github=GitHub();self.engine=Engine();self.config={'repositories':[REPO],'controller_id':'test','max_sessions':1}
        self.subject=broker.Broker(self.config,self.path,self.github,self.engine)
    def tearDown(self):self.tmp.cleanup()
    def test_admission_is_allowlisted_and_label_constrained(self):
        for labels in [['ubuntu-latest'],[LABEL,'privileged'],['self-hosted']]:
            self.assertFalse(self.subject.eligible({'status':'queued','labels':labels}))
        self.subject.tick();self.assertEqual(self.github.created,1)
        self.assertNotIn('SENSITIVE_JIT',self.path.read_text())
        self.subject.tick();self.assertEqual(self.github.created,1)
    def test_restart_adopts_session_after_lost_start_response(self):
        self.engine.fail_after_start=True
        with self.assertRaises(RuntimeError):self.subject.tick()
        restarted=broker.Broker(self.config,self.path,self.github,self.engine)
        restarted.tick()
        self.assertEqual(self.github.created,1);self.assertEqual(len(restarted.state['sessions']),1)
    def test_ambiguous_registration_is_removed_not_blindly_duplicated(self):
        self.github.fail_response=True
        with self.assertRaises(broker.APIError):self.subject.tick()
        self.github.jobs=[]
        broker.Broker(self.config,self.path,self.github,self.engine).tick()
        self.assertEqual(self.github.deleted,[1]);self.assertEqual(self.github.created,1)
    def test_actual_assignment_not_queued_candidate_owns_cancellation(self):
        self.subject.tick();self.github.jobs[0].update(id=99,runner_id=1,status='in_progress')
        self.subject.tick();entry=next(iter(self.subject.state['sessions'].values()))
        identifier=entry['session_id']
        self.assertEqual(entry['job_id'],99)
        self.github.jobs[0]['status']='completed'
        self.subject.tick();self.assertEqual(self.engine.stopped,[identifier]);self.assertEqual(self.github.deleted,[1])
    def test_failed_cleanup_never_frees_admission_slot(self):
        self.subject.tick();self.github.jobs[0].update(runner_id=1,status='completed');self.engine.clean=False
        with self.assertRaises(RuntimeError):self.subject.tick()
        self.assertEqual(len(self.subject.state['sessions']),1);self.assertEqual(self.github.deleted,[])
    def test_paper_admission_reserves_capacity_against_another_job(self):
        paper='bme-isolated-paper-v1'
        self.config.update(profiles={LABEL:8,paper:20},max_sessions=2,disk_budget_gib=20)
        self.github.jobs=[dict(self.github.jobs[0],labels=[paper]),dict(self.github.jobs[0],id=5)]
        subject=broker.Broker(self.config,self.path,self.github,self.engine)
        subject.tick();subject.tick()
        self.assertEqual(self.github.created,1)
        self.assertEqual(self.engine.sessions[0]['disk_gib'],20)
        self.path.unlink()
        restarted=broker.Broker(self.config,self.path,self.github,self.engine);restarted.tick()
        self.assertEqual(self.github.created,1)
        self.assertEqual(next(iter(restarted.state['sessions'].values()))['profile'],paper)

    def test_idle_timeout_starts_after_long_preparation_and_survives_restart(self):
        with patch.object(broker.time,'time',return_value=1000):self.subject.tick()
        identifier=next(iter(self.subject.state['sessions'].values()))['session_id']
        self.engine.preparing=True
        with patch.object(broker.time,'time',return_value=1500):self.subject.tick()
        self.assertNotIn('idle_since',next(iter(self.subject.state['sessions'].values())))
        self.engine.preparing=False
        with patch.object(broker.time,'time',return_value=1501):self.subject.tick()
        self.assertEqual(self.engine.stopped,[])
        self.assertEqual(self.github.created,1)
        restarted=broker.Broker(self.config,self.path,self.github,self.engine)
        self.assertEqual(next(iter(restarted.state['sessions'].values()))['idle_since'],1501)
        with patch.object(broker.time,'time',return_value=1670):restarted.tick()
        self.assertEqual(self.engine.stopped,[])
        again=broker.Broker(self.config,self.path,self.github,self.engine)
        self.assertEqual(next(iter(again.state['sessions'].values()))['idle_since'],1501)
        with patch.object(broker.time,'time',return_value=1682):again.tick()
        self.assertEqual(self.engine.stopped,[identifier])
        self.assertEqual(self.github.deleted,[1]);self.assertEqual(self.github.created,2)


if __name__=='__main__':unittest.main()
