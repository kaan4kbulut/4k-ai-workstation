#!/usr/bin/env node
// npm betiklerinden uv'yi platform bağımsız çağırır (~/.local/bin/uv PATH'te olmasa bile).
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const exe = process.platform === 'win32' ? 'uv.exe' : 'uv';
const candidates = [path.join(os.homedir(), '.local', 'bin', exe), path.join(os.homedir(), '.cargo', 'bin', exe)];
const uv = candidates.find((p) => fs.existsSync(p)) || 'uv';

const r = spawnSync(uv, process.argv.slice(2), { stdio: 'inherit', cwd: path.join(__dirname, '..') });
if (r.error) {
  console.error(`uv çalıştırılamadı (${r.error.message}). Kurulum: https://docs.astral.sh/uv/getting-started/installation/`);
  process.exit(1);
}
process.exit(r.status ?? 1);
