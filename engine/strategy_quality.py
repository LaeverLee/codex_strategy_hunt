"""Source-grounded strategy research and deterministic causality validation."""
from quality_policy import strict_json
import ast
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import urllib.error
import re
from html.parser import HTMLParser
import numpy as np
import pandas as pd

VERSION = "research-v7"
ROOT = Path(os.environ.get("OPENCLAW_SESSIONS", "/home/node/.openclaw/workspace/strategy_lab_v7/sessions"))
RESEARCH = ROOT / "goldhuntv2" / "research"
ALLOWED_TFS = {"5m", "15m", "30m", "1h", "4h"}

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temp, path)

def canonical_url(url):
    p = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(p.query)
    query = [(k,v) for k,v in query if not k.lower().startswith("utm_") and k not in {"ref", "fbclid"}]
    return urllib.parse.urlunsplit(("https", p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), urllib.parse.urlencode(query), ""))

def safe_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise ValueError("Only public HTTPS sources are supported")
    for item in socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError("Source resolves to a non-public address")
    return url

class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(url):
    req = urllib.request.Request(safe_url(url),headers={"User-Agent":"OpenClaw-StrategyResearch/6", "Accept":"text/html,application/json,text/plain"})
    with urllib.request.build_opener(PublicRedirect()).open(req,timeout=20) as response:
        content_type = response.headers.get("Content-Type","")
        if any(t in content_type for t in ["application/pdf","image/","application/octet-stream"]):
            raise ValueError("Unsupported source format; obtain the full text first")
        body = response.read(1_500_001)
        if len(body)>1_500_000:
            raise ValueError("Source exceeds size budget")
        return body.decode("utf-8",errors="replace"), response.geturl()

class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip=0; self.parts=[]; self.blocks=[]; self.code=0; self.current=[]
    def handle_starttag(self,tag,attrs):
        if tag in {"script","style","nav","footer","header","noscript","svg"}: self.skip+=1
        if tag in {"pre"} and not self.skip: self.code+=1; self.current=[]
    def handle_endtag(self,tag):
        if tag in {"script","style","nav","footer","header","noscript","svg"} and self.skip: self.skip-=1
        if tag=="pre" and self.code:
            self.blocks.append("".join(self.current)); self.code-=1
        if tag in {"p","div","li","h1","h2","h3","br","pre"} and not self.skip: self.parts.append("\n")
    def handle_data(self,data):
        if not self.skip:
            self.parts.append(data)
            if self.code: self.current.append(data)

def github_git_source(url,hypothesis=""):
    """Read public commit/tree/blobs without spending anonymous REST quotas or checking out code."""
    p=urllib.parse.urlsplit(url);pieces=p.path.strip('/').split('/')
    owner,repo=pieces[:2];repo=repo.removesuffix('.git')
    if not all(re.fullmatch(r'[A-Za-z0-9_.-]+',v) and v not in {'.','..'} for v in [owner,repo]):raise ValueError('Invalid repository path')
    explicit='/'.join(pieces[4:]) if len(pieces)>4 and pieces[2]=='blob' else None
    ref=pieces[3] if explicit else None
    env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull}
    with tempfile.TemporaryDirectory(prefix='public-strategy-source-') as folder:
        dest=Path(folder)/'repo'
        def git(args,inside=True):
            cmd=['git','-c','credential.helper=','-c','core.hooksPath='+os.devnull]
            if inside:cmd+=['-C',str(dest)]
            r=subprocess.run(cmd+args,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=40)
            if r.returncode:raise ValueError('Public Git read failed: '+r.stderr[-300:])
            return r.stdout
        args=['clone','--quiet','--depth','1','--filter=blob:none','--no-checkout','--single-branch']
        sha_ref=ref and bool(re.fullmatch('[0-9a-fA-F]{40}',ref))
        if ref and not sha_ref:args+=['--branch',ref]
        git(args+[f'https://github.com/{owner}/{repo}.git',str(dest)],False)
        if sha_ref:git(['fetch','--quiet','--depth','1','origin',ref])
        commit=git(['rev-parse',ref if sha_ref else 'HEAD']).strip()
        files=git(['ls-tree','-r','--name-only',commit]).splitlines()
        candidates=[f for f in files if f.endswith('.py') and not any(t in f.lower() for t in ['tests/','test_','_test.py','setup.py','venv','__init__','download','credential']) and any(t in f.lower() for t in ['strateg','signal','trend','momentum','reversion','breakout','backtest','bitcoin','btc','main.py'])]
        if explicit and explicit.endswith('.py'):
            candidates=[explicit] if explicit in files else []
        if not candidates:raise ValueError('No concrete strategy Python file located')
        tokens=[w.lower() for w in re.findall(r'[A-Za-z]+',hypothesis) if len(w)>2]
        selected=sorted(candidates,key=lambda f:(-sum(w in f.lower() for w in tokens),len(f),f))[:2]
        chunks=['REPOSITORY '+owner+'/'+repo]
        readme=next((f for f in files if f.lower()=='readme.md'),None)
        for f in ([readme] if readme else [])+selected:
            content=git(['show',commit+':'+f])
            if len(content)>24000:raise ValueError('Strategy source requires a dedicated full-file review')
            chunks.append('FILE '+f+'\n'+content)
        return {'url':url,'commit':commit,'files':selected,'text':'\n\n'.join(chunks),'retrieval':'public_git_no_checkout'}

