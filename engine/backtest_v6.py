"""Causal execution, full equity accounting and fixed out-of-sample evaluation."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request
import numpy as np
import pandas as pd
from strategy_quality import ROOT, atomic_json, evaluate_isolated, VERSION
from quality_policy import POLICY, THRESHOLDS, passes_metrics

RESULTS=ROOT/"pytest/research_results"
TRAIN_END=1704067200000  # 2024-01-01 UTC; fixed before examining candidates
VALIDATION_END=1735689600000  # 2025-01-01 UTC
TF_MS={"5m":300000,"15m":900000,"30m":1800000,"1h":3600000,"4h":14400000}

def load_data(tf):
    files=sorted((ROOT/"pytest/k_line_data"/tf).glob("*.csv"))
    if not files: raise RuntimeError("Native timeframe data missing: "+tf)
    df=pd.concat([pd.read_csv(f) for f in files],ignore_index=True)
    required=["timestamp","open","high","low","close","volume"]
    if not set(required)<=set(df): raise ValueError("Missing OHLCV fields")
    df[required]=df[required].apply(pd.to_numeric,errors="raise")
    if not np.isfinite(df[required].to_numpy()).all(): raise ValueError("Invalid numeric data")
    duplicates=df[df.timestamp.duplicated(False)]
    if not duplicates.empty and (duplicates.groupby("timestamp")[required[1:]].nunique().max(axis=1)>1).any():
        raise ValueError("Conflicting timestamp duplicates")
    duplicates_removed=int(df.timestamp.duplicated().sum())
    df=df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    if (df[["open","high","low","close"]]<=0).any().any() or (df.volume<0).any(): raise ValueError("Nonpositive prices or negative volume")
    if ((df.high<df[["open","close","low"]].max(axis=1))|(df.low>df[["open","close","high"]].min(axis=1))).any(): raise ValueError("Invalid high/low")
    delta=df.timestamp.diff(); gaps=df.loc[delta>TF_MS[tf],"timestamp"].astype(int).tolist()
    if ((delta.dropna()%TF_MS[tf])!=0).any(): raise ValueError("Irregular candle interval")
    report={"bar_count":len(df),"duplicates_removed":duplicates_removed,"gaps":gaps,"start":int(df.timestamp.min()),"end":int(df.timestamp.max()),"stale_days":round((time.time()*1000-df.timestamp.max())/86400000,1),"data_hash":hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()}
    return df,report

def atr_series(df,period=14,method="sma"):
    prev=df.close.shift(1)
    tr=pd.concat([df.high-df.low,(df.high-prev).abs(),(df.low-prev).abs()],axis=1).max(axis=1)
    if method=="sma": return tr.rolling(period).mean().to_numpy()
    if method=="ema": return tr.ewm(span=period,adjust=False,min_periods=period).mean().to_numpy()
    if method!="wilder": raise ValueError("Unknown ATR smoothing")
    values=tr.to_numpy(); out=np.full(len(values),np.nan)
    if len(values)>=period:
        out[period-1]=values[:period].mean()
        for i in range(period,len(values)):out[i]=(out[i-1]*(period-1)+values[i])/period
    return out

def simulate(df,signals,risk,*,warmup=50,legacy=False,cost_multiplier=1.,start=0,end=None,ledger=False):
    """signal[t] is known at close t; fill at open t+1. Legacy already-shifted signals use t."""
    end=len(df) if end is None else end
    inverse=os.environ.get("STRATEGY_CONTRACT_TYPE","inverse")=="inverse"
    reference=float(df.open.iloc[max(start,warmup,15)])
    capital=5000.; initial=capital; pos=None; equity=[]; trades=[]; funding_paid=0.
    arrays={c:df[c].to_numpy() for c in ["timestamp","open","high","low","close"]}
    ls,ss,le,se=signals; atr=atr_series(df,risk.get("atr_period") or 14,risk.get("atr_method") or "sma")
    fee=float(os.environ.get("STRATEGY_FEE_PER_SIDE","0.001"))*cost_multiplier
    entry_slip=float(os.environ.get("STRATEGY_ENTRY_SLIP","0.0004"))*cost_multiplier
    exit_slip=float(os.environ.get("STRATEGY_EXIT_SLIP","0.0006"))*cost_multiplier
    spread=float(os.environ.get("STRATEGY_SPREAD_ROUNDTRIP","0.0002"))*cost_multiplier
    position_fraction=float(os.environ.get("STRATEGY_POSITION_FRACTION","0.3"))
    if not 0<position_fraction<=1: raise ValueError("Position fraction must be in (0,1]")
    def close_position(price,i,reason):
        nonlocal capital,pos
        fill=price*(1-exit_slip*pos["side"])
        gross=pos["notional"]*(1/pos["entry"]-1/fill)*pos["side"]*reference if inverse else pos["qty"]*(fill-pos["entry"])*pos["side"]
        exit_fee=pos["notional"]/fill*reference*(fee+spread/2) if inverse else pos["qty"]*fill*(fee+spread/2)
        capital+=gross-exit_fee
        pnl=gross-exit_fee-pos["entry_fee"]-pos["funding"]
        trades.append({"entry_bar":pos["bar"],"exit_bar":i,"entry_timestamp":int(arrays["timestamp"][pos["bar"]]),"exit_timestamp":int(arrays["timestamp"][i]),"side":pos["side"],"entry":pos["entry"],"exit":fill,"net_pnl":pnl,"fees":exit_fee+pos["entry_fee"],"funding":pos["funding"],"reason":reason})
        pos=None
    first=max(start,warmup,15)
    for i in range(first,end):
        signal_index=i if legacy else i-1
        just_closed=False
        if pos:
            side=pos["side"]; op=arrays["open"][i]
            if "funding_rate" in df:
                rate=float(df.funding_rate.iloc[i])
                amount=pos["notional"]/op*reference*rate*side if inverse else pos["qty"]*op*rate*side
                capital-=amount; funding_paid+=amount; pos["funding"]+=amount
            # Stop gaps take priority, then pre-existing exit instructions at this open.
            if pos["sl"] is not None and (op<=pos["sl"] if side==1 else op>=pos["sl"]): close_position(op,i,"gap_stop"); just_closed=True
            elif pos["tp"] is not None and (op>=pos["tp"] if side==1 else op<=pos["tp"]): close_position(op,i,"gap_target"); just_closed=True
            elif (le[signal_index] if side==1 else se[signal_index]): close_position(op,i,"signal_exit"); just_closed=True
            elif risk.get("max_hold_bars") and i-pos["bar"]>=risk["max_hold_bars"]: close_position(op,i,"time_exit"); just_closed=True
        if pos is None and not just_closed and capital>0 and np.isfinite(atr[i-1]):
            side=1 if ls[signal_index] and not ss[signal_index] else -1 if ss[signal_index] and not ls[signal_index] else 0
            if side:
                fill=arrays["open"][i]*(1+entry_slip*side); notional=capital/reference*fill*position_fraction if inverse else capital*position_fraction
                # BTCUSD inverse contracts have USD face value; fractional contracts aren't executable.
                if inverse: notional=np.floor(notional/100)*100
                if notional>0:
                    entry_fee=notional/fill*reference*(fee+spread/2) if inverse else notional*(fee+spread/2); capital-=entry_fee
                    pos={"side":side,"entry":fill,"qty":notional/fill,"notional":notional,"funding":0.,"entry_fee":entry_fee,"bar":i,
                         "sl":fill-side*atr[i-1]*risk["stop_atr"] if risk.get("stop_atr") else fill*(1-side*risk["stop_pct"]) if risk.get("stop_pct") else None,
                         "tp":fill+side*atr[i-1]*risk["take_atr"] if risk.get("take_atr") else fill*(1+side*risk["take_pct"]) if risk.get("take_pct") else None}
        if pos:
            side=pos["side"]
            sl=pos["sl"] is not None and (arrays["low"][i]<=pos["sl"] if side==1 else arrays["high"][i]>=pos["sl"])
            tp=pos["tp"] is not None and (arrays["high"][i]>=pos["tp"] if side==1 else arrays["low"][i]<=pos["tp"])
            # Without tick sequence, conservatively choose stop first, including entry bar.
            if sl: close_position(pos["sl"],i,"ambiguous_stop_first" if tp else "stop")
            elif tp: close_position(pos["tp"],i,"target")
        unrealized=(pos["notional"]*(1/pos["entry"]-1/arrays["close"][i])*pos["side"]*reference if inverse else pos["qty"]*(arrays["close"][i]-pos["entry"])*pos["side"]) if pos else 0
        marked=capital+unrealized
        equity.append((int(arrays["timestamp"][i]),marked))
        if marked<=0: break
    if pos and equity:
        i=min(end-1,first+len(equity)-1); close_position(arrays["close"][i],i,"period_end"); equity[-1]=(equity[-1][0],capital)
    if not equity: raise ValueError("Insufficient period after warmup")
    e=pd.Series([initial]+[x[1] for x in equity]); dd=((e.cummax()-e)/e.cummax()).max()*100
    daily=pd.Series([x[1] for x in equity],index=pd.to_datetime([x[0] for x in equity],unit="ms",utc=True)).resample("1D").last().ffill()
    # Include initial capital to capture the first day's return.
    daily_values=np.r_[initial,daily.to_numpy()]; dr=pd.Series(daily_values).pct_change().dropna()
    sharpe=float(dr.mean()/dr.std(ddof=1)*np.sqrt(365)) if len(dr)>2 and dr.std(ddof=1)>0 else 0.
    profits=sum(max(0,x["net_pnl"]) for x in trades); losses=sum(max(0,-x["net_pnl"]) for x in trades)
    days=max((equity[-1][0]-equity[0][0])/86400000,1)
    metrics={"return_pct":round((capital/initial-1)*100,4),"drawdown_pct":round(float(dd),4),"win_rate":round(100*sum(x["net_pnl"]>0 for x in trades)/len(trades),2) if trades else 0.,"profit_factor":round(profits/losses,4) if losses else (99. if profits else 0.),"trade_count":len(trades),"sharpe_ratio":round(sharpe,4),"annualized_return_pct":round(((max(capital,0)/initial)**(365/days)-1)*100,4),"fees":round(sum(x["fees"] for x in trades),4),"funding_paid":round(funding_paid,4),"ambiguous_bars":sum(x["reason"]=="ambiguous_stop_first" for x in trades),"return_currency":"BTC" if inverse else "USD","usd_portfolio_return_pct":round((capital/initial*arrays["close"][min(end-1,first+len(equity)-1)]/reference-1)*100,4) if inverse else round((capital/initial-1)*100,4)}
    return {"metrics":metrics,"trades":trades if ledger else [],"equity":equity if ledger else []}

def db(legacy,table,method="GET",data=None,query=""):
    base=legacy.SUPABASE_URL.rsplit("/rest/v1/",1)[0]; key=legacy.SUPABASE_KEY
    req=urllib.request.Request(base+"/rest/v1/"+table+query,data=None if data is None else json.dumps(data).encode(),method=method,headers={"apikey":key,"Authorization":"Bearer "+key,"Content-Type":"application/json","Prefer":"return=representation"})
    with urllib.request.urlopen(req,timeout=20) as r:
        body=r.read(); return json.loads(body) if body else []

def status(legacy,version,state,error=None):
    rows=db(legacy,"backtest_version_status",query=f"?version=eq.{version}")
    payload={"version":str(version),"status":state,"updated_at":pd.Timestamp.now(tz="UTC").isoformat(),"retry_count":rows[0].get("retry_count",0) if rows else 0,"error_detail":error}
    db(legacy,"backtest_version_status","PATCH" if rows else "POST",payload,f"?version=eq.{version}" if rows else "")

def qualify(result):
    v=result["validation"]["metrics"]; t=result["test"]["metrics"]
    positive=sum(x["metrics"]["return_pct"]>0 for x in result["test_folds"])
    ok=all(passes_metrics(m) for m in [v,t]) and positive>=2 and result["cost_stress"]["metrics"]["return_pct"]>0
    return ok,dict(THRESHOLDS,policy=POLICY)

def requalify(result):
    result['qualified'],result['thresholds']=qualify(result)
    if result.get('status')=='source_review_failed': result['qualified']=False
    result['paper_ready']=result['qualified'] and result['data']['stale_days']<=2 and result['funding_included']
    return result

def align_funding(funding,tf):
    # Exchange funding timestamps often carry a few milliseconds of jitter.
    # Match the containing candle rather than silently dropping non-exact timestamps.
    buckets=(funding.fundingTime.astype('int64')//TF_MS[tf])*TF_MS[tf]
    return funding.fundingRate.groupby(buckets).sum()

def run_candidate(path):
    meta=json.loads(path.with_suffix(".json").read_text())
    if not meta.get("db_committed"): raise RuntimeError("Discovery DB commit incomplete; preserve candidate for retry")
    if not meta.get('source_review',{}).get('approved') and meta.get('source_url')!='integration-fixture-only':
        raise ValueError('Independent source semantic review missing or failed')
    code=path.read_text(); digest=hashlib.sha256(code.encode()).hexdigest()
    if digest!=meta["code_hash"]: raise ValueError("Candidate changed after source validation")
    tf=meta["spec"]["timeframe"]; df,data_report=load_data(tf)
    funding_path=ROOT/"pytest/k_line_data/funding_BTCUSD_PERP.csv"
    funding_included=False
    if funding_path.exists():
        funding=pd.read_csv(funding_path)
        funding=funding.drop_duplicates("fundingTime").sort_values("fundingTime")
        # Funding assessed at bar OPEN to positions carried into that timestamp.
        df["funding_rate"]=df.timestamp.map(align_funding(funding,tf)).fillna(0.)
        coverage=json.loads(funding_path.with_suffix(".json").read_text())
        funding_included=coverage.get("complete",False) and coverage["start"]<=int(df.timestamp.min()) and coverage["end"]>=int(df.timestamp.max())
    warmup=max(50,meta["spec"]["warmup_bars"])
    a=int(np.searchsorted(df.timestamp.to_numpy(),TRAIN_END)); b=int(np.searchsorted(df.timestamp.to_numpy(),VALIDATION_END))
    if min(a,b-a,len(df)-b)<max(300,warmup*2): raise ValueError("Insufficient fixed train/validation/test history")
    # Validate technical causality on development data only; no future-data optimization.
    evaluate_isolated(code,df.iloc[max(0,a-4096):a].reset_index(drop=True),check=True)
    signals=evaluate_isolated(code,df,timeout=90)
    risk=meta["spec"]["risk"]
    result={"engine":VERSION,"version":meta["version"],"source_url":meta["source_url"],"code_hash":digest,"spec":meta["spec"],"keywords":meta.get("keywords",[]),"data":data_report,"split":{"train_end":TRAIN_END,"validation_end":VALIDATION_END},"funding_included":funding_included,"status":"research_only","contract":"Binance COIN-M BTCUSD_PERP","return_currency":"BTC"}
    result['cost_model']={name:float(os.environ.get(env,default)) for name,env,default in [
        ('fee_per_side','STRATEGY_FEE_PER_SIDE','0.001'),('entry_slip','STRATEGY_ENTRY_SLIP','0.0004'),
        ('exit_slip','STRATEGY_EXIT_SLIP','0.0006'),('spread_roundtrip','STRATEGY_SPREAD_ROUNDTRIP','0.0002'),
        ('position_fraction','STRATEGY_POSITION_FRACTION','0.3')]}
    result['cost_model'].update(contract_type=os.environ.get('STRATEGY_CONTRACT_TYPE','inverse'),return_currency='BTC',funding_included=funding_included)
    funding_hash=hashlib.sha256(funding_path.read_bytes()).hexdigest() if funding_path.exists() else 'absent'
    result['data']['funding_hash']=funding_hash
    result['dataset_fingerprint']=hashlib.sha256((tf+':'+data_report['data_hash']+':'+funding_hash).encode()).hexdigest()
    for name,start,end in [("train",0,a),("validation",a,b),("test",b,len(df))]:
        result[name]=simulate(df,signals,risk,warmup=warmup,start=start,end=end,ledger=True)
    edges=np.linspace(b,len(df),4,dtype=int)
    result["test_folds"]=[simulate(df,signals,risk,warmup=warmup,start=int(edges[i]),end=int(edges[i+1])) for i in range(3)]
    result["cost_stress"]=simulate(df,signals,risk,warmup=warmup,start=b,cost_multiplier=1.5)
    result["qualified"],result["thresholds"]=qualify(result)
    # Data feed stale and funding absent: even qualified candidates only advance to research review.
    result["paper_ready"]=result["qualified"] and data_report["stale_days"]<=2 and result["funding_included"]
    result["limitations"]=["No order-book or intrabar sequence", "Funding timestamps align to candle open; bar-open price proxies mark price", "Source rules require human review", "Selection across many candidates remains a multiple-testing risk"]
    result['limitations'].append('2025-2026 is reused historical evaluation, not a fresh holdout; forward paper validation is required')
    if not funding_included: result["limitations"].append("Funding coverage incomplete")
    return result

def main(legacy):
    RESULTS.mkdir(parents=True,exist_ok=True)
    with open("/tmp/backtest_research_v7.lock","a") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: print("[research-v7] Backtest already running; skipped"); return
        folder=ROOT/"pytest/Strategy"
        # New source-grounded candidates have priority; old candidates aren't silently relabeled.
        candidates=[]
        for f in folder.glob("*_Strategy_Gold.py"):
            side=f.with_suffix(".json")
            if not side.exists(): continue
            meta=json.loads(side.read_text())
            if meta.get("engine")==VERSION and meta.get("db_committed"):
                candidates.append(f)
        candidates.sort(key=lambda f:int(f.name.split("_")[0]))
        if not candidates:
            print("[research-v7] No source-grounded candidate queued; legacy candidates require migration/review."); return
        path=candidates[0]; ver=int(path.name.split("_")[0]); report_path=RESULTS/f"{ver}.json"
        db(legacy,"ctrl_manager","PATCH",{"status":"running"},"?module=eq.backtest")
        try:
            if report_path.exists():
                result=json.loads(report_path.read_text())
                if result['code_hash']!=hashlib.sha256(path.read_bytes()).hexdigest():raise ValueError('Candidate changed after cached backtest')
            else:
                result=run_candidate(path); atomic_json(report_path,result)
            requalify(result); atomic_json(report_path,result)
            m=result["test"]["metrics"]
            schema={k:m[k] for k in ["return_pct","drawdown_pct","win_rate","profit_factor","trade_count","sharpe_ratio"]}
            row={**schema,"strategy_name":path.stem,"version":str(ver),"timeframe":result["spec"]["timeframe"],"atr_param":result["spec"]["risk"].get("stop_atr") or 0.}
            # Idempotent retry of this new version only; don't rewrite historical results.
            exists=db(legacy,"backtest_strategy",query=f"?version=eq.{ver}&limit=1")
            if not exists: db(legacy,"backtest_strategy","POST",[row])
            status(legacy,ver,"success" if result["qualified"] else "tested_failed","research-v7: OOS qualified; research review only" if result["qualified"] else "research-v7: OOS quality gates not met")
            # Keep legacy Good untouched; reviewed research lives in a separate tier.
            destination=ROOT/"pytest"/("Research_Qualified" if result["qualified"] else "Research_Rejected")
            destination.mkdir(parents=True,exist_ok=True)
            for f in [path,path.with_suffix(".json")]:
                os.replace(f,destination/f.name)
            print(f"[research-v7] v{ver}: OOS return {m['return_pct']}%, DD {m['drawdown_pct']}%, PF {m['profit_factor']}, trades {m['trade_count']}; qualified={result['qualified']}; research only")
        except (ValueError,SyntaxError,KeyError) as e:
            atomic_json(RESULTS/f"{ver}.rejected.json",{"engine":VERSION,"version":ver,"qualified":False,"reason":str(e)})
            status(legacy,ver,"tested_failed",str(e)[:1000])
            destination=ROOT/"pytest/Research_Rejected"; destination.mkdir(parents=True,exist_ok=True)
            for f in [path,path.with_suffix(".json")]:
                if f.exists(): os.replace(f,destination/f.name)
            print(f"[research-v7] Candidate rejected: {e}")
        finally:
            db(legacy,"ctrl_manager","PATCH",{"status":"idle"},"?module=eq.backtest")
