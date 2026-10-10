"""Local SSH -> kubectl exec bridge. JSON stdin prevents shell interpolation of strategy text."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


def run(argv, data=None, timeout=180):
    result = subprocess.run(argv, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        # Never return raw remote errors: they may include URLs or private connection details.
        raise RuntimeError('Remote command failed (exit %s); inspect sanitized server logs' % result.returncode)
    return result.stdout


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['health', 'install', 'submit', 'result'])
    p.add_argument('--config', required=True)
    p.add_argument('--bundle')
    p.add_argument('--version', type=int)
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding='utf-8'))
    for name in ['host', 'user', 'namespace', 'service_id']:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', cfg[name]):
            raise ValueError('Invalid connection field: ' + name)
    root = cfg['remote_root']
    if not root.startswith('/home/node/.openclaw/') or '..' in root.split('/'):
        raise ValueError('Unexpected remote root')
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes']
    if cfg.get('identity_file'):
        ssh += ['-i', str(Path(cfg['identity_file']).expanduser())]
    ssh += [cfg['user'] + '@' + cfg['host']]
    def remote(argv, data=None):
        return run(ssh + [shlex.join(argv)], data)
    pods = json.loads(remote(['kubectl', 'get', 'pods', '-n', cfg['namespace'], '-o', 'json']))['items']
    prefix = 'service-' + cfg['service_id'] + '-'
    ready = [x['metadata']['name'] for x in pods if x['metadata']['name'].startswith(prefix)
             and x['status'].get('phase') == 'Running' and not x['metadata'].get('deletionTimestamp')
             and any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in x['status'].get('conditions', []))]
    if len(ready) != 1:
        raise RuntimeError('Expected exactly one Ready service pod; found %s' % len(ready))
    base = ['kubectl', 'exec', '-i', '-n', cfg['namespace'], ready[0]]
    if cfg.get('container'):
        base += ['-c', cfg['container']]
    base += ['--']
    target = root + '/codex_submit.py'
    if a.action == 'install':
        script = Path(__file__).with_name('submit_candidate.py').read_bytes()
        installer = 'import sys,pathlib,os;p=pathlib.Path(sys.argv[1]);t=p.with_suffix(".installing");t.write_bytes(sys.stdin.buffer.read());os.replace(t,p)'
        remote(base + ['python3', '-c', installer, target], script)
        helper = Path(__file__).with_name('candidate_validation.py').read_bytes()
        remote(base + ['python3', '-c', installer, root + '/candidate_validation.py'], helper)
        # Existing replay adapter must preserve variant lineage, rather than relabeling it.
        patcher = '''import pathlib,sys
p=pathlib.Path(sys.argv[1])/"lab_records.py"
s=p.read_text()
old="'research_mode':'reproduction','review_status':"
new="'research_mode':meta.get('research_mode','reproduction'),'parent_version':str(meta['parent_version']) if meta.get('parent_version') else None,'review_status':"
if old in s:
 b=p.with_suffix('.py.pre_codex');
 if not b.exists(): b.write_text(s)
 p.write_text(s.replace(old,new))
elif new not in s: raise RuntimeError('Unknown candidate adapter; review manually')
'''
        remote(base + ['python3', '-c', patcher, root])
        print(json.dumps({'installed': True, 'pod': ready[0]}))
    elif a.action == 'submit':
        if not a.bundle:
            p.error('--bundle required')
        data = Path(a.bundle).read_bytes()
        json.loads(data)
        cmd = base + ['python3', target, '--root', root]
        if a.dry_run:
            cmd += ['--dry-run']
        print(remote(cmd, data).decode())
    elif a.action == 'health':
        print(remote(base + ['python3', root + '/lab_runtime.py', 'health']).decode())
    else:
        if a.version is None or a.version < 1:
            p.error('--version must be a positive integer')
        reader = 'import sys,pathlib;p=pathlib.Path(sys.argv[1]);print(p.read_text() if p.exists() else "RESULT_PENDING")'
        print(remote(base + ['python3', '-c', reader, root + '/pytest/research_results/' + str(a.version) + '.json']).decode())


if __name__ == '__main__':
    main()
