"""Incremental public Binance BTCUSD_PERP data refresh; atomic yearly partitions."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import time
import urllib.parse
import urllib.request
import pandas as pd
from strategy_quality import ROOT, atomic_json
from backtest_v6 import TF_MS

DATA=ROOT/'pytest/k_line_data'
COLUMNS=['timestamp','open','high','low','close','volume','close_time','quote_volume','trades','taker_buy_base','taker_buy_quote']

def public(endpoint,params):
    url='https://dapi.binance.com/dapi/v1/'+endpoint+'?'+urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'OpenClaw-Research/6'}),timeout=25) as r:
                data=json.loads(r.read())
            if not isinstance(data,list): raise RuntimeError('Unexpected Binance response: '+str(data)[:200])
            return data
        except Exception:
            if attempt==3: raise
            time.sleep(min(2**attempt,8))

def klines(tf,start,end):
    rows=[];cursor=start;step=TF_MS[tf]
    while cursor<end:
        # Explicit bounded window prevents API returning the most recent LIMIT rows in a huge range.
        stop=min(cursor+step*1000,end)
        data=public('klines',{'symbol':'BTCUSD_PERP','interval':tf,'startTime':cursor,'endTime':stop-1,'limit':1000})
        if not data: raise RuntimeError(f'No candles returned for {tf} at {cursor}; gap not silently skipped')
        valid=[r[:11] for r in data if cursor<=int(r[0])<stop and int(r[6])<int(time.time()*1000)]
        if not valid: break
        rows.extend(valid);next_cursor=int(valid[-1][0])+step
        if next_cursor<=cursor: raise RuntimeError('Pagination made no progress')
        cursor=next_cursor;time.sleep(0.15)
    return rows

def refresh():
    with open('/tmp/strategy_data_refresh_v7.lock','a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: print('Refresh already running');return
        run_id=time.strftime('%Y%m%d_%H%M%S',time.gmtime())
        stage=DATA/('_refresh_'+run_id);stage.mkdir()
        backup_name='strategy_data_latest_previous' if (DATA/'research_data_manifest.json').exists() else 'strategy_data_'+run_id
        backup=ROOT.parent.parent/'backups'/backup_name;backup.mkdir(parents=True,exist_ok=True)
        report={'symbol':'BTCUSD_PERP','exchange':'Binance','contract':'inverse COIN-M','volume_unit':'contracts','legacy_quote_volume_unit':'BTC','time_zone':'UTC','intervals':{},'backup':str(backup)}
        now=int(time.time()*1000)
        for tf in ['5m','15m','30m','1h']:
            files=sorted((DATA/tf).glob('*.csv'))
            if not files: raise RuntimeError('Missing source history: '+tf)
            df=pd.concat([pd.read_csv(f) for f in files],ignore_index=True).sort_values('timestamp')
            dup=df[df.timestamp.duplicated(False)]
            if not dup.empty and (dup.groupby('timestamp')[COLUMNS[1:]].nunique().max(axis=1)>1).any(): raise RuntimeError('Conflicting source duplicates: '+tf)
            removed=int(df.timestamp.duplicated().sum());df=df.drop_duplicates('timestamp').reset_index(drop=True)
            step=TF_MS[tf];end=(now//step)*step;start=int(df.timestamp.max())+step
            additions=klines(tf,start,end) if start<end else []
            gap_starts=df.timestamp.shift(1)[df.timestamp.diff()>step]
            for i,left in gap_starts.items(): additions.extend(klines(tf,int(left)+step,int(df.timestamp.iloc[i])))
            if additions:
                added=pd.DataFrame(additions,columns=COLUMNS).apply(pd.to_numeric)
                df=pd.concat([df,added],ignore_index=True).drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
            if (df.timestamp.diff().dropna()!=step).any(): raise RuntimeError('Continuity validation failed: '+tf)
            df['year']=pd.to_datetime(df.timestamp,unit='ms',utc=True).dt.year
            (stage/tf).mkdir()
            for year,group in df.groupby('year'): group[COLUMNS].to_csv(stage/tf/f'{year}.csv',index=False)
            report['intervals'][tf]={'rows':len(df),'duplicates_removed':removed,'added':len(additions),'start':int(df.timestamp.min()),'end':int(df.timestamp.max())}
            print('Validated',tf,report['intervals'][tf],flush=True)
        # Exact four-hour aggregation, never manufacture incomplete bars.
        hourly=pd.concat([pd.read_csv(f) for f in (stage/'1h').glob('*.csv')]).sort_values('timestamp')
        hourly['bucket']=(hourly.timestamp//TF_MS['4h'])*TF_MS['4h']
        groups=hourly.groupby('bucket');count=groups.size()
        four=groups.agg(timestamp=('timestamp','first'),open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),close_time=('close_time','last'),quote_volume=('quote_volume','sum'),trades=('trades','sum'),taker_buy_base=('taker_buy_base','sum'),taker_buy_quote=('taker_buy_quote','sum'))
        four=four[count==4].reset_index(drop=True)
        four['year']=pd.to_datetime(four.timestamp,unit='ms',utc=True).dt.year
        (stage/'4h').mkdir()
        for year,group in four.groupby('year'): group[COLUMNS].to_csv(stage/'4h'/f'{year}.csv',index=False)
        report['intervals']['4h']={'rows':len(four),'derived_from':'four complete 1h bars'}
        # Funding timestamps for the exact same inverse perpetual contract.
        start=min(d['start'] for d in report['intervals'].values() if 'start' in d)
        existing_funding=DATA/'funding_BTCUSD_PERP.csv'
        funding=pd.read_csv(existing_funding).to_dict('records') if existing_funding.exists() else []
        cursor=int(max(x['fundingTime'] for x in funding))+1 if funding else start
        try:
            while cursor<now:
                stop=min(cursor+180*86400000,now)
                rows=public('fundingRate',{'symbol':'BTCUSD_PERP','startTime':cursor,'endTime':stop-1,'limit':1000})
                if rows:
                    funding.extend(rows);cursor=int(rows[-1]['fundingTime'])+1
                else:cursor=stop
                time.sleep(0.15)
            f=pd.DataFrame(funding)
            if not f.empty:
                f=f[['fundingTime','fundingRate']].apply(pd.to_numeric).drop_duplicates('fundingTime').sort_values('fundingTime')
                f.to_csv(stage/'funding_BTCUSD_PERP.csv',index=False)
                complete=int(f.fundingTime.min())<=start+86400000 and int(f.fundingTime.max())>=now-86400000 and not (f.fundingTime.diff()>86400000).any()
                atomic_json(stage/'funding_BTCUSD_PERP.json',{'complete':bool(complete),'start':start,'end':now,'rows':len(f),'symbol':'BTCUSD_PERP'})
                report['funding_rows']=len(f);report['funding_complete']=bool(complete)
            else:report['funding_error']='No historical rates returned'
        except Exception as e:report['funding_error']=str(e)[:300]
        # Swap only after all candle intervals validate. Preserve every original file.
        for tf in ['5m','15m','30m','1h','4h']:
            target=DATA/tf;target.mkdir(exist_ok=True);(backup/tf).mkdir(exist_ok=True)
            for f in (stage/tf).glob('*.csv'):
                original=target/f.name
                if original.exists() and original.read_bytes()==f.read_bytes():continue
                if original.exists():shutil.copy2(original,backup/tf/f.name)
                os.replace(f,original)
        for name in ['funding_BTCUSD_PERP.csv','funding_BTCUSD_PERP.json']:
            if (stage/name).exists():
                if (DATA/name).exists():shutil.copy2(DATA/name,backup/name)
                os.replace(stage/name,DATA/name)
        atomic_json(DATA/'research_data_manifest.json',report)
        print(json.dumps(report,ensure_ascii=False),flush=True)

def ensure_fresh():
    manifest=DATA/'research_data_manifest.json'
    state=json.loads(manifest.read_text()) if manifest.exists() else {}
    latest=state.get('intervals',{}).get('1h',{}).get('end',0)
    if time.time()*1000-latest>24*3600000:
        print('[research-v7] Refreshing public market history before discovery',flush=True)
        refresh()

if __name__=='__main__':refresh()
