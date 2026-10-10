"""Bounded read-only Android health sampling through an already connected private ADB server; not UI acceptance."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

SERVICES = ('surfaceflinger', 'system_server', 'adbd', 'netd', 'vold', 'nemuinit', 'mediaserver')
COMMAND = "echo uptime=$(cut -d' ' -f1 /proc/uptime)\necho boot=$(getprop sys.boot_completed)\n" + '''for n in surfaceflinger system_server adbd netd vold nemuinit mediaserver; do
 p=$(pidof "$n"); echo "$n=$p"; if [ -n "$p" ]; then p=${p%% *}; echo "$n.state=$(awk '{print $3}' /proc/$p/stat)"; fi
done
if dmesg >/dev/null 2>&1; then
 if dmesg | grep -q 'Kernel panic - not syncing'; then echo panic=1; else echo panic=0; fi
else echo panic=unknown; fi
'''


def parse_health(text):
    pairs = [line.split('=', 1) for line in text.splitlines() if '=' in line]
    fields = dict(pairs)
    if len(fields) != len(pairs): raise ValueError('Duplicate fields')
    allowed = {'uptime', 'boot', 'panic', *SERVICES, *(n + '.state' for n in SERVICES)}
    if set(fields) != allowed or not re.fullmatch(r'\d+\.\d+', fields['uptime']): raise ValueError('Unexpected/missing fields')
    if fields['boot'] != '1' or fields['panic'] != '0': raise ValueError('Boot/panic check failed or unavailable')
    for name in SERVICES:
        if not re.fullmatch(r'[1-9]\d*', fields[name]) or fields[name + '.state'] not in ('R', 'S'):
            raise ValueError('Missing, ambiguous, stopped or blocked core service')
    return {'uptime': float(fields['uptime']), 'core_pids': {n: fields[n] for n in SERVICES},
            'core_states': {n: fields[n + '.state'] for n in SERVICES}, 'panic': False}


def observe(args):
    root = Path.cwd().resolve(); adb = Path(args.adb).resolve(); home = Path(args.adb_home).resolve(); output = Path(args.output_dir).resolve()
    if not adb.is_relative_to(root) or not home.is_relative_to(root) or not output.is_relative_to(root) or output.is_relative_to(Path(__file__).resolve().parents[1]) or output.exists() or output == root:
        raise ValueError('Use a workspace ADB, private home and NEW workspace output directory')
    if not home.is_dir() or home.stat().st_uid != os.getuid() or home.stat().st_mode & 0o077:
        raise ValueError('ADB home must be owned by you and mode700')
    if not re.fullmatch(r'[0-9a-f]{64}', args.adb_sha256) or hashlib.sha256(adb.read_bytes()).hexdigest() != args.adb_sha256:
        raise ValueError('ADB input identity mismatch')
    if args.server_port == 5037 or not 0 < args.server_port < 65536 or not 0 < args.guest_port < 65536:
        raise ValueError('Require private server and Guest forwarding ports')
    if not 0 < args.duration_seconds <= 86400 or not 5 <= args.interval_seconds <= 60: raise ValueError('Invalid duration/interval')
    for name in ('tmp', '.android'):
        if not (home / name).resolve().is_relative_to(home): raise ValueError('ADB home symlink escape')
    (home / 'tmp').mkdir(mode=0o700, exist_ok=True)
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LC_ALL': 'C', 'HOME': str(home),
           'ANDROID_USER_HOME': str(home / '.android'), 'TMPDIR': str(home / 'tmp') + '/'}
    output.mkdir(mode=0o700)
    state = {'status': 'RUNNING_HEALTH_ONLY', 'start_time': dt.datetime.now().astimezone().isoformat(),
             'required_seconds': args.duration_seconds, 'samples': [], 'native_input_verified': False,
             'host_identity_and_loaded_memory_verified': False, 'never_launch_stop_or_modify_VM': True}
    start = time.monotonic(); previous = None
    def save():
        p = output / 'status.tmp.json'; p.write_text(json.dumps(state, indent=2) + '\n'); os.chmod(p, 0o600); os.replace(p, output / 'status.json')
    try:
        while True:
            process = subprocess.run([str(adb), '-P', str(args.server_port), '-s', '127.0.0.1:' + str(args.guest_port), 'shell', 'sh'], input=COMMAND, env=env, capture_output=True, text=True, timeout=10)
            if process.returncode: raise RuntimeError('Guest query failed')
            current = parse_health(process.stdout); elapsed = time.monotonic() - start
            if previous and (current['uptime'] < previous['uptime'] or current['core_pids'] != previous['core_pids']): raise ValueError('Guest reboot/core restart')
            if state['samples'] and elapsed - state['samples'][-1]['elapsed_seconds'] > 100: raise ValueError('Observation gap')
            state['samples'].append({'elapsed_seconds': round(elapsed, 3), 'guest': current}); previous = current
            if elapsed >= args.duration_seconds:
                state['status'] = 'BOUNDED_HEALTH_COMPLETE_NATIVE_INPUT_UNVERIFIED'; state['total_seconds'] = round(elapsed, 3)
            save()
            if elapsed >= args.duration_seconds: return
            time.sleep(min(args.interval_seconds, args.duration_seconds - elapsed))
    except Exception as error:
        state['status'] = 'FAIL_OR_INCONCLUSIVE_HEALTH'; state['error_class'] = type(error).__name__; save(); raise


def self_test():
    text = 'uptime=12.3\nboot=1\npanic=0\n' + ''.join(n + '=123\n' + n + '.state=S\n' for n in SERVICES)
    assert parse_health(text)['uptime'] == 12.3
    for bad in (text + 'private=secret\n', text + 'boot=1\n', text.replace('panic=0', 'panic=unknown'), text.replace('vold.state=S', 'vold.state=T'), text.replace('vold=123', 'vold=123 124')):
        try: parse_health(bad)
        except ValueError: pass
        else: raise AssertionError('Uncertain/failing or private health accepted')
    print('PASS strict scalar privacy, duplicate fields, panic availability and core-service health')


if __name__ == '__main__':
    if not __debug__: raise RuntimeError('Do not use python -O')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true'); p.add_argument('--adb'); p.add_argument('--adb-sha256'); p.add_argument('--adb-home'); p.add_argument('--output-dir')
    p.add_argument('--server-port', type=int, default=5061); p.add_argument('--guest-port', type=int); p.add_argument('--duration-seconds', type=int, default=3600); p.add_argument('--interval-seconds', type=int, default=20)
    a = p.parse_args()
    if a.self_test: self_test()
    elif all((a.adb, a.adb_sha256, a.adb_home, a.output_dir, a.guest_port)): observe(a)
    else: p.error('Supply explicit ADB identity, private home/ports and output directory, or --self-test')
