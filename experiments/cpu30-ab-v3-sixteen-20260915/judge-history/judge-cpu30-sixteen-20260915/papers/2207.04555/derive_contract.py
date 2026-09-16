"""Paper-only APDG arithmetic. No repository implementation or observations are inputs."""
from fractions import Fraction as F
import hashlib,json
from pathlib import Path

def V(x): return [F(str(a)) for a in x]
def add(x,y): return [a+b for a,b in zip(x,y)]
def sub(x,y): return [a-b for a,b in zip(x,y)]
def mul(a,x): return [a*b for b in x]
def mv(a,x): return [sum(v*w for v,w in zip(row,x)) for row in a]
def transpose(a): return list(zip(*a))
def numeric(x): return [numeric(a) for a in x] if isinstance(x,(list,tuple)) else float(x)

def build_case(id,x0,w0,q,c,gamma):
    q,c,x,w=map(V,(q,c,x0,w0)); gamma=F(str(gamma))
    A=[[F(1),F(0),F(0),F(0)],[F(0),F(0),F(1),F(0)],
       [gamma,0,-gamma,0],[0,gamma,0,-gamma],[-gamma,0,gamma,0],[0,-gamma,0,gamma]]
    AT=transpose(A); y=mv(A,w); yold=y[:]; xf=x[:]; yf=y[:]
    params={'eta_x':0.05,'eta_y':0.1,'alpha_x':1,'beta_x':0.5,'beta_y':0.25,'tau_x':0.6,'tau_y':0.7,'sigma_x':0.8,'sigma_y':0.9,'theta':0.4,'gamma_constraint_scale':float(gamma),'updates':3}
    ex,trace=[],[]
    def put(k,n,v):
      ex.append({'step':k,'name':n,'value':numeric(v)}); trace.append(f'{k}:{n}={v}')
    for k in range(3):
      ym=add(y,mul(F('0.4'),sub(y,yold)))
      xg=add(mul(F('0.6'),x),mul(F('0.4'),xf)); yg=add(mul(F('0.7'),y),mul(F('0.3'),yf))
      grad=add([a*b for a,b in zip(q,xg)],c)
      xn=sub(sub(add(x,mul(F('0.05'),sub(xg,x))),mul(F('0.025'),mv(AT,mv(A,x)))),mul(F('0.05'),add(grad,mv(AT,ym))))
      yn=add(sub(y,mul(F('0.025'),mv(A,add(mv(AT,y),grad)))),mul(F('0.1'),mv(A,xn)))
      xfn=add(xg,mul(F('0.8'),sub(xn,x))); yfn=add(yg,mul(F('0.9'),sub(yn,y)))
      for name,value in [('y_m_used',ym),('x_g_used',xg),('y_g_used',yg),('x',xn),('y',yn),('x_f',xfn),('y_f',yfn),('constraint_Ax',mv(A,xn)),('objective',sum(a*b*b/2+d*b for a,b,d in zip(q,xn,c)))]: put(k+1,name,value)
      x,xf,yold,y,yf=xn,xfn,y,yn,yfn
    return {'id':id,'purpose':'Check the unpreconditioned affine-constrained decentralized APDG recursion, including distinct extrapolated and fast states.','covers':['dual_extrapolation','primal_dual_coupling','fast_state_updates'],
      'inputs':{'network':{'nodes':2,'edges':[[0,1]],'W':[[1,-1],[-1,1]]},'local_dimension':2,'B':[[1,0]],'objective':'F(x)=sum_j (q_j*x_j^2/2+c_j*x_j); flattened x=[node0_coord0,node0_coord1,node1_coord0,node1_coord1].','q':numeric(q),'c':numeric(c),'x0':x0,'y0':numeric(mv(A,w)),'A':numeric(A),'dual_order':'First two rows are (I_2 tensor B), last four rows gamma*(W tensor I_2).','initialization':'x_f^0=x0; y_f^0=y^{-1}=y0. Both range restrictions in Algorithm 1 hold; y0=A*w0.','randomness':'None; full local gradients.','observations':'step s=k+1: *_used are the extrapolates formed at the start of iteration k; x,y,x_f,y_f and Ax are after completing lines 8-11; objective is evaluated at updated x.'},
      'parameters':params,'atol':1e-10,'rtol':1e-10,'expected':ex,
      'derivation':'Algorithm 1, PDF p.5 lines 5-11, applied in printed order. All arithmetic uses exact rational Fraction values, rounded once to binary64 for JSON. A=[I tensor B; gamma W tensor I]. '+ '\n'.join(trace)}

def build():
 return {'schema_version':'optirepro.paper_algorithm_contract.v1','paper':{'paper_id':'2207.04555','title':'Decentralized Strongly-Convex Optimization with Affine Constraints: Primal and Dual Approaches','sha256':'14ec04ecc551e5f2285d3987575179d88a59769d9a9e1b725b776830f48ac0c1'},'algorithm':{'name':'Algorithm 1 APDG (unpreconditioned primal approach)','citations':['PDF p.4, problem (3) and Assumption 2','PDF p.5, problem (4) and Algorithm 1 lines 1-11'],'core_mechanisms':['dual_extrapolation','primal_dual_coupling','fast_state_updates'],'assumptions':['Local smooth strongly convex quadratics; deterministic gradients.','Connected two-node graph, common affine B*x_i=0, consensus W*x=0.','Parameters satisfy Algorithm 1 input domains; no claim of using theorem-optimal parameter tuning or verifying asymptotic rates.','No Chebyshev preconditioning and no claims about the distinct globally/locally dual approaches.']},'cases':[build_case('apdg_gamma_one',[1,2,-1,-2],[1,1,0,-1],[2,3,4,5],[-1,2,3,-2],1),build_case('apdg_scaled_constraints',[-2,1,3,-1],[0,2,1,-1],[3,2,5,4],[2,-3,-1,1],0.5)]}
if __name__=='__main__':
 Path(__file__).with_name('contract.json').write_text(json.dumps(build(),indent=2,ensure_ascii=False)+'\n')
