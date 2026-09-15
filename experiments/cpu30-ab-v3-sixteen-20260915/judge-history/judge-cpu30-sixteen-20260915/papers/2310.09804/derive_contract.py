"""Paper-only Byz-DASHA-PAGE with fixed supported random draws, exact fractions."""
from fractions import Fraction as F
import json
from pathlib import Path

def frac(x):return [frac(a) for a in x] if isinstance(x,list) else F(str(x))
def num(x):return [num(a) for a in x] if isinstance(x,list) else float(x)
def add(x,y):return [a+b for a,b in zip(x,y)]
def sub(x,y):return [a-b for a,b in zip(x,y)]
def mul(a,x):return [a*b for b in x]
def mean(xs):return [sum(c)/len(xs) for c in zip(*xs)]
def diagmv(q,x):return [a*b for a,b in zip(q,x)]

def case(id,x0,coins,samples,keep,bad,permutations):
 q=frac([[[i+1,i+2],[i+3,i+1]] for i in range(5)])
 b=frac([[[i-2,2-i],[1-i,i-1]] for i in range(5)])
 x=frac(x0);bad=frac(bad);a=F(1,3);gamma=F(1,50)
 def grad(i,z):return mean([add(diagmv(qi,z),bi) for qi,bi in zip(q[i],b[i])])
 def aggregate(local,attack,perm):
  allv=local+[attack]; buckets=[mean([allv[perm[j]],allv[perm[j+1]]]) for j in range(0,6,2)]
  return [sorted(col)[1] for col in zip(*buckets)],buckets
 h=[grad(i,x) for i in range(5)];g=[r[:] for r in h];g0=[r[:] for r in g]
 agg,_=aggregate(g,bad[0],permutations[0]);agg0=agg[:];ex=[];trace=[]
 for t,coin in enumerate(coins):
  xn=sub(x,mul(gamma,agg))
  hn=[grad(i,xn) if coin else add(h[i],diagmv(q[i][samples[t][i]],sub(xn,x))) for i in range(5)]
  delta=[sub(sub(hn[i],h[i]),mul(a,sub(g[i],h[i]))) for i in range(5)]
  msg=[[2*row[j] if j==keep[t][i] else F(0) for j in range(2)] for i,row in enumerate(delta)]
  gn=[add(g[i],msg[i]) for i in range(5)]
  aggn,buckets=aggregate(gn,bad[t+1],permutations[t+1])
  obj=sum(sum(sum(qij[k]*xn[k]*xn[k]/2+bij[k]*xn[k] for k in range(2)) for qij,bij in zip(qi,bi))/2 for qi,bi in zip(q,b))/5
  for name,value in [('x',xn),('h_regular',hn),('compression_input_regular',delta),('message_regular',msg),('g_regular',gn),('bucket_means',buckets),('g_aggregate',aggn),('objective',obj)]:
   ex.append({'step':t+1,'name':name,'value':num(value)});trace.append(f'{t+1}:{name}={value}')
  x,h,g,agg=xn,hn,gn,aggn
 return {'id':id,'purpose':'Exercise both PAGE refresh/difference branches, Rand-1 compression with nonzero momentum memory, and bucketed robust aggregation under a malicious worker.','covers':['page_estimator_recursion','dasha_momentum_compression','local_estimator_memory','byzantine_bucket_aggregation'],
 'inputs':{'network':'One synchronous server and 6 workers, indices 0..5; workers 0..4 honest, worker 5 Byzantine.','objective':'f=(1/5)*sum_i f_i over honest workers only; f_i=(f_i0+f_i1)/2, f_ij(x)=sum_k(q[i][j][k]*x[k]^2/2+b[i][j][k]*x[k]).','q':num(q),'b':num(b),'x0':x0,'h0_regular':num(g0),'g0_regular':num(g0),'initialization':'h_i^0=g_i^0=full local gradient at x0. Server g0 is computed by the specified bucketed median using Byzantine state at index 0 and permutation at index 0.','page_coins':coins,'sampled_component_indices':samples,'rand1_kept_coordinate':keep,'byzantine_g_states':num(bad),'bucket_permutations':permutations,'aggregator':'Algorithm 5 with bucket size s=2 and coordinatewise median: permute all 6 g_i states, average consecutive disjoint pairs, then take median separately in each coordinate over 3 pair means. No extra averaging.','oracle':'On refresh, full mean of two component gradients. Otherwise sample exactly one listed component j and set delta_hat_i=grad f_ij(x_next)-grad f_ij(x_old), same j at both points. Component indices are zero-based and ignored at refresh steps.','compressor':'Unbiased Rand-1 in d=2: keep exactly the listed coordinate and multiply it by 2; zero other coordinate. Uniform independent coordinate selection before conditioning.','randomness':'Fixed supported realizations: listed Bernoulli PAGE coins (p=1/2), uniform component indices, uniform compressor coordinates, and uniform permutations. All arrays chronological; rows of samples/keep cover five honest workers. Byzantine states include initialization plus each post-update state; a malicious increment may equivalently be chosen as consecutive state difference.','observations':'step s=t+1 after Algorithm 2 line 16. x uses previous server g; h is after lines 7-11; compression_input is the argument to Q in line 12; message is Q output; g_regular after line 13; bucket_means and g_aggregate come from current complete local states (not raw increments); objective at updated x.'},
 'parameters':{'gamma':0.02,'a':1/3,'a_exact':'1/3','p':0.5,'updates':3,'local_finite_sum_size':2,'batch_size':1,'bucket_size':2,'compression_omega':1},'atol':1e-10,'rtol':1e-10,'expected':ex,
 'derivation':'PDF p.6 Algorithm 2 lines 6-16 with p.17 Algorithm 5 and CM, p.18 Rand-K K=1,d=2. Exact Fraction arithmetic, exact a=1/3. '+ '\n'.join(trace)}

