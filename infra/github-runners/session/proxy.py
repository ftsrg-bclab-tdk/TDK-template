#!/usr/bin/env python3
"""Per-session HTTPS CONNECT relay: domain and numeric-address checks before connect."""
import argparse
import asyncio
import ipaddress
import json
import os
import pwd
import re
import socket
import struct
from pathlib import Path

# Suffix entries match a DNS label boundary, not arbitrary string suffixes.
DOMAINS = ('github.com', 'api.github.com', 'codeload.github.com', 'githubusercontent.com',
           'actions.githubusercontent.com', 'blob.core.windows.net', 'ghcr.io',
           'pkg-containers.githubusercontent.com', 'docker.io', 'docker.com',
           'cloudflare.docker.com', 'production.cloudflare.docker.com',
           'production.cloudfront.docker.com', 'registry.npmjs.org', 'pypi.org',
           'files.pythonhosted.org', 'archive.ubuntu.com', 'security.ubuntu.com')


def allowed_host(host):
    if not re.fullmatch(r'[a-z0-9.-]{1,253}', host) or '..' in host:
        return False
    return any(host == domain or host.endswith('.' + domain) for domain in DOMAINS)


def allowed_ip(address, denied):
    ip = ipaddress.ip_address(address)
    return ip.is_global and not any(ip in net for net in denied if ip.version == net.version)


async def serve(path, username, denied):
    semaphore = asyncio.Semaphore(48)

    async def client(reader, writer):
        upstream = None
        try:
            peer = writer.get_extra_info('socket').getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            _, uid, _ = struct.unpack('3i', peer)
            if uid != pwd.getpwnam(username).pw_uid:
                raise ValueError('wrong session UID')
            async with semaphore:
                raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)
                if len(raw) > 8192:
                    raise ValueError('header too large')
                request = raw.split(b'\r\n', 1)[0].decode('ascii').split(' ')
                if len(request) != 3 or request[0] != 'CONNECT' or request[2] != 'HTTP/1.1':
                    raise ValueError('CONNECT required')
                host, port = request[1].rsplit(':', 1)
                host = host.lower()
                if port != '443' or not allowed_host(host):
                    raise ValueError('destination denied')
                answers = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(
                    host, 443, type=socket.SOCK_STREAM), 10)
                ips = list(dict.fromkeys(answer[4][0] for answer in answers))
                if not ips or not all(allowed_ip(ip, denied) for ip in ips):
                    raise ValueError('address denied')
                # Connect a checked literal, never resolve the name a second time.
                for ip in ips:
                    try:
                        incoming, upstream = await asyncio.wait_for(asyncio.open_connection(ip, 443), 10)
                        break
                    except OSError:
                        continue
                if upstream is None:
                    raise ValueError('upstream unavailable')
                writer.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
                await writer.drain()

                async def pump(source, target):
                    while data := await source.read(65536):
                        target.write(data)
                        await target.drain()
                tasks = [asyncio.create_task(pump(reader, upstream)),
                         asyncio.create_task(pump(incoming, writer))]
                done, pending = await asyncio.wait(tasks, timeout=3600, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except (ValueError, KeyError, OSError, asyncio.TimeoutError, asyncio.IncompleteReadError,
                asyncio.LimitOverrunError, UnicodeError):
            writer.write(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
        finally:
            writer.close()
            if upstream:
                upstream.close()

    server = await asyncio.start_unix_server(client, path=path, limit=8192)
    os.chmod(path, 0o666)  # SO_PEERCRED admits only this session's dynamic UID.
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('socket')
    parser.add_argument('user')
    parser.add_argument('policy')
    args = parser.parse_args()
    denied = [ipaddress.ip_network(x) for x in json.loads(Path(args.policy).read_text())]
    asyncio.run(serve(args.socket, args.user, denied))
