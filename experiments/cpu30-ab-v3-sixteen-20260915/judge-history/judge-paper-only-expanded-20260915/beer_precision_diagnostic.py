"""Post-freeze diagnostic ONLY: never writes the official contract or adapter.
Evaluate the paper recurrence under the precision/order exposed by original source.
Not an adapter and not a new oracle: comparison does not change official verdict.
"""
from pathlib import Path
import json
import hashlib
import numpy as np

ROOT=Path(__file__).resolve().parent
CONTRACT=ROOT/'papers/2201.13320/contract.json'
ADAPTER=ROOT/'adapters/beer/reasflow/adapter.py'
row=json.loads(next((ROOT/'validation').glob('*/beer-reasflow-1.row.json')).read_text())
source=Path(row['workspace'])/'beer_repro/core.py'
protected=[CONTRACT,ADAPTER,source,Path(row['result'])]
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
c=json.loads(CONTRACT.read_text())
result=json.loads(Path(row['result']).read_text())
checks=result['comparison']['checks']

def diagnose(case,state_dtype):
    inp,par=case['inputs'],case['parameters']
    centers=np.asarray(inp['quadratic_centers_by_client'],dtype=np.float64)
    diagonal=np.asarray(inp['quadratic_diagonals_by_client'],dtype=np.float64)
    W=np.asarray(inp['mixing_matrix_W'],dtype=np.float64)
    x=np.tile(np.asarray(inp['initial_common_point'],dtype=state_dtype),(len(centers),1))
    def grad(p): return (diagonal*(p-centers)).astype(state_dtype)
    def C(p):
        if par['compressor']['name']=='scale': return p*par['compressor']['factor'],None
        y=np.zeros_like(p); index=int(np.argmax(np.abs(p)));y[index]=p[index]
        return y,index
    h=np.zeros_like(x); v=grad(x);g=np.zeros_like(x)
    trace=[];supports=[]
    def save(): return {name:value.T.copy() for name,value in [('X',x),('H',h),('V',v),('G',g)]}
    trace.append(save())
    for step in range(1,par['iterations']+1):
        old_x=x.copy()
        old_gradient=grad(old_x)
        # First model phase is in-place float32 in the source. Later model
        # candidates promote through float64 W; H consumes candidate before X cast.
        if step==1:
            candidate=x.copy();candidate-=par['eta']*v
        else:
            candidate=x+par['gamma']*(W@h-h)-par['eta']*v
        chosen_h=[]
        for i in range(len(centers)):
            msg,idx=C(candidate[i]-h[i]);h[i]+=msg;chosen_h.append(idx)
        x=candidate.astype(state_dtype,copy=False)
        new_gradient=grad(x)
        # Grouping follows original arithmetic, while the real-valued formula is
        # exactly Algorithm 1: V + gamma*G*(W-I) + gradnew - gradold.
        v+=par['gamma']*(W@g-g)+new_gradient-old_gradient
        chosen_g=[]
        for i in range(len(centers)):
            msg,idx=C(v[i]-g[i]);g[i]+=msg;chosen_g.append(idx)
        supports.append({'step':step,'H':chosen_h,'G':chosen_g})
        trace.append(save())
    return trace,supports

summary={'official_status':result['status'],'numpy_version':np.__version__,'description':'Post-freeze diagnostic; official tolerance and verdict unchanged.','cases':[],'failures':[]}
for case in c['cases']:
    diag32,support32=diagnose(case,np.float32)
    diag64,support64=diagnose(case,np.float64)
    actuals=[item for item in checks if item['case_id']==case['id']]
    residual32=[];residual64=[];reference64=[];exact_actual_matches=0
    for item in actuals:
        j,i=item['path'];step=item['step'];name=item['name']
        d32=float(diag32[step][name][j,i]);d64=float(diag64[step][name][j,i])
        residual32.append(abs(d32-item['actual']))
        residual64.append(abs(d64-item['actual']))
        reference64.append(abs(d64-item['expected']))
        exact_actual_matches+=int(d32==item['actual'])
        if not item['passed']:
            ulp=float(abs(np.spacing(np.float32(item['expected']))))
            summary['failures'].append(dict(item,diagnostic_float32=d32,diagnostic_float64=d64,
               float32_diagnostic_minus_actual=abs(d32-item['actual']),float32_ulp_at_reference=ulp,
               absolute_error_in_float32_ulps=item['difference']/ulp,
               exceeds_tolerance_by_factor=item['difference']/item['tolerance']))
    summary['cases'].append({'id':case['id'],'numeric_checks':len(actuals),'exact_actual_matches_float32':exact_actual_matches,
       'max_abs_float32_diagnostic_minus_actual':max(residual32),
       'max_abs_float64_diagnostic_minus_exact_contract':max(reference64),
       'max_abs_actual_minus_float64_diagnostic':max(residual64),
       'same_compressor_supports_float32_float64':support32==support64,
       'supports':support32})
after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
assert before==after
summary['unchanged_protected_sha256']=after
(ROOT/'beer_precision_diagnostic.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2,ensure_ascii=False))
