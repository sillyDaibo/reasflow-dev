#!/usr/bin/env python3
"""Independent paper-only local barycenter oracle/PPS contract, no graph recursion."""
from pathlib import Path
from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json
import math

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
PDF=ROOT/'datasets/benchmarks/cpu30_v1/input/2501.18312/paper.pdf'
spec=importlib.util.spec_from_file_location('contract_schema',ROOT/'repo_judge/src/judge/paper_contract.py')
schema=importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema)
D=lambda x:Decimal(str(x))
MECHANISMS=['sample_barycenter_softmax','minibatch_before_quantization','simplex_pps_fixed_uniforms']
COMMON={
 'cost':'c(y,xi)=(y-xi)^2',
 'local_oracle':'At each listed call independently, evaluate p_h=exp((mu_h-c(y_h,xi))/gamma)/sum_l exp((mu_l-c(y_l,xi))/gamma) for every source sample, then average the r vectors before PPS.',
 'pps_rule':'Apply Eq. (1) to the minibatch mean. Positive mass is 1; negative mass is 0 and its term is absent. Each uniform chooses the first one-based h with u<cumulative_mean_probability[h]; quantized_gradient[h]=count(h)/M.',
 'step_semantics':'step 1 and step 2 are two separately specified oracle calls at the supplied nonzero local mu vectors. There is no recurrence between calls.',
 'observation_semantics':'sample_probabilities has source-sample rows and support columns; minibatch_mean and quantized_gradient have one component per support point; positive_mass is the l1 mass of the nonnegative batch gradient; pps_indices are one-based categories in public uniform order.',
 'scope':'Local Lemma 3 oracle and Eq. (1) PPS only. This contract does not test Algorithm 3 graph communication, accelerated dual updates, primal recovery, any global m-rescaling, or full algorithm correctness.'
}

def cases():
 return [
  {'id':'local_binary_support_two_nonzero_arguments',
   'purpose':'Check the signed local argument, non-unit gamma, per-sample softmax normalization, averaging before quantization, and fixed-uniform PPS in two distinct bounded draws.',
   'covers':MECHANISMS,
   'inputs':{'target_support':[0,1],'source_space':[0,1], 'source_distribution':{'law':'uniform','interval':[0,1]},
    'calls':[{'mu':[0.2,-0.1],'source_samples':[0.15,0.65],'pps_uniforms':[0.08,0.35,0.66,0.91]},
             {'mu':[-0.25,0.4],'source_samples':[0.3,0.85],'pps_uniforms':[0.05,0.24,0.57,0.89]}]},
   'parameters':{**COMMON,'gamma':0.5,'r':2,'M':4},'atol':1e-10,'rtol':1e-9,
   'derivation':'For binary support, p_1(mu,xi)=sigmoid((mu_1-mu_2+1-2xi)/gamma) and p_2=1-p_1. Call 1 therefore uses sigmoid(2) and sigmoid(0); call 2 uses sigmoid(-0.5) and sigmoid(-2.7). Average the two vectors in each call before comparing supplied uniforms to the first-component CDF. PPS is the empirical category frequency with unit positive mass. The companion script computes every required observation in 60-digit Decimal arithmetic and checks against an independent ordinary-float evaluation.'},
  {'id':'local_three_support_minibatch_then_pps',
   'purpose':'Three support coordinates and three unequal source samples distinguish cost-adjusted softmax from linear normalization and distinguish quantizing a minibatch mean from independently quantizing sample gradients.',
   'covers':MECHANISMS,
   'inputs':{'target_support':[-1,0,1],'source_space':[-1,1], 'source_distribution':{'law':'uniform','interval':[-0.8,0.9]},
    'calls':[{'mu':[0.3,-0.2,0.1],'source_samples':[-0.65,-0.1,0.55],'pps_uniforms':[0.06,0.26,0.48,0.73,0.95]},
             {'mu':[-0.2,0.35,-0.1],'source_samples':[-0.4,0.2,0.8],'pps_uniforms':[0.04,0.22,0.5,0.79,0.96]}]},
   'parameters':{**COMMON,'gamma':0.75,'r':3,'M':5},'atol':1e-10,'rtol':1e-9,
   'derivation':'For each call and each listed xi compute three logits (mu_h-(y_h-xi)^2)/(3/4), exponentiate and normalize each row separately. Average the three normalized rows, sum their CDF in support order (-1,0,1), and apply the five fixed uniforms to this batch CDF. Multiply empirical one-hot frequencies by positive l1 mass 1; the zero negative part contributes nothing. No graph or dual iteration is inferred from these independent nonzero local arguments. The companion script computes every required observation in 60-digit Decimal arithmetic and checks it independently with ordinary-float arithmetic.'}
 ]

def numeric(x):
 if isinstance(x,list):return [numeric(v) for v in x]
 return float(x) if isinstance(x,Decimal) else x