def acquire_source(url,hypothesis=""):
    """Return actual strategy evidence, never search snippets as a substitute."""
    url=canonical_url(url); p=urllib.parse.urlsplit(url); pieces=p.path.strip("/").split("/")
    if p.hostname in {"github.com","gist.github.com"}:
        if p.hostname=="gist.github.com" or len(pieces)<2 or pieces[0] in {"topics","search","collections"}:
            raise ValueError("Repository/file evidence required; index pages are rejected")
        return github_git_source(url,hypothesis)
    if any(t in p.path.lower() for t in ["/topics/","/equities/","/tag/","/category/"]):
        raise ValueError("Index or quote page is not a strategy source")
    body,final=fetch(url); parser=ArticleParser(); parser.feed(body)
    text=html.unescape("".join(parser.parts)).strip()
    if len(text)<1200: raise ValueError("Insufficient complete strategy evidence")
    # Reject instead of blindly cutting off the exit rules.
    if len(text)>50000: raise ValueError("Source too long for faithful single-pass translation")
    if not any(t in text.lower() for t in ["entry", "enter", "buy", "long", "進場"]):
        raise ValueError("No entry rules found")
    if not any(t in text.lower() for t in ["exit", "stop", "sell", "close position", "出場", "停損"]):
        raise ValueError("No exit/risk rules found")
    return {"url":canonical_url(final),"commit":None,"files":[],"text":text}

def parse_model_response(text):
    text=text.strip()
    if text.startswith("```"): text="\n".join(text.splitlines()[1:-1])
    d=strict_json(text)
    if not isinstance(d,dict) or type(d.get("supported")) is not bool:
        raise ValueError("Model response requires a boolean supported field")
    if not d["supported"]:
        raise ValueError("Unsupported source: "+str(d.get("reason","unspecified")))
    spec=d.get("spec")
    if not isinstance(spec,dict): raise ValueError("Supported source requires a specification object")
    tf=spec.get("timeframe")
    if tf not in ALLOWED_TFS: raise ValueError("Source must specify a supported native timeframe")
    if spec.get("market")!="BTC": raise ValueError("Source must explicitly support BTC")
    for field in ["hypothesis","entry_rules","exit_rules","evidence_quotes","failure_conditions"]:
        if not spec.get(field): raise ValueError("Missing source-grounded field: "+field)
    risk=spec.get("risk",{})
    if not isinstance(risk,dict): raise ValueError("Risk must be an object")
    for field in ["stop_atr","take_atr","max_hold_bars"]:
        if field not in risk: raise ValueError("Missing explicit risk field: "+field)
    for field in ["stop_atr","take_atr"]:
        if risk[field] is not None and (not isinstance(risk[field],(int,float)) or not 0<risk[field]<=20):
            raise ValueError("Invalid risk parameter")
    hold=risk["max_hold_bars"]
    if hold is not None and (type(hold)!=int or not 1<=hold<=10000): raise ValueError("Invalid holding period")
    for field in ["stop_pct","take_pct"]:
        value=risk.get(field)
        if value is not None and (not isinstance(value,(int,float)) or not 0<value<1): raise ValueError("Invalid percentage exit")
    if risk.get("stop_atr") and risk.get("stop_pct") or risk.get("take_atr") and risk.get("take_pct"):
        raise ValueError("Ambiguous mixed exit levels")
    if risk.get("stop_atr") or risk.get("take_atr"):
        if type(risk.get("atr_period"))!=int or not 1<=risk["atr_period"]<=500 or risk.get("atr_method") not in {"wilder","sma","ema"}:
            raise ValueError("Source ATR period/smoothing must be explicit")
    # No inventing a 1:1 ATR bracket where the source had different exits.
    if not any(risk.get(f) for f in ["stop_atr","take_atr","stop_pct","take_pct","max_hold_bars"]) and not spec.get("signal_exit"):
        raise ValueError("No source-supported exit mechanism")
    audit_code(d["code"])
    return d

