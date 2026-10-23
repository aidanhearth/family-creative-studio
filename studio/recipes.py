"""Validated starts for several workflows; no copied private source material."""
import json
from .paths import ROOT
from .seed import demo
from .schema import Manifest

def recipes():
    return list(json.loads((ROOT/'web/upgrade-copy.json').read_text())['templates'].values())

def create_project(store,recipe_id,project_id,title=None):
    options={r['id']:r for r in recipes()}
    if recipe_id not in options:raise ValueError('Unknown recipe')
    document=demo().model_dump();document['id']=project_id
    copy=json.loads((ROOT/'web/recipes-copy.json').read_text())[recipe_id]
    document.update(title=title or copy['title'],subtitle=copy['subtitle'])
    document['beats']=[dict(b,id=f'chapter-{i+1}',visual={'mode':['orbit','explode' if recipe_id!='product_explainer' else 'diagram','diagram'][i]}) for i,b in enumerate(copy['beats'])]
    if recipe_id=='assembly_story':
        document['solids']=[{'id':'base','name':'Base','kind':'cylinder','size':[120,120,14],'position':[0,0,7],'color':'#B37B52'}, {'id':'pillar','name':'Stem','kind':'cylinder','size':[20,20,150],'position':[0,0,89],'color':'#545C61'}, {'id':'tray','name':'Cap','kind':'cylinder','size':[90,90,12],'position':[0,0,170],'bore':12,'color':'#D8C6A7'}]
        document['beats'][0]['visual']={'mode':'orbit'};document['beats'][1]['visual']={'mode':'explode'}
    if recipe_id=='media_story':document['beats'][0]['visual']={'mode':'orbit'}
    m=Manifest.model_validate(document);m.resolved()
    return store.save(m,expected_revision=0)
