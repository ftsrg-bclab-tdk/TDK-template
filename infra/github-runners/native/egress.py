#!/usr/bin/env python3
"""Restrict only the tdk-ci UID to public HTTPS and the host DNS stub."""
import argparse
import ipaddress
import json
import os
import pwd
import subprocess

TABLE = 'tdk_ci_egress'


def rules(uid, interfaces):
    v4 = {'0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
          '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16', '198.18.0.0/15',
          '224.0.0.0/4', '240.0.0.0/4'}
    v6 = {'::/128', '::1/128', 'fc00::/7', 'fe80::/10', 'ff00::/8'}
    for interface in interfaces:
        for address in interface.get('addr_info', []):
            net = ipaddress.ip_interface(f"{address['local']}/{address['prefixlen']}").network
            (v4 if net.version == 4 else v6).add(str(net))
    return f'''table inet {TABLE} {{
  chain output {{
    type filter hook output priority 10; policy accept;
    meta skuid {uid} jump restricted
  }}
  chain restricted {{
    ct state established,related accept
    ip daddr {{ 127.0.0.53, 127.0.0.54 }} udp dport 53 accept
    ip daddr {{ 127.0.0.53, 127.0.0.54 }} tcp dport 53 accept
    ip daddr {{ {', '.join(sorted(v4))} }} counter reject
    ip6 daddr {{ {', '.join(sorted(v6))} }} counter reject
    tcp dport 443 accept
    counter reject
  }}
}}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('root required')
    exists = subprocess.run(['nft', 'list', 'table', 'inet', TABLE],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if args.remove:
        if not args.apply:
            print('Would delete only table inet ' + TABLE)
        elif exists:
            subprocess.run(['nft', 'delete', 'table', 'inet', TABLE], check=True)
        return
    interfaces = json.loads(subprocess.check_output(['ip', '-j', 'address'], text=True))
    script = ('delete table inet ' + TABLE + '\n' if exists else '') + rules(pwd.getpwnam('tdk-ci').pw_uid, interfaces)
    if not args.apply:
        print(script)
        return
    # Check, then replace only our table in one atomic nft transaction.
    subprocess.run(['nft', '--check', '-f', '-'], input=script, text=True, check=True)
    subprocess.run(['nft', '-f', '-'], input=script, text=True, check=True)


if __name__ == '__main__':
    main()
