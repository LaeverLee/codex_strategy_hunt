"""Replayable local journals synchronize complete research records to the fresh project."""
import hashlib
import json
from pathlib import Path
import urllib.parse
import uuid
from quality_policy import validate_result, strict_json
from strategy_quality import ROOT, RESEARCH, VERSION, atomic_json

def identity(key): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'openclaw-strategy-lab-v7:'+key))

def write(backend, table, row, conflict):
    json.dumps(row, allow_nan=False)
    return backend.request(table,'POST',row,'?on_conflict='+conflict,upsert=True)

def sync_discovery(backend,path):
    report=strict_json(path.read_text()); key=report['run_id']; rid=identity(key)
    write(backend,'research_runs',{'id':rid,'run_key':key,'engine':VERSION,'kind':'discovery',
        'status':'completed' if 'model_calls' in report else 'interrupted',
        'configuration':{'keyword':report.get('keyword'),'keyword_id':report.get('keyword_id'),
            'selection_policy':report.get('selection_policy'),'queries':report.get('queries',[]),
            'pipeline_revision':report.get('pipeline_revision','v7-initial'),
            'qualification_policy':report.get('qualification_policy')},
        'summary':{'created':report.get('created',[]),'model_calls':report.get('model_calls'),
            'attempts':len(report.get('attempts',[])), 'journal':str(path)}},'run_key')
    for i,attempt in enumerate(report.get('attempts',[])):
        write(backend,'source_attempts',{'id':identity(key+':attempt:'+str(i)), 'run_id':rid,
            'attempt_key':str(i),'keyword_id':report.get('keyword_id'), 'query':attempt.get('query'),
            'source_url':attempt['url'],'source_hash':attempt.get('source_hash'),
            'commit_hash':attempt.get('commit'),'outcome':attempt['status'],
            'reason':attempt.get('reason'),'details':attempt},'run_id,attempt_key')

def sync_candidate(backend,path):
    meta=strict_json(path.read_text())
    write(backend,'research_candidates',{'version':str(meta['version']),'run_id':identity(meta['run_id']),
        'source_hash':meta['source_hash'],'code_hash':meta['code_hash'],
        'signal_hash':meta['signal_hash'],'specification':meta['spec'],
        'research_mode':meta.get('research_mode','reproduction'),'parent_version':str(meta['parent_version']) if meta.get('parent_version') else None,'review_status':'approved' if meta.get('source_review',{}).get('approved') else 'rejected' if meta.get('source_review') else 'pending',
        'source_review':meta.get('source_review',{})},'version')

def sync_result(backend,path):
    result=strict_json(path.read_text()); validate_result(result); ver=str(result['version'])
    key='backtest:'+ver+':'+result['code_hash']; rid=identity(key)
    config=result['cost_model']; fingerprint=result['dataset_fingerprint']; did=identity('dataset:'+fingerprint)
    write(backend,'dataset_snapshots',{'id':did,'fingerprint':fingerprint,
        'market':result['contract'],'contract_type':result['cost_model']['contract_type'],'timeframe':result['spec']['timeframe'],
        'first_bar_ms':result['data']['start'],'last_bar_ms':result['data']['end'],
        'bar_count':result['data']['bar_count'],'manifest':result['data']},'fingerprint')
    write(backend,'research_runs',{'id':rid,'run_key':key,'engine':VERSION,'kind':'backtest',
        'status':'completed','configuration':{'cost_model':config,'split':result['split'],'thresholds':result['thresholds']},
        'summary':{'qualified':result['qualified'],'paper_ready':result['paper_ready'],
            'journal':str(path),'journal_hash':hashlib.sha256(path.read_bytes()).hexdigest(),
            'limitations':result['limitations']}},'run_key')
    splits=[(name,result[name],1.5 if name=='cost_stress' else 1.) for name in ['train','validation','test','cost_stress']]
    splits += [('test_fold_'+str(i+1),value,1.) for i,value in enumerate(result['test_folds'])]
    for name,value,multiplier in splits:
        write(backend,'research_evaluations',{'id':identity(key+':'+name),'evaluation_key':key+':'+name,
            'version':ver,'run_id':rid,'dataset_id':did,'split':name,
            'cost_model':{**config,'multiplier':multiplier},'metrics':value['metrics'],
            'qualified':result['qualified'],'reasons':result.get('rejection_reasons',[]) or ([] if result['qualified'] else ['Historical quality gates not met'])},'evaluation_key')

def sync_all(backend):
    directory=ROOT/'sync_journal';directory.mkdir(parents=True,exist_ok=True)
    # Parents before children; independent candidate journals also recover late DB commits.
    candidates=[]
    for folder in ['Strategy','Research_Qualified','Research_Rejected']:
        for path in (ROOT/'pytest'/folder).glob('*_Strategy_Gold.json'):
            meta=strict_json(path.read_text())
            if meta.get('engine')==VERSION and meta.get('db_committed'): candidates.append(path)
    paths=sorted(RESEARCH.glob('*.run.json'))+candidates+sorted((ROOT/'pytest/research_results').glob('*.json'))
    for path in paths:
        if path.name.endswith('.rejected.json'):
            continue  # operational rejection remains in compatibility status + local journal
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        mark=directory/(hashlib.sha256(str(path).encode()).hexdigest()+'.json')
        if mark.exists() and strict_json(mark.read_text()).get('hash')==digest: continue
        if path.name.endswith('.run.json'): sync_discovery(backend,path)
        elif path.name.endswith('_Strategy_Gold.json'): sync_candidate(backend,path)
        else: sync_result(backend,path)
        atomic_json(mark,{'hash':digest,'source':str(path)})
