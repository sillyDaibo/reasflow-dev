import inspect, json, os, sys
from pathlib import Path
import numpy as np
sys.dont_write_bytecode = True
VARIANT = "codex"
WORK=Path(os.environ["OPTIREPRO_WORKSPACE"])
PUBLIC=json.loads(Path(os.environ["OPTIREPRO_CASES"]).read_text())
if VARIANT == "codex":
    sys.path.insert(0,str(WORK))
    from src import algorithms as alg
    from src import wasserstein as objective
    gradient = objective.gradient_from_samples
    driver = alg.run_decentralized
else:
    sys.path.insert(0,str(WORK/"src"))
    from pps_barycenter import algorithms as alg
    from pps_barycenter import objectives as objective
    gradient = objective.local_distribution
    driver = alg.run_algorithm

def line_of(function, snippet):
    lines,start=inspect.getsourcelines(function)
    return next(start+i for i,line in enumerate(lines) if snippet in line)

def run(case):
    inputs,p=case["inputs"],case["parameters"]
    support=np.asarray(inputs["target_support"],dtype=float)
    samples=np.asarray(inputs["source_samples"],dtype=float)
    uniforms=np.asarray(inputs["pps_uniforms"],dtype=float)
    W=np.asarray(inputs["W"],dtype=float)
    nodes,dim=W.shape[0],support.size
    measured={}; diag={"source_oracle_inputs":[],"source_oracle_means":[],"source_pps_indices":[],"source_driver_states":[]}
    quant_calls=0; gradient_calls=0; sample_calls=0
    # This coordinate map represents exactly c=(y-xi)^2 through the native
    # squared_cost=(native_y-native_xi)^2/6.5; no source operation is replaced.
    scale=np.sqrt(6.5) if VARIANT=="codex" else 1.0
    native_support=support*scale
    saved_rng=np.random.default_rng
    class FixedPPS:
        def indices(self, probabilities, count):
            nonlocal quant_calls
            step,node=divmod(quant_calls,nodes)
            assert count==p["M"] and step<len(uniforms)
            selected=np.searchsorted(np.cumsum(probabilities),uniforms[step,node],side="right")
            assert np.all(selected<len(probabilities))
            diag["source_pps_indices"].append((selected+1).tolist())
            quant_calls+=1
            return selected
        def multinomial(self,n,pvals):
            return np.bincount(self.indices(pvals,n),minlength=len(pvals))
        def choice(self,n,size,replace,p):
            assert replace is True
            return self.indices(p,size)
    fixed=FixedPPS()
    old_draw=getattr(alg,"_draw_node_samples",None)
    def fixed_node_samples(node, dual, support, data, batch, rng):
        assert batch==p["r"]
        step=quant_calls//nodes
        interval=inputs["source_distributions"][node]["interval"]
        return samples[step,node,:,None].copy(),np.full(batch,-np.log(interval[1]-interval[0]))
    last_sample=None
    def sample_factory(rng,count):
        nonlocal sample_calls,last_sample
        if count==p["r"]:
            last_sample=samples[sample_calls]*scale;sample_calls+=1
            return last_sample.copy()
        # Native diagnostic metrics request 32 samples; give repeated fixed
        # realizations without advancing the declared optimization sample stream.
        assert last_sample is not None
        return np.resize(last_sample,(nodes,count))
    if VARIANT=="codex":
        before_loop=line_of(driver,'for t in range(iterations):')
        after_update=line_of(driver,'if (t + 1) % record_every')
    else:
        before_loop=line_of(driver,'history = {')
        after_update=line_of(driver,'should_eval =')
    means=[]; mus=[]
    def trace(frame,event,arg):
        nonlocal gradient_calls
        if frame.f_code is gradient.__code__:
            if event=="call":
                value=frame.f_locals['lambdas' if VARIANT=="codex" else 'dual']
                diag['source_oracle_inputs'].append(np.asarray(value).tolist())
                if gradient_calls < (1 if VARIANT=="codex" else nodes): mus.append(np.asarray(value).copy())
            if event=="return":
                diag['source_oracle_means'].append(np.asarray(arg).tolist())
                if gradient_calls < (1 if VARIANT=="codex" else nodes): means.append(np.asarray(arg).copy())
                gradient_calls+=1
        if frame.f_code is driver.__code__ and event=="line":
            f=frame.f_locals
            if frame.f_lineno==before_loop and (0,'mu') not in measured:
                measured[0,'mu']=mus[0] if VARIANT=='codex' else np.asarray(mus)
                measured[0,'oracle_mean']=means[0] if VARIANT=='codex' else np.asarray(means)
                measured[0,'pps_indices']=np.asarray(diag['source_pps_indices'][:nodes])
                measured[0,'quantized_gradient']=f['transmitted'].copy() if VARIANT=='codex' else f['gradients'].T.copy()
                if VARIANT=='reasflow': measured[0,'graph_gradient']=f['mixed'].T.copy()
            if frame.f_lineno in (before_loop,after_update):
                keys=('alpha','beta','cumulative_weight','lambdas','weighted_gradient','z','mu','chi') if VARIANT=='codex' else ('alpha','beta','A','dual','weighted_gradients','z','mu','hat_mu')
                diag['source_driver_states'].append({k:np.asarray(f[k]).tolist() for k in keys if k in f})
        return trace
    old_trace=sys.gettrace()
    try:
        if VARIANT=='codex':
            np.random.default_rng=lambda seed=None: fixed if seed==1235 else saved_rng(seed)
        else:
            np.random.default_rng=lambda seed=None: fixed
            alg._draw_node_samples=fixed_node_samples
        sys.settrace(trace)
        if VARIANT=='codex':
            result=driver(means=np.zeros(nodes),stds=np.ones(nodes),support=native_support,laplacian=W,gamma=p['gamma'],iterations=p['T'],batch_size=p['r'],quantization_samples=p['M'],seed=1234,quantized=True,record_every=p['T']+1,sample_factory=sample_factory)
        else:
            result=driver({'nodes':nodes,'iterations':p['T'],'gamma':p['gamma'],'cost_scale':1.0,'r':p['r'],'M':p['M'],'topology':'path','seed':1234,'evaluate_every':p['T']+1},{'kind':'fixed_public_uniform_samples'},native_support[:,None])
    finally:
        sys.settrace(old_trace);np.random.default_rng=saved_rng
        if VARIANT=='reasflow':alg._draw_node_samples=old_draw
    assert gradient_calls==(p['T']+1)*(1 if VARIANT=='codex' else nodes)
    assert quant_calls==(p['T']+1)*nodes
    reason='The driver fixes alpha/beta internally and cannot express the public schedules. Only initial oracle/PPS (and an actual stored initial graph product when available) are comparable; all schedule-dependent and later source states are diagnostics only.'
    observations=[{'step':s['step'],'name':s['name'],'value':np.asarray(measured[s['step'],s['name']]).tolist()} for s in case['observation_schema'] if (s['step'],s['name']) in measured]
    missing=[s for s in case['observation_schema'] if (s['step'],s['name']) not in measured]
    return {'id':case['id'],'status':'blocked','reason':reason,'missing_observations':missing,'observations':observations,'diagnostics':diag}
print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':[run(c) for c in PUBLIC['cases']]}))