def immutable_default(node):
    if isinstance(node,ast.Constant):
        return node.value is None or type(node.value) in {bool,int,float,str}
    if isinstance(node,ast.Tuple): return all(immutable_default(item) for item in node.elts)
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
        return isinstance(node.operand,ast.Constant) and type(node.operand.value) in {int,float}
    return False

def audit_code(code):
    tree=ast.parse(code)
    funcs={n.name for n in tree.body if isinstance(n,ast.FunctionDef)}
    if not {"get_signals","get_exits"}.issubset(funcs): raise ValueError("Both get_signals and get_exits required")
    denied={"open","eval","exec","compile","__import__","getattr","setattr","delattr","globals","locals","input","breakpoint"}
    attrs={"to_csv","to_pickle","to_json","to_sql","read_csv","read_pickle","read_json","load","save","savez","memmap","ctypes","system","popen","eval","exec","compile","fromfile","tofile","random","testing","f2py"}
    for n in tree.body:
        if isinstance(n,ast.Import):
            if any(a.name not in {"numpy","pandas"} for a in n.names): raise ValueError("Only numpy/pandas imports allowed")
        elif not isinstance(n,(ast.FunctionDef,ast.Expr)) or isinstance(n,ast.Expr) and not isinstance(n.value,ast.Constant):
            raise ValueError("No module-level executable statements")
    for n in ast.walk(tree):
        if isinstance(n,(ast.ImportFrom,ast.ClassDef,ast.While,ast.Global,ast.Nonlocal,ast.AsyncFunctionDef)):
            raise ValueError("Unsupported generated construct: "+type(n).__name__)
        if isinstance(n,ast.Import) and any(a.name not in {"numpy","pandas"} for a in n.names): raise ValueError("Unsupported import")
        if isinstance(n,ast.Attribute) and (n.attr.startswith("_") or n.attr in attrs or n.attr.startswith("read_")): raise ValueError("Unsafe attribute")
        if isinstance(n,ast.Name) and (n.id.startswith("__") or n.id in denied): raise ValueError("Unsafe name")
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="shift" and n.args:
            try:
                if ast.literal_eval(n.args[0])<0: raise ValueError("Negative shift is noncausal")
            except (TypeError,SyntaxError): pass
        if isinstance(n,ast.FunctionDef):
            defaults=n.args.defaults+[d for d in n.args.kw_defaults if d is not None]
            if n.decorator_list or not all(immutable_default(d) for d in defaults):
                raise ValueError("No decorators, mutable or evaluated defaults")
            if any(isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id==n.name for x in ast.walk(n)): raise ValueError("No recursion")
    return tree

