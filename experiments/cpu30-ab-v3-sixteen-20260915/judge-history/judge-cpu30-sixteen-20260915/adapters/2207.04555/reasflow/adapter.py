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

sys.path.insert(0,str(WORK/"src"))
from reproduction import algorithms as alg
if VARIANT=="codex":
    from reproduction.model import QuadraticProblem
else:
    from reproduction.model import SyntheticProblem
fn=alg.apdg

def run(case):
    inp,p=case["inputs"],case["parameters"]
    q,c=np.asarray(inp["q"],dtype=float),np.asarray(inp["c"],dtype=float)
    if VARIANT=="codex":
        problem=QuadraticProblem(2,2,1)
        problem.theta=1.0
        problem.C=np.asarray([np.diag(np.sqrt(block-1.0)) for block in q.reshape(2,2)])
        problem.d=(-c/np.sqrt(q-1.0)).reshape(2,2)
        problem._hessians=np.asarray([np.diag(block) for block in q.reshape(2,2)])
        problem._rhs=-c.reshape(2,2)
        problem.B=np.vstack([np.asarray(inp["B"],dtype=float),np.zeros((1,2))])
        problem.W=np.asarray(inp["network"]["W"],dtype=float)
        problem.gamma=p["gamma_constraint_scale"]
        # Embed rectangular B in the source's square B with one zero row per worker.
        dual_indices=np.asarray([0,2,4,5,6,7])
        y0=np.zeros(8);y0[dual_indices]=inp["y0"]
        loopline=line_of(fn,"for _ in range")
        snapshotline=line_of(fn,"objective_error.append")
        names={"x":"x","y":"y","x_f":"x_f","y_f":"y_f","y_m_used":"y_m","x_g_used":"x_g","y_g_used":"y_g"}
    else:
        problem=SyntheticProblem(2,2,1)
        problem.Q=np.diag(q);problem.q=-c
        problem.theta=1.0;problem.bC=np.diag(np.sqrt(q-1.0));problem.bd=-c/np.sqrt(q-1.0)
        problem.A=np.asarray(inp["A"],dtype=float);problem.ATA=problem.A.T@problem.A
        dual_indices=np.arange(6);y0=np.asarray(inp["y0"],dtype=float)
        loopline=line_of(fn,"for _ in range")
        snapshotline=line_of(fn,"f_errors.append")
        ygline=line_of(fn,"del yg")
        names={"x":"x","y":"y","x_f":"xf","y_f":"yf","y_m_used":"ym","x_g_used":"xg"}
    values={};injected=False;count=0;effective={}
    def trace(frame,event,arg):
        nonlocal injected,count
        if frame.f_code is fn.__code__ and event=="line":
            f=frame.f_locals
            if frame.f_lineno==loopline and not injected:
                for name in (["x","x_f"] if VARIANT=="codex" else ["x","xf"]):f[name][:]=inp["x0"]
                for name in (["y","y_f","y_previous"] if VARIANT=="codex" else ["y","yf","yprev"]):f[name][:]=y0
                effective.update({key:float(f[key]) for key in ["eta_x","eta_y","alpha_x","beta_x","beta_y","tau_x","tau_y","sigma_x","sigma_y","theta"]})
                injected=True
            if VARIANT=="reasflow" and frame.f_lineno==ygline:values[(count+1,"y_g_used")]=f["yg"].copy()
            if frame.f_lineno==snapshotline:
                count+=1
                for name,local in names.items():
                    val=f[local]
                    values[(count,name)]=(val[dual_indices] if name.startswith("y") else val).copy()
                values[(count,"constraint_Ax")]=(problem.a_apply(f["x"])[dual_indices] if VARIANT=="codex" else problem.A@f["x"]).copy()
                # Observation of the public objective at the original algorithm's x.
                values[(count,"objective")]=float(np.sum(0.5*q*f["x"]**2+c*f["x"]))
        return trace
    old=sys.gettrace();sys.settrace(trace)
    try:
        if VARIANT=="codex":
            params=((p["eta_x"],p["alpha_x"],p["beta_x"],p["tau_x"],p["sigma_x"]),(p["theta"],p["eta_y"],0.0,p["beta_y"],p["tau_y"],p["sigma_y"]))
            fn(problem,max_iterations=p["updates"],tolerance=0.0,params=params)
        else:fn(problem,max_iter=p["updates"],tolerance=0.0)
    finally:sys.settrace(old)
    result=packed(case,{})
    result.update(status="blocked",reason="Original apdg has no public parameter interface and forcibly uses spectral tuning, including sigma_y=1 instead of requested 0.9. No requested-parameter trajectory is available.")
    result["diagnostics"]={"source_tuned_trajectory":packed(case,values)["observations"],"effective_parameters":effective,"unsupported_parameters":{key:p[key] for key in effective if effective[key]!=p[key]}}
    return result
print("OPTIREPRO_OBSERVATIONS="+json.dumps({"cases":[run(c) for c in CASES]}))
