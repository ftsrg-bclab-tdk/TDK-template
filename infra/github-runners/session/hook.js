'use strict';
// This adapter is a compatibility layer inside the outer job sandbox, not a boundary.
const {spawnSync} = require('node:child_process');
const result = spawnSync('/infra/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2', [
  '--library-path', '/infra/usr/lib/x86_64-linux-gnu', '/infra/usr/bin/python3',
  '/infra/scripts/hook.py'
], {stdio: 'inherit', env: {...process.env, PYTHONHOME: '/infra/usr'}});
if (result.error) console.error('Container hook could not start.');
process.exit(result.status === null ? 1 : result.status);
