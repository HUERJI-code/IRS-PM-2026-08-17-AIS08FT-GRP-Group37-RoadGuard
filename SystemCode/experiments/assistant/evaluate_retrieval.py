"""Reproducible diagnostic comparison on the same current knowledge corpus."""
import argparse
import importlib.metadata
import subprocess
import types
import json
from pathlib import Path
import sys
import time

root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'SystemCode/backend'))
from roadguard.assistant.knowledge import load_package
from roadguard.assistant.models import KnowledgeSearchRequest
from roadguard.assistant.retrieval import search
parser=argparse.ArgumentParser(description='Compare synthetic citation retrieval using real local embeddings; no GPT calls.')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
baseline='dd23ca7e44b21fa2520fec2c8bac0f05335dc8cf'
source=subprocess.check_output(['git','show',baseline+':SystemCode/backend/roadguard/assistant/retrieval.py'],cwd=root,text=True,encoding='utf-8')
lexical=types.ModuleType('roadguard.assistant.lexical_reference')
lexical.__package__='roadguard.assistant'
exec(compile(source,'git:'+baseline,'exec'),lexical.__dict__)
package=load_package()
suite=json.loads((root/'SystemCode/backend/knowledge/acceptance_cases.json').read_text(encoding='utf-8'))
cases=[{'id':c['case_id'],'question':c['question'],'expected':c['expected_citations'],'kind':'existing_specification'} for c in suite['cases']]
extra=[
    ('Where do the maintenance teams depart from?', 'rg-kb-scope#depot-crews'),
    ('How long should a severe road cavity take to repair?', 'rg-kb-demo-rules#demo-rule-table'),
    ('Can a worker inspect assignments belonging to another team?', 'rg-kb-workflow#workflow-account-roles'),
    ('How does the genetic optimizer create and improve its population?', 'rg-kb-routing#routing-ga'),
    ('\u65bd\u5de5\u961f\u6bcf\u5929\u4ece\u4ec0\u4e48\u5730\u65b9\u51fa\u53d1？', 'rg-kb-scope#depot-crews'),
    ('\u6df1\u5751\u6d1e\u9700\u8981\u5b89\u6392\u591a\u5c11\u7ef4\u4fee\u65f6\u95f4？', 'rg-kb-demo-rules#demo-rule-table'),
    ('\u6211\u80fd\u7528\u4e8c\u961f\u8d26\u53f7\u67e5\u770b\u4e00\u961f\u7684\u4efb\u52a1\u5417？', 'rg-kb-workflow#workflow-account-roles'),
    ('\u9057\u4f20\u7b97\u6cd5\u600e\u6837\u9009\u62e9\u548c\u7e41\u6b96\u4e0b\u4e00\u4ee3？', 'rg-kb-routing#routing-ga'),
]
cases += [{'id':f'paraphrase-{i+1}','question':q,'expected':[citation],'kind':'paraphrase'} for i,(q,citation) in enumerate(extra)]
cases += [{'id':f'negative-{i+1}','question':q,'expected':[],'kind':'out_of_scope'} for i,q in enumerate([
    'What is the best recipe for chocolate cake?', '\u5e2e\u6211\u63a8\u8350\u660e\u5929\u7684\u80a1\u7968\u4e70\u5165\u4ef7\u683c', 'xyzzyq987 qqqzz'])]
rows=[]
for case in cases:
    row=dict(case)
    for name,fn in [('lexical',lexical.search),('chroma',search)]:
        start=time.perf_counter()
        result=fn(package,KnowledgeSearchRequest(query=case['question'],limit=5))
        hits=[{'citation_id':h.citation_id,'score':h.score,'text':h.text} for h in result.hits]
        row[name]={'status':result.status,'seconds':round(time.perf_counter()-start,4),'hits':hits,
                   'expected_hit':bool(set(case['expected']) & {h['citation_id'] for h in hits}) if case['expected'] else None}
    rows.append(row)
summary={}
for kind in ['existing_specification','paraphrase','out_of_scope']:
    subset=[r for r in rows if r['kind']==kind]
    summary[kind]={'count':len(subset),**{name:sum(bool(r[name]['expected_hit']) for r in subset) if kind!='out_of_scope' else sum(r[name]['status']=='no_matches' for r in subset) for name in ['lexical','chroma']}}
report={'baseline_commit':baseline,'python':sys.version,'dependencies':{name:importlib.metadata.version(name) for name in ['chromadb','onnxruntime','tokenizers']},'is_synthetic':True,'real_embedding_called':True,'real_gpt_called':False,'manifest_sha256':package.manifest_sha256,
        'scope':'Top-five expected-parent citation retrieval only, not answer correctness. Existing specifications may require live plans or refusal.',
        'summary':summary,'cases':rows}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(summary,indent=2))
for row in rows:
    print(json.dumps({'id':row['id'],'query':row['question'],'chroma_hit':row['chroma']['expected_hit'],
                      'hits':[(h['citation_id'],h['score']) for h in row['chroma']['hits']]},ensure_ascii=False))
