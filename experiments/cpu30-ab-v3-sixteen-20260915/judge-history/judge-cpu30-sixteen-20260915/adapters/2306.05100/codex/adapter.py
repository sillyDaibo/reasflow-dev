import os, sys, json, inspect
from pathlib import Path
sys.dont_write_bytecode = True
import numpy as np
WORK = Path(os.environ["OPTIREPRO_WORKSPACE"])
CASES = json.load(open(os.environ["OPTIREPRO_CASES"]))["cases"]
def packed(case, values, reason=None):
    obs = [{"step": s["step"], "name": s["name"], "value": np.asarray(values[(s["step"],s["name"])]).tolist()} for s in case["observation_schema"] if (s["step"],s["name"]) in values]
    result={"id":case["id"],"observations":obs}
    missing=[s for s in case["observation_schema"] if (s["step"],s["name"]) not in values]
    if missing: result.update(status="blocked",reason=reason or "Original routine did not expose all requested states",missing_observations=missing)
    return result
def line_of(fn, text):
    lines,start=inspect.getsourcelines(fn)
    return next(start+i for i,line in enumerate(lines) if text in line)
class BudgetEnd(Exception): pass
VARIANT='codex'

sys.path.insert(0,str(WORK / ("src" if VARIANT=="reasflow" else "")))
if VARIANT=="codex":
    from proxskip_vip import algorithms as alg
    from proxskip_vip.games import LinearFiniteSumVIP
    fn=alg.proxskip_fl
else:
    from vip_repro import algorithms as alg
    from vip_repro.problems import AffineVIP
    fn=alg.proxskip

def run(case):
    inp,p=case["inputs"],case["parameters"]
    matrices=np.asarray(inp["operator_matrices"],dtype=float)[:,None]
    offsets=np.asarray(inp["operator_offsets"],dtype=float)[:,None]
    problem=LinearFiniteSumVIP(matrices,offsets) if VARIANT=="codex" else AffineVIP(matrices,offsets,"public",{})
    coins=iter(inp["communication_coins"])
    class RNG:
        def random(self): return 0.0 if next(coins) else 1.0
    values={}; gradients=[]; injected=False; seen=0
    loopline=line_of(fn,"while ")
    gline=line_of(fn,"xhat[i] =")
    def trace(frame,event,arg):
        nonlocal injected,seen
        if frame.f_code is not fn.__code__: return trace
        if event=="line":
            f=frame.f_locals
            if frame.f_lineno==loopline:
                if not injected:
                    f["h"][:]=np.asarray(inp["h0"],dtype=float)
                    f["rng"]=RNG()
                    injected=True
                else:
                    s=f["local_steps" if VARIANT=="codex" else "iterations"]
                    if s>seen:
                        x=f["x_clients" if VARIANT=="codex" else "clients"]
                        for name,val in [("operator_used",gradients),("x_hat",f["xhat"]),("x",x),("h",f["h"]),("mean_x",x.mean(axis=0)),("communication_count",f["communications" if VARIANT=="codex" else "communication"])]:
                            values[(s,name)]=np.asarray(val).copy()
                        gradients.clear();seen=s
                    if seen>=p["number_of_updates"]: raise BudgetEnd()
            if frame.f_lineno==gline: gradients.append(f["g"].copy())
        return trace
    old=sys.gettrace();sys.settrace(trace)
    try:
        if VARIANT=="codex":
            fn(np.asarray(inp["x0"],dtype=float)[0],len(inp["x0"]),sum(inp["communication_coins"])+1,p["gamma"],p["p"],problem.operator,problem.relative_error,max_local_steps=p["number_of_updates"]+1)
        else:
            fn(problem,sum(inp["communication_coins"])+1,p["gamma"],p["p"],0,x0=np.asarray(inp["x0"],dtype=float)[0])
    except BudgetEnd: pass
    finally: sys.settrace(old)
    return packed(case,values)
print("OPTIREPRO_OBSERVATIONS="+json.dumps({"cases":[run(c) for c in CASES]}))
