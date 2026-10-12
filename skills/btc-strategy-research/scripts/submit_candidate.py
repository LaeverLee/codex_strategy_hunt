"""Run inside the OpenClaw container; accepts a Codex bundle on stdin. No model calls."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys


def retry_state(root, saved, content_hash, code_hash, backend):
    """Read evidence under both producer and consumer locks; never republish a retry."""
    if saved.get('content_hash') != content_hash:
        raise ValueError('submission_id already belongs to different content')
    version = saved.get('version')
    if type(version) is not int or version < 1:
        raise ValueError('Invalid receipt version')
    found = []
    for folder in ['Strategy', 'Research_Qualified', 'Research_Rejected']:
        path = root / 'pytest' / folder / f'{version}_Strategy_Gold.py'
        side = path.with_suffix('.json')
        if path.exists() or side.exists():
            if not path.exists() or not side.exists():
                raise RuntimeError('Incomplete candidate evidence; reconciliation required')
            meta = json.loads(side.read_text())
            if meta.get('code_hash') != code_hash or hashlib.sha256(path.read_bytes()).hexdigest() != code_hash:
                raise ValueError('Retry candidate hash conflict')
            found.append((folder, meta))
    result = root / 'pytest/research_results' / f'{version}.json'
    rejected = result.with_name(f'{version}.rejected.json')
    terminal = result.exists() or rejected.exists()
    if result.exists() and json.loads(result.read_text()).get('code_hash') != code_hash:
        raise ValueError('Retry result hash conflict')
    rows = backend.request('research_candidates', query=f'?version=eq.{version}&limit=1')
    if rows and rows[0].get('code_hash') != code_hash:
        raise ValueError('Retry DB candidate hash conflict')
    states = backend.request('backtest_version_status', query=f'?version=eq.{version}&limit=1')
    terminal = terminal or any(x.get('status') in {'success', 'tested_failed'} for x in states)
    if len(found) > 1:
        raise RuntimeError('Conflicting queue/archive evidence; reconciliation required')
    if terminal or found and found[0][0] != 'Strategy':
        if found and found[0][0] == 'Strategy':
            raise RuntimeError('Terminal candidate still in queue; reconciliation required')
        return {'submitted': True, 'queued': False, 'queued_this_call': False,
                'current_state': 'completed', 'version': version, 'already_submitted': True}
    if found and found[0][1].get('db_committed') is True and rows:
        return {'submitted': True, 'queued': True, 'queued_this_call': False,
                'current_state': 'queued', 'version': version, 'already_submitted': True}
    raise RuntimeError('Ambiguous or interrupted submission; reconciliation required, retry cannot republish')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    os.environ['OPENCLAW_SESSIONS'] = str(root)
    sys.path.insert(0, str(root))
    from strategy_quality import VERSION, RESEARCH, parse_model_response, evaluate_isolated, atomic_json
    from candidate_validation import load_validation
    import numpy as np
    bundle = json.load(sys.stdin)
    key = bundle['submission_id']
    if not isinstance(key, str) or not key or len(key) > 120 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in key):
        raise ValueError('Invalid submission_id')
    if bundle.get('generator') != 'Codex':
        raise ValueError('Only Codex-generated bundles accepted')
    if bundle.get('research_mode') not in {'reproduction', 'controlled_variant'}:
        raise ValueError('Explicit research_mode required')
    if bundle['research_mode'] == 'controlled_variant' and not bundle.get('changes'):
        raise ValueError('Variants require explicit changes')
    if bundle['research_mode'] == 'controlled_variant' and not bundle.get('parent_version') and bundle.get('parent_origin') != 'external_source':
        raise ValueError('Variant needs a registered parent or explicit external_source lineage')
    review = bundle['source_review']
    if review.get('approved') is not True or not review.get('checks') or not review.get('evidence'):
        raise ValueError('Completed source review and evidence required')
    source = bundle['source']
    if not source.get('text') or not source.get('url', '').startswith('https://'):
        raise ValueError('Complete source text and HTTPS origin required')
    spec = bundle['spec']
    if spec.get('directions') not in {'long_only', 'short_only', 'long_short'}:
        raise ValueError('Explicit directions required')
    warmup = spec.get('warmup_bars')
    if type(warmup) is not int or not 1 <= warmup <= 10000:
        raise ValueError('Invalid warmup_bars')
    if not bundle.get('translation_zh'):
        raise ValueError('Chinese translation required')
    parse_model_response(json.dumps({'supported': True, 'spec': spec, 'code': bundle['code']}))
    df = load_validation(spec['timeframe'], warmup)
    ls, ss, le, se = evaluate_isolated(bundle['code'], df, check=True)
    if spec['directions'] == 'long_only' and ss.any() or spec['directions'] == 'short_only' and ls.any():
        raise ValueError('Signals violate declared direction')
    signal_hash = hashlib.sha256(spec['timeframe'].encode() + df.timestamp.to_numpy().tobytes() + np.packbits(np.vstack([ls, ss, le, se])).tobytes()).hexdigest()
    source_hash = hashlib.sha256(source['text'].encode()).hexdigest()
    content_hash = hashlib.sha256(json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if args.dry_run:
        print(json.dumps({'validated': True, 'queued': False, 'submission_id': key, 'timeframe': spec['timeframe'], 'signal_hash': signal_hash}))
        return
    from lab_runtime import Backend
    from lab_records import sync_all
    backend = Backend()
    if bundle['research_mode'] == 'controlled_variant' and bundle.get('parent_version'):
        parent = str(int(bundle['parent_version']))
        if not backend.request('research_candidates', query='?version=eq.' + parent + '&limit=1'):
            raise ValueError('Parent candidate must be registered before variant')
    receipts = root / 'codex_submissions'
    receipts.mkdir(exist_ok=True)
    with open('/tmp/strategy_lab_v7_hunt.lock', 'a') as lock, open('/tmp/backtest_research_v7.lock', 'a') as consumer_lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(consumer_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Discovery lock occupied; retry later without deleting lock')
        receipt = receipts / (key + '.json')
        if receipt.exists():
            saved = json.loads(receipt.read_text())
            state = retry_state(root, saved, content_hash,
                                hashlib.sha256((bundle['code'].rstrip() + '\n').encode()).hexdigest(), backend)
            print(json.dumps(state))
            return
        else:
            # Check behavior against prior approved candidates; validation data only.
            for folder in ['Strategy', 'Research_Qualified', 'Research_Rejected']:
                for path in (root / 'pytest' / folder).glob('*_Strategy_Gold.json'):
                    previous = json.loads(path.read_text())
                    if previous.get('signal_hash') == signal_hash and previous.get('source_review', {}).get('approved'):
                        raise ValueError('Duplicate approved trading behavior')
            control = backend.request('ctrl_manager', query='?module=eq.strategy_hunt')
            if not control:
                raise RuntimeError('Discovery control row missing')
            versions = [int(x['version']) for x in backend.request('strategy_hunt', query='?select=version') if str(x['version']).isdigit()]
            for folder in ['Strategy', 'Research_Qualified', 'Research_Rejected']:
                versions += [int(x.name.split('_')[0]) for x in (root / 'pytest' / folder).glob('*_Strategy_Gold.py') if x.name.split('_')[0].isdigit()]
            version = max([int(control[0]['current_version']) - 1] + versions) + 1
            atomic_json(receipt, {'version': version, 'content_hash': content_hash, 'queued': False})
        filename = f'{version}_Strategy_Gold.py'
        path = root / 'pytest' / 'Strategy' / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        code = bundle['code'].rstrip() + '\n'
        metadata = {'engine': VERSION, 'run_id': 'codex_' + key, 'version': version,
                    'signal_timing': 'close_decision_next_open', 'source_url': source['url'],
                    'source_hash': source_hash, 'signal_hash': signal_hash, 'commit': source.get('commit'),
                    'keywords': [bundle['keyword']], 'spec': spec,
                    'code_hash': hashlib.sha256(code.encode()).hexdigest(), 'model': 'Codex',
                    'source_review': review, 'pipeline_revision': 'codex-direct-v1', 'db_committed': False,
                    'research_mode': bundle['research_mode'], 'parent_version': bundle.get('parent_version'),
                    'changes': bundle.get('changes', []), 'parent_origin': bundle.get('parent_origin')}
        atomic_json(path.with_suffix('.json'), metadata)
        temporary = path.with_suffix('.py.tmp')
        temporary.write_text(code, encoding='utf-8')
        os.replace(temporary, path)
        atomic_json(RESEARCH / (source_hash + '.source.json'), source)
        evidence_dir = receipts / key
        evidence_dir.mkdir(exist_ok=True)
        atomic_json(evidence_dir / 'bundle.json', bundle)
        (evidence_dir / 'translation.zh.md').write_text(bundle['translation_zh'], encoding='utf-8')
        journal = {'engine': VERSION, 'run_id': metadata['run_id'], 'keyword': bundle['keyword'],
                   'model_calls': 0, 'pipeline_revision': 'codex-direct-v1',
                   'created': [filename], 'attempts': [{'url': source['url'], 'status': 'accepted',
                   'version': version, 'source_hash': source_hash, 'signal_hash': signal_hash}]}
        atomic_json(RESEARCH / (metadata['run_id'] + '.run.json'), journal)
        backend.request('strategy_hunt', 'POST', {'version': str(version), 'file_name': filename,
                        'source_url': source['url'], 'source_site': source['url'].split('/')[2],
                        'status': 'discovered', 'search_keyword': bundle['keyword'],
                        'strategy_description': bundle['title']}, '?on_conflict=version', upsert=True)
        backend.request('ctrl_manager', 'PATCH', {'current_version': version + 1}, '?module=eq.strategy_hunt')
        # Register research parents and candidate before the consumer can see a committed job.
        from lab_records import sync_discovery, identity, write
        sync_discovery(backend, RESEARCH / (metadata['run_id'] + '.run.json'))
        write(backend, 'research_candidates', {'version': str(version), 'run_id': identity(metadata['run_id']),
              'source_hash': source_hash, 'code_hash': metadata['code_hash'], 'signal_hash': signal_hash,
              'specification': spec, 'research_mode': bundle['research_mode'],
              'parent_version': str(bundle['parent_version']) if bundle.get('parent_version') else None,
              'review_status': 'approved', 'source_review': review}, 'version')
        metadata['db_committed'] = True
        atomic_json(path.with_suffix('.json'), metadata)
        atomic_json(receipt, {'version': version, 'content_hash': content_hash, 'queued': True})
        print(json.dumps({'queued': True, 'version': version, 'queue_file': str(path), 'translation_file': str(evidence_dir / 'translation.zh.md')}))


if __name__ == '__main__':
    main()
