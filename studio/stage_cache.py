"""Verified stage reuse with canonical internal names and independent output copies."""
import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path
from .paths import atomic_json, contained, sha256

class StageCache:
    def __init__(self, root, engine):
        self.root=root/'stages';self.engine=engine;self.records=[]

    def run(self, stage, inputs, out, names, execute):
        internal=[str(i)+Path(name).suffix for i,name in enumerate(names)]
        key=hashlib.sha256(json.dumps([2,stage,inputs,internal,self.engine],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        location=self.root/stage/key;start=time.monotonic();reused=False
        try:
            records=json.loads((location/'outputs.json').read_text())
            valid=set(records)==set(internal) and all(contained(location,n).is_file() and sha256(contained(location,n))==records[n] for n in internal)
        except (OSError,ValueError,TypeError):valid=False
        if valid:
            for name,cached in zip(names,internal):
                target=contained(out,name);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(contained(location,cached),target)
            reused=True
        else:
            execute()
            location.parent.mkdir(parents=True,exist_ok=True)
            temp=location.parent/(key+'.pending-'+uuid.uuid4().hex);temp.mkdir()
            records={}
            for name,cached in zip(names,internal):
                source=contained(out,name)
                if not source.is_file():raise ValueError('Stage output missing: '+name)
                target=contained(temp,cached);shutil.copy2(source,target);records[cached]=sha256(target)
            atomic_json(temp/'outputs.json',records)
            if location.exists():location.replace(location.with_name(key+'.invalid-'+uuid.uuid4().hex))
            temp.replace(location)
        result={'stage':stage,'key':key,'reused':reused,'bytes':sum(contained(out,n).stat().st_size for n in names),'elapsed_s':round(time.monotonic()-start,3),'outputs':{n:records[c] for n,c in zip(names,internal)}}
        self.records.append(result)
        return result