def build():
 perm=[[0,1,2,3,4,5],[2,0,4,5,1,3],[5,2,1,4,3,0],[4,1,3,5,0,2]]
 return {'schema_version':'optirepro.paper_algorithm_contract.v1','paper':{'paper_id':'2310.09804','title':'Communication Compression for Byzantine Robust Learning: New Efficient Algorithms and Improved Rates','sha256':'d4f2427abc729e228c76d5850fdae85925ef58b3ea305058394a7ebffa2ac26c'},'algorithm':{'name':'Byz-DASHA-PAGE (Algorithm 2), Rand-1 and bucketed coordinatewise median','citations':['PDF p.6, Algorithm 2 lines 1-17','PDF p.17, Appendix B.1 Coordinate-wise Median and Algorithm 5','PDF p.18, Appendix B.2 RandK sparsification'],'core_mechanisms':['page_estimator_recursion','dasha_momentum_compression','local_estimator_memory','byzantine_bucket_aggregation'],'assumptions':['Smooth strongly convex finite-sum quadratic objectives on regular workers.','One Byzantine worker with explicit arbitrary estimator states; no objective assigned to it.','Unbiased uniform one-component gradient differences and Rand-1 compression, conditioned on supported draws.','Recurrence validation only; no assertion that this finite fixture verifies asymptotic robustness constants or theorem stepsize restrictions.','Other proposed methods (Byz-VR-MARINA 2.0, Byz-EF21 and Byz-EF21-BC) are outside this contract.']},'cases':[case('difference_difference_refresh',[1,-1],[0,0,1],[[0,1,0,1,0],[1,0,1,0,1],[0,0,0,0,0]],[[0,1,0,1,0],[1,0,1,0,1],[0,0,1,1,0]],[[20,-20],[-15,30],[40,25],[-35,-20]],perm),case('refresh_difference_difference',[-2,1],[1,0,0],[[0,0,0,0,0],[0,1,1,0,1],[1,0,0,1,0]],[[1,0,1,0,1],[0,1,0,1,0],[1,1,0,0,1]],[[-30,40],[20,-30],[-25,35],[45,-40]],list(reversed(perm)))]}
if __name__=='__main__':Path(__file__).with_name('contract.json').write_text(json.dumps(build(),indent=2,ensure_ascii=False)+'\n')
