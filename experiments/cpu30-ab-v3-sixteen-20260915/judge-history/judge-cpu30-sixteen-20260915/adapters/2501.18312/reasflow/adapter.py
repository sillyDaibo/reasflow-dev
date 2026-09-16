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
VARIANT='reasflow'

if VARIANT=="codex":
    sys.path.insert(0,str(WORK))
    from src.pps_quantization import pps_quantize
else:
    sys.path.insert(0,str(WORK/"src"))
    from pps_barycenter.pps import pps_quantize

def run(case):
    inp,p=case["inputs"],case["parameters"]
    q,c,a,b=[np.asarray(inp[k],dtype=float) for k in ["q","c","A_diagonal","b"]]
    mu=np.zeros_like(q)
    # Public deterministic conjugate oracle at its declared initial input only.
    oracle=b-a*(c-a/q*mu)
    selected=[]
    class RNG:
        def indices(self,probabilities,size):
            uniforms=inp["positive_uniforms" if not selected else "negative_uniforms"][0]
            assert len(uniforms)==size
            indices=np.searchsorted(np.cumsum(probabilities),uniforms,side="right")
            selected.append(indices.copy())
            return indices
        def multinomial(self,n,pvals):
            return np.bincount(self.indices(pvals,n),minlength=len(pvals))
        def choice(self,n,size,replace,p):
            assert replace is True
            return self.indices(p,size)
    actual={}
    def trace(frame,event,arg):
        if frame.f_code is pps_quantize.__code__:
            if event=="call": actual["input"]=np.asarray(frame.f_locals["vector"]).copy()
            if event=="return": actual["masses"]=[frame.f_locals["positive"].sum(),frame.f_locals["negative"].sum()]
        return trace
    old=sys.gettrace();sys.settrace(trace)
    try: result=pps_quantize(oracle,p["M"][0],RNG())
    finally: sys.settrace(old)
    values={(0,"oracle_g"):actual["input"],(0,"PPS_G"):result,
            (0,"positive_negative_mass"):actual["masses"],
            (0,"sampled_positive_indices"):selected[0],(0,"sampled_negative_indices"):selected[1]}
    return packed(case,values,"Only original signed PPS at mu0 is callable for this fixture. Workspace exposes barycenter Algorithm 3, not generic affine Algorithm 2; lambda and accelerated/primal-restoration states cannot be obtained without substituting the algorithm and its simplex quantizer.")
print("OPTIREPRO_OBSERVATIONS="+json.dumps({"cases":[run(c) for c in CASES]}))
