// scripts/metrics.mjs — in { "<metric>": <số> } cho MCA. Chỉ số tổng hợp, không có tên khách hay đường dẫn.
// Daemon của MCA chạy script này mỗi ngày (nguồn `cmd`, tối đa 2 phút). KHÔNG để token/khoá trong script.
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const core = path.join(root, 'packages', 'core');
const venvPython = process.platform === 'win32' ? path.join(core, '.venv', 'Scripts', 'python.exe') : path.join(core, '.venv', 'bin', 'python');
const python = process.env.CADGUARD_PYTHON || (existsSync(venvPython) ? venvPython : process.platform === 'win32' ? 'python' : 'python3');

try {
  const out = execFileSync(python, ['-m', 'cadguard', 'stats', '--json'], { cwd: core, encoding: 'utf8', timeout: 60_000 });
  const stats = JSON.parse(out); // ví dụ: { rules_implemented: 16, drawings_audited_7d: 0 }
  process.stdout.write(JSON.stringify(stats));
} catch (err) {
  // Chưa cài lõi: báo 0 thay vì làm hỏng lần thu (nguồn lỗi 3 ngày liên tiếp mới thành cảnh báo).
  process.stdout.write(JSON.stringify({ rules_implemented: 0 }));
}
