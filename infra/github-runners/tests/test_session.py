import asyncio
import contextlib
import io
import ipaddress
import json
import os
from pathlib import Path
import pwd
import socket
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

SESSION=Path(__file__).resolve().parents[1]/'session'
sys.path.insert(0,str(SESSION))
import image
import proxy
import hook
import paper


class PolicyTests(unittest.TestCase):
    def test_offline_namespace_is_selected_before_container_identity_mapping(self):
        meta={'rootfs':'/fixture','process':{},'reference':'fixture:latest','digest':'sha256:'+'a'*64,'resolved_at':1}
        for offline in (False,True):
            args={'environmentVariables':{'TDK_NETWORK_NONE':'1'} if offline else {}}
            with patch.object(hook.subprocess,'run') as execute:
                hook.container(meta,args,['true'])
            argv=execute.call_args.args[0]
            self.assertIn('--unshare-all',argv)
            self.assertEqual('--share-net' in argv,not offline)
            self.assertIn('--cap-drop',argv)

    def test_allowlist_requires_label_boundary(self):
        for name in ['github.com','api.github.com','foo.actions.githubusercontent.com','ghcr.io']:
            self.assertTrue(proxy.allowed_host(name),name)
        for name in ['github.com.evil.org','evilgithub.com','169.254.169.254','localhost','github.com:443','github.com\r\nX:y','github..com']:
            self.assertFalse(proxy.allowed_host(name),name)

    def test_numeric_checks_block_metadata_private_and_host_subnets(self):
        denied=[ipaddress.ip_network('8.8.8.0/24'),ipaddress.ip_network('2606:4700::/32')]
        for address in ['127.0.0.1','10.9.0.25','169.254.169.254','::1','fe80::1','::ffff:127.0.0.1','8.8.8.8','2606:4700::1111']:
            self.assertFalse(proxy.allowed_ip(address,denied),address)
        self.assertTrue(proxy.allowed_ip('1.1.1.1',denied))

    def test_unsupported_container_features_fail_closed(self):
        for key,value in [('createOptions','--privileged'),('userMountVolumes',[{}]),('registry',{'password':'x'}),
                          ('portMappings',{'22':'22'}),('dockerfile','Dockerfile')]:
            with self.subTest(key=key),self.assertRaises(ValueError):hook.restrictions({key:value})


class BootstrapTests(unittest.TestCase):
    def test_paper_translation_uses_the_actual_shared_recipe(self):
        path=SESSION.parents[2]/'scripts/ci/paper.Dockerfile'
        self.assertEqual(paper.recipe(path)[-2:],['pymupdf','jsonschema'])
        with tempfile.TemporaryDirectory() as tmp:
            changed=Path(tmp)/'Dockerfile'
            changed.write_text(path.read_text()+'RUN echo unsupported\n')
            with self.assertRaises(ValueError):paper.recipe(changed)

    def test_cold_image_progress_does_not_corrupt_lifecycle_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);digest='sha256:'+('a'*64)
            def operation(argv, **kwargs):
                print('image preparation progress',file=kwargs.get('stdout',sys.stdout))
                if argv[0]=='umoci':
                    runner=base/('a'*64)/'bundle/rootfs/home/runner'
                    runner.mkdir(parents=True)
                    (runner/'run.sh').write_text('fixture')
            output=io.StringIO();errors=io.StringIO()
            with patch.object(image,'BASE',base),patch.object(image.os,'geteuid',return_value=0), \
                 patch.object(image.subprocess,'check_output',return_value=json.dumps({'Digest':digest})), \
                 patch.object(image.subprocess,'run',side_effect=operation), \
                 contextlib.redirect_stdout(output),contextlib.redirect_stderr(errors):
                print(json.dumps(image.prepare()))
            self.assertEqual(json.loads(output.getvalue())['digest'],digest)
            self.assertIn('image preparation progress',errors.getvalue())


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory();self.path=str(Path(self.directory.name)/'proxy')
        self.server=asyncio.create_task(proxy.serve(self.path,pwd.getpwuid(os.getuid()).pw_name,[]))
        for _ in range(100):
            if Path(self.path).exists():break
            await asyncio.sleep(.01)

    async def asyncTearDown(self):
        self.server.cancel()
        try:await self.server
        except asyncio.CancelledError:pass
        self.directory.cleanup()

    async def request(self,header):
        reader,writer=await asyncio.open_unix_connection(self.path)
        writer.write(header);await writer.drain()
        result=await asyncio.wait_for(reader.read(1024),2)
        writer.close();await writer.wait_closed();return result

    async def test_private_dns_answer_never_dialed(self):
        answer=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('169.254.169.254',443))]
        with patch.object(asyncio.get_running_loop(),'getaddrinfo',AsyncMock(return_value=answer)),patch.object(asyncio,'open_connection',AsyncMock()) as dial:
            response=await self.request(b'CONNECT github.com:443 HTTP/1.1\r\n\r\n')
            self.assertIn(b'403',response);dial.assert_not_called()

    async def test_dial_uses_validated_numeric_address_not_second_dns(self):
        answer=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('1.1.1.1',443))]
        with patch.object(asyncio.get_running_loop(),'getaddrinfo',AsyncMock(return_value=answer)),patch.object(asyncio,'open_connection',AsyncMock(side_effect=OSError)) as dial:
            await self.request(b'CONNECT github.com:443 HTTP/1.1\r\n\r\n')
            dial.assert_awaited_once_with('1.1.1.1',443)

    async def test_wrong_peer_uid_denied_before_dns(self):
        with patch.object(proxy.pwd,'getpwnam',return_value=type('User',(),{'pw_uid':os.getuid()+1})()),patch.object(asyncio.get_running_loop(),'getaddrinfo',AsyncMock()) as dns:
            self.assertIn(b'403',await self.request(b'CONNECT github.com:443 HTTP/1.1\r\n\r\n'))
            dns.assert_not_called()

    async def test_plain_http_and_wrong_ports_are_rejected(self):
        for header in [b'GET http://github.com/ HTTP/1.1\r\n\r\n',b'CONNECT github.com:22 HTTP/1.1\r\n\r\n']:
            self.assertIn(b'403',await self.request(header))


if __name__=='__main__':unittest.main()
