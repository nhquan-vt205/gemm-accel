#!/usr/bin/env python3
"""Run <TB> <TC> [NAME=value ...] lists; persist logs and replay reports."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
SIMDIR = ROOT / 'src/sim'


def report(data):
    rows = [('PATTERN', 'SIM', 'SEED', 'RESULT')]
    for r in data['results']:
        tc = Path(r['tc'])
        pattern = f'{tc.parent.name}-{tc.name}' if tc.parent.name else tc.name
        rows.append((pattern, data['sim'], str(r['seed']), r['status']))
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    def format_row(row):
        return ' | '.join(value.ljust(width) for value, width in zip(row, widths)).rstrip()
    lines = [format_row(rows[0]), '-+-'.join('-' * width for width in widths)]
    lines.extend(format_row(row) for row in rows[1:])
    counts = {s: sum(r['status'] == s for r in data['results'])
              for s in ('PASS', 'FAIL', 'ERROR', 'TIMEOUT', 'NOT_RUN')}
    lines.append('TOTAL=%d  ' % len(data['results']) +
                 '  '.join(f'{s}={n}' for s, n in counts.items()))
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('list', nargs='?', type=Path)
    ap.add_argument('--sim', choices=['questa', 'verilator'], default=os.getenv('SIM', 'questa'))
    ap.add_argument('--seeds', default='1')
    ap.add_argument('--timeout', type=float, default=300,
                    help='wall-clock seconds per test, compile included')
    ap.add_argument('--report', type=Path, help='replay a run directory or results.json')
    ap.add_argument('--var', action='append', default=[], help='extra Make NAME=value, repeatable')
    args = ap.parse_args()
    if args.report:
        path = args.report / 'results.json' if args.report.is_dir() else args.report
        try:
            data = json.loads(path.read_text())
            print(report(data), end='')
            return int(any(r['status'] != 'PASS' for r in data['results']))
        except (OSError, ValueError, KeyError) as e:
            ap.error(str(e))
    if not args.list or args.timeout <= 0:
        ap.error('provide a list and --timeout > 0')
    try:
        seeds = [str(int(s)) for s in args.seeds.split(',')]
        if any(int(s) < 1 for s in seeds):
            raise ValueError('seeds must be positive')
        jobs = []
        for number, line in enumerate(args.list.read_text().splitlines(), 1):
            if line.lstrip().startswith('//'):
                continue
            tok = shlex.split(line, comments=True)
            if not tok:
                continue
            if len(tok) < 2:
                raise ValueError(f'line {number}: expected TB TC [NAME=value ...]')
            extra = args.var + tok[2:]
            for v in extra:
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', v):
                    raise ValueError(f'line {number}: invalid Make assignment {v!r}')
                if v.split('=', 1)[0] in ('TB', 'TC', 'SIM', 'SEED'):
                    raise ValueError(f'line {number}: TB/TC/SIM/SEED must use their dedicated fields')
            for seed in seeds:
                jobs.append(dict(tb=tok[0], tc=tok[1], seed=seed, extra=extra))
        if not jobs:
            raise ValueError('empty pattern list: no tests to run')
    except (OSError, ValueError) as e:
        ap.error(str(e))

    run = SIMDIR / 'out/regress' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    (run / 'logs').mkdir(parents=True)
    (run / 'pat.list').write_text(args.list.read_text())
    data = dict(sim=args.sim, list=str(args.list.resolve()),
                started=datetime.now().isoformat(), results=[])
    for i, job in enumerate(jobs, 1):
        data['results'].append(dict(**job, status='NOT_RUN', note='not started',
                                    seconds=0, log=str(run / 'logs' / f'{i:04d}.log')))

    def save():
        temp = run / 'results.tmp'
        temp.write_text(json.dumps(data, indent=2) + '\n')
        temp.replace(run / 'results.json')
        (run / 'report.txt').write_text(report(data))

    save()
    print(f'Report directory: {run}', flush=True)
    for r in data['results']:
        cmd = ['make', '-s', '-C', str(SIMDIR), 'sim', f'SIM={args.sim}',
               f"TB={r['tb']}", f"TC={r['tc']}", f"SEED={r['seed']}"] + r['extra']
        r['command'] = cmd
        tc = Path(r['tc'])
        pattern = f'{tc.parent.name}-{tc.name}' if tc.parent.name else tc.name
        print(f"[TC] {pattern} (seed={r['seed']})", flush=True)
        start = time.monotonic()
        with open(r['log'], 'w') as log:
            try:
                # New session lets timeout terminate make and simulator descendants.
                p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    r['returncode'] = p.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    import signal
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait()
                    r.update(status='TIMEOUT', note='runner wall-clock timeout')
                except KeyboardInterrupt:
                    import signal
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait()
                    r.update(status='ERROR', note='interrupted')
                    r['seconds'] = time.monotonic() - start
                    save()
                    return 130
            except OSError as e:
                r.update(status='ERROR', note=str(e))
        r['seconds'] = time.monotonic() - start
        if r['status'] == 'NOT_RUN':
            out = Path(r['log']).read_text(errors='replace')
            # Anchored markers: do not treat a compiler's source echo as a result.
            markers = re.findall(r'^\s*(?:#\s*)?TEST (PASSED|FAILED)\b([^\n]*)', out, re.M)
            if re.search(r'^\s*(?:#\s*)?TEST FAILED:[^\n]*TIMEOUT', out, re.M):
                r.update(status='TIMEOUT', note='TB watchdog timeout')
            elif any(m[0] == 'FAILED' for m in markers):
                r.update(status='FAIL', note=next(m[1].strip(': ') for m in markers if m[0] == 'FAILED'))
            elif r['returncode'] == 0 and any(m[0] == 'PASSED' for m in markers):
                r.update(status='PASS', note='test completed')
            else:
                r.update(status='ERROR', note=f"build/simulator failed or missing result (exit={r['returncode']})")
        save()
        print(f"| {r['status']}", flush=True)
    print(report(data), end='')
    return int(any(r['status'] != 'PASS' for r in data['results']))


if __name__ == '__main__':
    raise SystemExit(main())