def derive(case):
 inp,p=case['inputs'],case['parameters']
 y=[D(x) for x in inp['target_support']]; n=len(y)
 expected=[]; margin=D(1)
 for step,call in enumerate(inp['calls'],1):
  mu=[D(x) for x in call['mu']]
  probs=[]
  for xi in call['source_samples']:
   ex=[((mu[j]-(v-D(xi))**2)/D(p['gamma'])).exp()for j,v in enumerate(y)]
   probs.append([v/sum(ex)for v in ex])
  mean=[sum(row[j]for row in probs)/D(p['r']) for j in range(n)]
  cdf=[sum(mean[:j+1])for j in range(n)]
  ids=[]
  for u in call['pps_uniforms']:
   ud=D(u);margin=min(margin,*(abs(ud-c)for c in cdf[:-1]))
   ids.append(next(j+1 for j,c in enumerate(cdf)if ud<c))
  quantized=[D(ids.count(j+1))/D(p['M'])for j in range(n)]
  positive=sum(mean)
  for name,v in [('sample_probabilities',probs),('minibatch_mean',mean),('positive_mass',positive),('pps_indices',ids),('quantized_gradient',quantized)]:
   expected.append({'step':step,'name':name,'value':numeric(v)})
  # Independent float evaluation, with no derived numeric oracle as input.
  check_probs=[]
  for xi in call['source_samples']:
   e=[math.exp((call['mu'][j]-(v-xi)**2)/p['gamma'])for j,v in enumerate(inp['target_support'])]
   check_probs.append([v/sum(e)for v in e])
  check_mean=[sum(row[j]for row in check_probs)/p['r'] for j in range(n)]
  check_ids=[next(j+1 for j in range(n)if u<sum(check_mean[:j+1]))for u in call['pps_uniforms']]
  assert check_ids==ids
  assert max(abs(float(a)-b)for ar,br in zip(probs,check_probs)for a,b in zip(ar,br))<1e-14
  assert max(abs(float(a)-b)for a,b in zip(mean,check_mean))<1e-14
  assert abs(positive-1)<D('1e-55') and sum(quantized)==1
  assert all(D(inp['source_distribution']['interval'][0])<D(x)<D(inp['source_distribution']['interval'][1])for x in call['source_samples'])
 case['expected']=expected
 assert margin>D('0.001'), margin
 return margin

def main():
 with localcontext()as ctx:
  ctx.prec=60
  cc=cases();margins=[derive(c)for c in cc]
 contract={'schema_version':schema.SCHEMA_VERSION,
  'paper':{'paper_id':'2501.18312','title':'Decentralised convex optimisation with probability-proportional-to-size quantization','sha256':hashlib.sha256(PDF.read_bytes()).hexdigest()},
  'algorithm':{'name':'Local component only: Lemma 3 barycenter stochastic gradient and Eq. (1) PPS quantization (not Algorithm 3 verification)',
   'citations':['PDF p. 20, Lemma 3, sample conjugate-gradient softmax','PDF p. 19, Section 6.1 and Eq. (9), continuous source probabilities and continuous transport cost','PDF pp. 6-7, Section 2, minibatch definition and PPS Eq. (1)','PDF p. 7, paragraph after Eq. (1), interpretation of fixed uniform random arguments'],
   'core_mechanisms':MECHANISMS,
   'assumptions':['Each source law is a bounded continuous uniform probability measure; all supplied samples lie strictly within its support.',
    'The selected squared-distance cost is continuous and nonnegative; gamma is positive. Every sample and batch gradient lies in the simplex with l1 bound B=1.',
    'All local arguments are public, nonzero vectors freely chosen from the unconstrained domain of the Lemma 3 conjugate. They are not derived from a repository run or an Algorithm 3 trajectory.',
    'PPS takes the average unquantized sample gradient and then uses the fixed uniform arguments. The probability vector has no negative part, so no arbitrary negative categorical distribution is introduced.',
    'A pass establishes only the listed local operators at these finite inputs. It cannot establish graph communication, accelerated updates, primal restoration, global coordinate scaling, or full Algorithm 3 correctness.']},'cases':cc}
 schema.validate_contract(contract)
 public=schema.public_contract(contract)
 (OUT/'contract.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False)+'\n')
 pub=ROOT/'reports/judge-followup-cpu30-20260915/public/2501.18312-oracle/public_cases.json'
 pub.parent.mkdir(parents=True,exist_ok=True)
 pub.write_text(json.dumps(public,indent=2,ensure_ascii=False)+'\n')
 assert all('expected'not in x and 'derivation'not in x for x in public['cases'])
 for c,margin in zip(cc,margins):
  print(c['id'],'CDF margin',margin)
  for e in c['expected']:
   if e['name']in ['minibatch_mean','pps_indices','quantized_gradient']:print(e)
 print('Validated 2 local-only cases; all independent float checks passed.')
if __name__=='__main__':main()
