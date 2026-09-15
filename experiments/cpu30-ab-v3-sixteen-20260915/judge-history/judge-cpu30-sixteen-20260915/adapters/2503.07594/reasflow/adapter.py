import sys,os,json
sys.dont_write_bytecode=True
from pathlib import Path
import numpy as np
W=Path(os.environ['OPTIREPRO_WORKSPACE']);sys.path.insert(0,str(W))
import scaffold_speedup.algorithms as m
from scaffold_speedup.data import ClientData
def solve(c):
    i,p=c['inputs'],c['parameters']; H=p['H']; R=p['rounds']; N=i['clients']
    a=np.array(i['quadratic_a'],float); b=np.array(i['quadratic_b'],float)
    X=np.repeat(np.sqrt(a)[:,None,None],2,axis=1)
    y=-(b[:,None]+np.array([-.25,.25])[None,:])/np.sqrt(a)[:,None]
    class RNG:
        k=0
        def integers(self,lo,hi,size):
            t,h=divmod(self.k,H);self.k+=1
            return (np.asarray(i['noise'][t][h])>0).astype(int)[:,None]
    old_rng=m.np.random.default_rng;m.np.random.default_rng=lambda *a,**kw:RNG()
    rows=[]; states=[]; samples=[]; corrected=[]; epoch={}
    def emit(name,val): rows.append({'step':epoch['round']+1,'name':name,'value':np.asarray(val).tolist()})
    original=m._batch_gradient
    def gradient(*args):
        states.append(args[2].copy().ravel())
        g=original(*args);samples.append(g.copy().ravel());return g
    m._batch_gradient=gradient
    def trace(f,event,arg):
        if f.f_code is m.scaffold.__code__ and event=='line':
            if f.f_lineno==130: f.f_locals['controls'][:]=np.array(i['xi_initial'])[:,None]
            if f.f_lineno==135:
                epoch['round']=f.f_locals['round_idx']
                emit('theta_before',f.f_locals['theta'][0]);emit('xi_before',f.f_locals['controls'].ravel())
            if f.f_lineno==143: corrected.append((f.f_locals['gradient']+f.f_locals['controls']).ravel().copy())
            if f.f_lineno==144:
                emit('local_theta',np.vstack([states[-H:],f.f_locals['local'].ravel()]))
                emit('sample_gradient',samples[-H:]);emit('corrected_gradient',corrected[-H:])
            if f.f_lineno==146:
                emit('theta_after',f.f_locals['theta'][0]);emit('xi_after',f.f_locals['controls'].ravel())
        return trace
    try:
        sys.settrace(trace)
        m.scaffold(ClientData(X,y,'linear'),np.array([i['theta_initial']],float),step=p['gamma'],lambda_=0.,batch_size=1,n_local=H,n_rounds=R)
    finally:
        sys.settrace(None);m._batch_gradient=original;m.np.random.default_rng=old_rng
    return {'id':c['id'],'observations':rows}
print('OPTIREPRO_OBSERVATIONS='+json.dumps({'cases':[solve(c) for c in json.load(open(os.environ['OPTIREPRO_CASES']))['cases']]}))
