import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'session'))
import session
import broker
from test_broker import GitHub, REPO


class StartReservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        for name in ['operations','sessions','receipts','disks','credentials']:
            (self.root/name).mkdir()
        self.root_patch=patch.object(session,'ROOT',self.root);self.root_patch.start()
        self.disk_patch=patch.object(session.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3));self.disk_patch.start()
        self.addCleanup(self.tmp.cleanup);self.addCleanup(self.root_patch.stop);self.addCleanup(self.disk_patch.stop)
        self.data={'repo':REPO,'runner_id':1,'label':'bme-auto-test-one','jit':'c2VjcmV0'}
        self.identifier='e'*32

    def reserve(self,identifier=None,disk_gib=8):
        with session.control_lock():
            return session.reserve(identifier or self.identifier,self.data,2700,disk_gib)

    def test_private_controller_umask_keeps_public_bootstrap_readable(self):
        self.reserve()
        code=self.root/'code';code.mkdir();(code/'worker.py').write_text('fixture')
        runtime=self.root/'runtime';runtime.mkdir()
        (self.root/'run').mkdir();(self.root/'lib').mkdir()
        def paths(value,*parts):
            return Path({'/run':self.root/'run','/var/lib':self.root/'lib'}.get(str(value),value),*parts)
        old=os.umask(0o077)
        try:
            with patch.object(session,'CODE',code),patch.object(session,'Path',side_effect=paths), \
                 patch.object(session,'run',return_value=SimpleNamespace(stdout='[]')):
                session.start(self.data,2700,{'rootfs':str(runtime)},identifier=self.identifier)
        finally:os.umask(old)
        control=self.root/'run'/('tdk-control-'+self.identifier)
        for path in [control,runtime/'infra',runtime/'infra/scripts']:
            self.assertEqual(path.stat().st_mode & 0o777,0o755)
        for name in ['metadata.json','policy.json']:
            path=control/name
            self.assertEqual(path.stat().st_mode & 0o777,0o644)
            self.assertNotIn(self.data['jit'],path.read_text())
        self.assertEqual((self.root/'sessions'/(self.identifier+'.json')).stat().st_mode & 0o777,0o600)

    def test_pending_preparation_is_durable_visible_and_reserves_capacity(self):
        self.reserve(disk_gib=20)
        pending=session.inventory()
        self.assertEqual(pending[0]['phase'],'preparing')
        self.assertEqual(pending[0]['id'],self.identifier)
        self.assertNotIn('jit',pending[0])
        with self.assertRaisesRegex(RuntimeError,'disk budget'):self.reserve('f'*32)
        with self.assertRaisesRegex(RuntimeError,'already exists'):self.reserve()

    def test_root_slot_limit_counts_pending_starts(self):
        self.reserve();self.reserve('f'*32)
        with self.assertRaisesRegex(RuntimeError,'slots'):self.reserve('d'*32)

    def test_stop_before_request_arrives_prevents_late_start(self):
        with session.control_lock():result=session.cancel(self.identifier)
        self.assertTrue(all(result['receipt'][key] for key in ('disk_removed','cgroup_removed','account_removed')))
        with self.assertRaisesRegex(RuntimeError,'already exists'):self.reserve()
        self.assertEqual(session.inventory(),[])

    def test_cancel_during_real_interleaved_preparation_prevents_allocation(self):
        ready=threading.Event();resume=threading.Event();errors=[]
        def prepare():
            ready.set()
            if not resume.wait(5):raise RuntimeError('test did not resume preparation')
            return {}
        def launch():
            try:session.launch(self.identifier,self.data,2700,8)
            except Exception as error:errors.append(error)
        with patch.object(session,'prepare',side_effect=prepare),patch.object(session,'run') as host:
            worker=threading.Thread(target=launch)
            worker.start()
            try:
                self.assertTrue(ready.wait(5))
                self.assertEqual(session.status(self.identifier)['phase'],'preparing')
                with session.control_lock():session.cancel(self.identifier)
                self.reserve('f'*32)
            finally:
                resume.set();worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(errors),1)
            self.assertIn('no longer active',str(errors[0]))
            host.assert_not_called()
        self.assertEqual([x['id'] for x in session.inventory()],['f'*32])

    def test_root_deadline_closes_abandoned_preparation(self):
        operation=self.reserve()
        with patch.object(session.time,'time',return_value=operation['preparation_deadline']+1),session.control_lock():
            session.reap()
        self.assertEqual(session.inventory(),[])
        with self.assertRaisesRegex(RuntimeError,'no longer active'):
            session.start(self.data,2700,{},identifier=self.identifier)

    def test_sparse_disks_and_pending_disks_reserve_their_full_capacity(self):
        self.reserve()
        disk=self.root/'disks'/self.identifier
        with disk.open('wb') as out:out.truncate(8*1024**3)
        self.assertLess(disk.stat().st_blocks*512,1024**3)
        with patch.object(session.shutil,'disk_usage',return_value=SimpleNamespace(free=19*1024**3)):
            with self.assertRaisesRegex(RuntimeError,'reserved disk'):self.reserve('f'*32)

    def test_capacity_is_rechecked_after_image_preparation(self):
        self.reserve()
        with patch.object(session.shutil,'disk_usage',return_value=SimpleNamespace(free=11*1024**3)),patch.object(session,'run') as host:
            with self.assertRaisesRegex(RuntimeError,'reserved disk'):
                session.start(self.data,2700,{},identifier=self.identifier)
            host.assert_not_called()

    def test_unrecorded_resources_cannot_produce_successful_cleanup_receipt(self):
        (self.root/'disks'/self.identifier).write_bytes(b'leftover')
        with session.control_lock(),self.assertRaisesRegex(RuntimeError,'unrecorded job resources'):
            session.cancel(self.identifier)
        self.assertFalse((self.root/'receipts'/(self.identifier+'.json')).exists())

    def test_broker_restart_preserves_pending_host_reservation(self):
        host=self
        class Engine:
            def call(self,action,identifier=None,data=None,seconds=None,disk_gib=8,paper=False):
                if action=='list':return session.inventory()
                if action=='start':
                    with session.control_lock():session.reserve(identifier,{**data,'jit':host.data['jit']},seconds,disk_gib)
                    raise RuntimeError('broker interrupted during preparation')
                if action=='status':return session.status(identifier)
                if action=='stop':
                    with session.control_lock():return session.cancel(identifier)
        config={'repositories':[REPO],'controller_id':'test','max_sessions':1}
        github=GitHub();state=self.root/'broker.json'
        subject=broker.Broker(config,state,github,Engine())
        with self.assertRaisesRegex(RuntimeError,'interrupted'):subject.tick()
        entry=next(iter(json.loads(state.read_text())['sessions'].values()))
        self.assertEqual(entry['session_id'],session.inventory()[0]['id'])
        restarted=broker.Broker(config,state,github,Engine());restarted.tick()
        self.assertEqual(github.created,1)
        self.assertEqual(len(session.inventory()),1)
        self.assertEqual(github.deleted,[])

    def test_broker_cancels_delayed_request_before_releasing_slot(self):
        host=self
        class DelayedEngine:
            def __init__(self):self.delayed=None;self.success=[]
            def call(self,action,identifier=None,data=None,seconds=None,disk_gib=8,paper=False):
                if action=='list':return session.inventory()
                if action=='start':
                    data={**data,'jit':host.data['jit']}
                    if self.delayed is None:
                        self.delayed=(identifier,data,seconds,disk_gib)
                        raise RuntimeError('request still in transit')
                    with session.control_lock():result=session.reserve(identifier,data,seconds,disk_gib)
                    self.success.append(identifier);return result
                if action=='stop':
                    with session.control_lock():return session.cancel(identifier)
                if action=='status':return session.status(identifier)
        config={'repositories':[REPO],'controller_id':'test','max_sessions':1}
        github=GitHub();state=self.root/'broker.json';engine=DelayedEngine()
        with self.assertRaisesRegex(RuntimeError,'transit'):broker.Broker(config,state,github,engine).tick()
        broker.Broker(config,state,github,engine).tick()
        old_id,data,seconds,disk=engine.delayed
        with session.control_lock(),self.assertRaisesRegex(RuntimeError,'already exists'):
            session.reserve(old_id,data,seconds,disk)
        self.assertEqual(len(session.inventory()),1)
        self.assertEqual(github.deleted,[1])
        self.assertEqual(github.created,2)


if __name__=='__main__':unittest.main()