def restricted_module(code):
    tree=audit_code(code)
    # Imports have already been vetted; remove them and provide numeric modules.
    for parent in ast.walk(tree):
        if hasattr(parent,"body") and isinstance(parent.body,list):
            parent.body=[n for n in parent.body if not isinstance(n,ast.Import)]
    import builtins
    safe={n:getattr(builtins,n) for n in ["abs","all","any","bool","dict","enumerate","float","int","len","list","max","min","range","round","sum","tuple","zip","ValueError","TypeError"]}
    ns={"np":np,"pd":pd,"numpy":np,"pandas":pd,"__builtins__":safe}
    exec(compile(tree,"validated_strategy","exec"),ns)
    return ns

def normalize_signals(pair,n,allow_both=False):
    if not isinstance(pair,(tuple,list)) or len(pair)!=2: raise ValueError("Expected two signal arrays")
    output=[]
    for v in pair:
        a=np.asarray(v)
        if a.shape!=(n,) or a.dtype.kind!="b": raise ValueError("Signals must be one-dimensional boolean arrays")
        output.append(a)
    if not allow_both and np.any(output[0]&output[1]): raise ValueError("Conflicting long/short signals")
    return output

def causal_check(ns,df):
    for name in ["get_signals","get_exits"]:
        baseline=normalize_signals(ns[name](df.copy(deep=True)),len(df),name=="get_exits")
        again=normalize_signals(ns[name](df.copy(deep=True)),len(df),name=="get_exits")
        if any(not np.array_equal(a,b) for a,b in zip(baseline,again)): raise ValueError("Nondeterministic signals")
        for cutoff in sorted(set([len(df)//3, len(df)//2, 2*len(df)//3, len(df)-8])):
            prefix=normalize_signals(ns[name](df.iloc[:cutoff].copy()),cutoff,name=="get_exits")
            if any(not np.array_equal(a[:cutoff],b) for a,b in zip(baseline,prefix)): raise ValueError("Prefix causality check failed: "+name)
            changed=df.copy(deep=True)
            for column in ["open","high","low","close","volume","quote_volume","trades","taker_buy_base","taker_buy_quote"]:
                if column in changed:
                    future=changed[column].iloc[cutoff:]*1.23+7
                    if pd.api.types.is_integer_dtype(changed[column].dtype): future=future.round().astype(changed[column].dtype)
                    changed.loc[changed.index[cutoff:],column]=future
            poisoned=normalize_signals(ns[name](changed),len(df),name=="get_exits")
            if any(not np.array_equal(a[:cutoff],b[:cutoff]) for a,b in zip(baseline,poisoned)): raise ValueError("Future perturbation failed: "+name)
    if not any(normalize_signals(ns["get_signals"](df.copy()),len(df))[i].any() for i in [0,1]): raise ValueError("No entry signals")

def evaluate_isolated(code,df,check=False,timeout=45):
    """Resource-limited worker; this is not an OS security sandbox."""
    audit_code(code)
    with tempfile.TemporaryDirectory(prefix="strategy-eval-") as d:
        d=Path(d); (d/"code.py").write_text(code,encoding="utf-8"); df.to_pickle(d/"frame.pkl")
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),"worker",str(d),str(int(check))],capture_output=True,text=True,timeout=timeout,env={k:v for k,v in os.environ.items() if k not in {"MINIMAX_API_KEY","TAVILY_API_KEY","SUPABASE_KEY","SUPABASE_SERVICE_ROLE_KEY"}})
        if result.returncode: raise ValueError("Strategy evaluation rejected: "+result.stderr[-1200:])
        with np.load(d/"signals.npz") as arrays: return tuple(arrays[k].copy() for k in ["ls","ss","le","se"])

def worker(directory,check):
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(35,40))
        resource.setrlimit(resource.RLIMIT_FSIZE,(100_000_000,100_000_000))
    except ImportError: pass
    d=Path(directory); ns=restricted_module((d/"code.py").read_text()); df=pd.read_pickle(d/"frame.pkl")
    if check: causal_check(ns,df)
    ls,ss=normalize_signals(ns["get_signals"](df.copy()),len(df)); le,se=normalize_signals(ns["get_exits"](df.copy()),len(df),True)
    np.savez(d/"signals.npz",ls=ls,ss=ss,le=le,se=se)

if __name__=="__main__" and len(sys.argv)>1 and sys.argv[1]=="worker":
    worker(sys.argv[2],bool(int(sys.argv[3])))
