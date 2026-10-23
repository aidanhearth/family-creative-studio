import json
from .paths import ROOT
from .schema import Manifest

def demo():
    copy=json.loads((ROOT/'web/copy.json').read_text())
    colors=copy['presets'][0]['colors']
    beats=[]
    for i,b in enumerate(copy['narrative']):
        body=b['body'].replace('180×130×12','{{base.size}}').replace('20×20×180','{{pillar.size}}').replace('130×90×12','{{tray.size}}').replace('60mm','{{tray.bore}}mm')
        narration=b['narration'].replace('一百八十','{{pillar.height}}').replace('六十','{{tray.bore}}')
        beats.append(dict(id=f'chapter-{i+1}',title=b['title'],body=body,narration=narration,duration=7,focus=[['base','pillar'],['tray'],['base','pillar','tray']][i]))
    return Manifest.model_validate({'schema_version':1,'id':'pour-over-stand','title':'模組化手沖咖啡架',
        'subtitle':copy['demo']['summary'], 'brand':{'name':copy['presets'][0]['name'],'paper':colors['canvasBg'],
        'ink':colors['textPrimary'],'accent':colors['accentPrimary'],'muted':colors['textSecondary']},
        'solids':[{'id':'base','name':'底座','kind':'box','size':[180,130,12],'position':[0,0,6],'color':colors['partBaseColor']},
        {'id':'pillar','name':'背柱','kind':'box','size':[20,20,180],'position':[0,55,102],'color':colors['partPillarColor']},
        {'id':'tray','name':'上托架','kind':'box','size':[130,90,12],'position':[0,0,186],'bore':60,'color':colors['partTrayColor']}],
        'beats':beats,'style_id':'3d'})
