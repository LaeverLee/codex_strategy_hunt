"""Private worker connection; legacy credentials are never copied into source files."""
import ast
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.parse
import urllib.request

BASE = Path(__file__).resolve().parent
CONFIG = BASE.parent / 'connection.json'
EXPECTED_URL = 'https://jygaprrhtuwzffyrnipt.supabase.co/functions/v1/strategy-worker'


class Backend:
    def __init__(self):
        config = json.loads(CONFIG.read_text())
        if config['url'] != EXPECTED_URL: raise RuntimeError('Unexpected project destination')
        self.SUPABASE_URL = config['url']
        self.SUPABASE_KEY = config['token']

    def check_url_exists(self, url):
        rows = self.request('strategy_hunt', query='?select=id&source_url=eq.'+urllib.parse.quote(url,safe='')+'&limit=1')
        return bool(rows)

    def request(self, table, method='GET', data=None, query='', upsert=False):
        req=urllib.request.Request(self.SUPABASE_URL+'/rest/v1/'+table+query,
            data=None if data is None else json.dumps(data,allow_nan=False).encode(),method=method,
            headers={'Authorization':'Bearer '+self.SUPABASE_KEY,'Content-Type':'application/json',
                     'Prefer':'return=representation,resolution=merge-duplicates' if upsert else 'return=representation'})
        with urllib.request.urlopen(req,timeout=25) as response:
            body=response.read(); return json.loads(body) if body else []








def main():
    os.environ['OPENCLAW_SESSIONS']=str(BASE)
    from lab_records import sync_all
    backend=Backend()
    mode=sys.argv[1] if len(sys.argv)>1 else 'health'
    if mode not in {'health','sync','backtest'}:
        raise ValueError('Codex research only: old hunt/MiniMax dispatcher is excluded')
    if mode=='health':
        print(json.dumps({'project':'jygaprrhtuwzffyrnipt','controls':backend.request('ctrl_manager',query='?select=module,current_version,status')}))
        return
    sync_all(backend)
    if mode=='backtest':
        import backtest_v6
        try: backtest_v6.main(backend)
        finally: sync_all(backend)

if __name__=='__main__': main()
