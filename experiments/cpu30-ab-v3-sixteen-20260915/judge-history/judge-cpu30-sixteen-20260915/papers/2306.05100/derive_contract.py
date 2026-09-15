"""Exact paper-only ProxSkip-VIP-FL trajectories; no repository input."""
from fractions import Fraction as F
import json
from pathlib import Path

def frac(x): return [frac(a) for a in x] if isinstance(x,list) else F(str(x))
def num(x): return [num(a) for a in x] if isinstance(x,list) else float(x)
def plus(x,y):return [a+b for a,b in zip(x,y)]
def minus(x,y):return [a-b for a,b in zip(x,y)]
def scale(a,x):return [a*b for b in x]
def mean(x):return [sum(col)/len(x) for col in zip(*x)]
def mv(A,x):return [sum(a*b for a,b in zip(row,x)) for row in A]

def case(id,x0,h0,coins,matrices,offsets):
 x,h,A,b=map(frac,[x0,h0,matrices,offsets]);gamma=F('0.1');p=F('0.5');ex=[];trace=[];comms=0
 for t,coin in enumerate(coins):
  g=[plus(mv(ai,xi),bi) for ai,xi,bi in zip(A,x,b)]
  hat=[minus(xi,scale(gamma,minus(gi,hi))) for xi,gi,hi in zip(x,g,h)]
  if coin:
   sent=[minus(hi,scale(gamma/p,ci)) for hi,ci in zip(hat,h)]
   xn=[mean(sent) for _ in x];comms+=1
  else:xn=hat
  hn=[plus(hi,scale(p/gamma,minus(xi,hati))) for hi,xi,hati in zip(h,xn,hat)]
  for name,value in [('operator_used',g),('x_hat',hat),('x',xn),('h',hn),('mean_x',mean(xn)),('communication_count',F(comms))]:
   ex.append({'step':t+1,'name':name,'value':num(value)});trace.append(f'{t+1}:{name}={value}')
  x,h=xn,hn
 return {'id':id,'purpose':'Exercise skip and communication branches with heterogeneous saddle operators and persistent nonzero control variates.','covers':['controlled_local_step','corrected_communication_average','control_variate_update'],
 'inputs':{'workers':len(x0),'network':'All workers communicate synchronously through one server; uniform averaging over every worker.','coordinates':'Each row is worker state [u,v] for min_u max_v.','operator_matrices':matrices,'operator_offsets':offsets,'objective':'Local saddle loss L_i(u,v)=A_i[0,0]*u^2/2+A_i[0,1]*u*v-A_i[1,1]*v^2/2+b_i[0]*u-b_i[1]*v. Operator g_i=[dL_i/du,-dL_i/dv]=A_i*[u,v]+b_i. Global saddle loss is the mean of local losses.','x0':x0,'h0':h0,'oracle':'Use full deterministic local saddle operator at current x_i; no sampling noise.','communication_coins':coins,'randomness':'Condition on exactly the listed server Bernoulli outcomes in chronological order; p=1/2. No extra draws.','observations':'step s=t+1 denotes completion of lines 4-11 for the t-th listed coin. operator_used is evaluated at pre-update x; x_hat precedes communication; x and h follow line 11. mean_x is post-update uniform mean; communication_count includes this step.'},
 'parameters':{'gamma':0.1,'p':0.5,'number_of_updates':len(coins),'loop_index_convention':'Execute exactly four t values 0,1,2,3 (Algorithm 2 prints inclusive 0,...,T; set its T=3).'},'atol':1e-10,'rtol':1e-10,'expected':ex,
 'derivation':'PDF p.7 Algorithm 2: hat=x-gamma*(g-h); when coin=1, x=mean(hat-gamma/p*h), otherwise x=hat; h_next=h+p/gamma*(x_next-hat). All operations are exact rational arithmetic and conversion to JSON float happens once. '+ '\n'.join(trace)}

def build():
 return {'schema_version':'optirepro.paper_algorithm_contract.v1','paper':{'paper_id':'2306.05100','title':'Communication-Efficient Gradient Descent-Accent Methods for Distributed Variational Inequalities: Unified Analysis and Local Updates','sha256':'e3403d50335aef71f975dd1ea908d645873f04aaf0b34d5c9d388cf7b50e14a2'},'algorithm':{'name':'ProxSkip-VIP-FL / deterministic ProxSkip-GDA-FL (Algorithm 2)','citations':['PDF p.7, Section 4 and Algorithm 2 lines 1-13','PDF p.8, Assumption 4.1'],'core_mechanisms':['controlled_local_step','corrected_communication_average','control_variate_update'],'assumptions':['Each local saddle operator has positive definite symmetric part and is smooth.','Full deterministic operator is an unbiased zero-variance oracle.','Coin outcomes are fixed supported realizations of the stated Bernoulli law.','Initial worker points agree and initial control vectors sum to zero.','Finite trajectories only; no claim of proving communication complexity, nonmonotone theory, or loopless-SVRG variants.']},'cases':[case('skip_then_communicate',[[1,-1],[1,-1]],[[0.5,-0.25],[-0.5,0.25]],[0,1,0,1],[[[2,1],[-1,3]],[[4,-2],[2,2]]],[[1,-2],[-3,1]]),case('communicate_then_skip',[[-1,2],[-1,2]],[[1,0.5],[-1,-0.5]],[1,0,1,0],[[[3,-1],[1,2]],[[2,2],[-2,4]]],[[-2,1],[1,-3]])]}
if __name__=='__main__':Path(__file__).with_name('contract.json').write_text(json.dumps(build(),indent=2,ensure_ascii=False)+'\n')
