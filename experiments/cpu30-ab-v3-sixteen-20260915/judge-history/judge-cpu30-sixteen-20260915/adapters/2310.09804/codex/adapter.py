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

sys.path.insert(0,str(WORK/"src"))
if VARIANT=="codex":
    from byz_repro import algorithms as alg, aggregation as agg
    fn=alg._run_dasha
    bucketfn=agg._buckets
else:
    from byz_compression import core as alg
    from scipy.sparse import csr_matrix
    fn=alg.run
    bucketfn=alg.coordinate_median_bucket
original_randk=alg.randk

def run(case):
    inp,p=case["inputs"],case["parameters"]
    q=np.asarray(inp["q"],dtype=float);b=np.asarray(inp["b"],dtype=float)
    fq=q.reshape(-1,2);fb=b.reshape(-1,2)
    values={}; compin=[]; messages=[]; buckets=None
    class RNG:
        stage=0; sample=0; keep=0; perm=0
        def random(self):
            result=0.0 if inp["page_coins"][self.stage] else 1.0
            self.stage+=1;self.sample=0;self.keep=0
            return result
        def permutation(self,n):
            result=np.asarray(inp["bucket_permutations"][self.perm]);self.perm+=1
            assert len(result)==n
            return result
        def choice(self,a,size,replace=False):
            assert size==1 and replace is False
            if inspect.currentframe().f_back.f_code is original_randk.__code__:
                j=inp["rand1_kept_coordinate"][self.stage-1][self.keep];self.keep+=1
                return np.asarray([j])
            j=inp["sampled_component_indices"][self.stage-1][self.sample];self.sample+=1
            return np.asarray([j if np.isscalar(a) else a[j]])
    rng=RNG()
    def gradient(x,ids):
        ids=np.asarray(ids,dtype=int)
        return (fq[ids]*x+fb[ids]).mean(axis=0)
    def loss(x): return float((0.5*fq*x*x+fb*x).sum(axis=1).mean())
    def compress(*args,**kwargs):
        compin.append(np.asarray(args[0]).copy())
        result=original_randk(*args,**kwargs)
        messages.append((result[0] if VARIANT=="codex" else result).copy())
        return result
    def malicious(*args,**kwargs):
        result=np.asarray(inp["byzantine_g_states"][rng.stage],dtype=float)
        return result[None,:] if VARIANT=="codex" else result
    alg.randk=compress
    if VARIANT=="codex":
        class Objective:
            dimension=2
            def grad(self,x,rows=None): return gradient(x,np.arange(10) if rows is None else rows)
            def batch_gradient(self,x,rows,batch_size,rng,labels=None):
                assert batch_size==len(rows)
                return self.grad(x,rows)
            def loss(self,x): return loss(x)
        problem=Objective()
        old_attack=alg._attack_vectors;alg._attack_vectors=malicious
        rngline=line_of(fn,"x = np.asarray")
        snapshotline=line_of(fn,"iters.append(step + 1)")
    else:
        problem=alg.Dataset("public",csr_matrix((10,2)),np.arange(10))
        old_grad,old_loss,old_attack=alg.logistic_grad,alg.logistic_loss,alg.attack_vectors
        alg.logistic_grad=lambda x,features,labels,l2,setting: gradient(x,labels)
        alg.logistic_loss=lambda x,features,labels,l2,setting: loss(x)
        alg.attack_vectors=malicious
        rngline=line_of(fn,"dimension = effective.dimension")
        initialline=line_of(fn,"local = np.vstack(")
        firstaggline=line_of(fn,"aggregate_gradient = aggregate(local")
        snapshotline=line_of(fn,"if iteration % max")
    def trace(frame,event,arg):
        nonlocal buckets
        if frame.f_code is bucketfn.__code__ and event=="return":
            buckets=np.asarray(arg if VARIANT=="codex" else frame.f_locals["buckets"]).copy()
        if frame.f_code is fn.__code__ and event=="line":
            f=frame.f_locals
            if frame.f_lineno==rngline: f["rng"]=rng
            if VARIANT=="reasflow":
                if frame.f_lineno==initialline:f["x"][:]=np.asarray(inp["x0"],dtype=float)
                if frame.f_lineno==firstaggline:f["local"][5:]=np.asarray(inp["byzantine_g_states"][0],dtype=float)
            if frame.f_lineno==snapshotline:
                s=f["step"]+1 if VARIANT=="codex" else f["iteration"]
                data={"x":f["x"],"h_regular":f["h"] if VARIANT=="codex" else f["local_h"][:5],"compression_input_regular":compin,"message_regular":messages,"g_regular":f["local"][:5],"bucket_means":buckets,"g_aggregate":f["g"] if VARIANT=="codex" else f["aggregate_gradient"],"objective":loss(f["x"])}
                for name,val in data.items():values[(s,name)]=np.asarray(val).copy()
                compin.clear();messages.clear()
        return trace
    old_trace=sys.gettrace();sys.settrace(trace)
    try:
        if VARIANT=="codex":
            rows=[np.arange(2*i,2*i+2) for i in range(5)]+[np.arange(10)]
            fn(problem,np.asarray(inp["x0"],dtype=float),rows,6,1,"PUBLIC","cm",p["gamma"],p["a"],p["p"],0.5,p["updates"],1,0)
        else:
            config=alg.RunConfig(method="dasha-page",steps=p["updates"],num_workers=6,num_byzantine=1,batch_fraction=0.5,compression_fraction=0.5,aggregator="cm",bucket_size=2,gamma=p["gamma"])
            fn(config,problem)
    finally:
        sys.settrace(old_trace);alg.randk=original_randk
        if VARIANT=="codex":alg._attack_vectors=old_attack
        else:alg.logistic_grad,alg.logistic_loss,alg.attack_vectors=old_grad,old_loss,old_attack
    return packed(case,values)
print("OPTIREPRO_OBSERVATIONS="+json.dumps({"cases":[run(c) for c in CASES]}))
