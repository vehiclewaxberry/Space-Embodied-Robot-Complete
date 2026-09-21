"""Pinned source intake for no-I/O ABI call review; no package execution."""
from pathlib import Path
import hashlib,json,urllib.request
D=Path(__file__).resolve().parent
commit='c48ebc4b2f250aa1f411a580d9d7b626e187040f'
paths=['motor_abi/src/lib.rs','motor_abi/include/motor_abi.h','motor_abi/src/controller_lifecycle_ffi.rs','motor_abi/src/controller_add_motor_ffi.rs','motor_abi/src/motor_control_ffi.rs','motor_abi/src/state_ffi.rs','bindings/python/src/motorbridge/abi.py','bindings/python/src/motorbridge/dm_device_runtime.py','bindings/python/src/motorbridge/errors.py','bindings/python/src/motorbridge/models.py']
rows=[]
for rel in paths:
    url=f'https://raw.githubusercontent.com/motorbridge/motorbridge/{commit}/{rel}'
    p=D/'sources'/'pinned'/rel
    try:
        if p.exists():b=p.read_bytes()
        else:
            with urllib.request.urlopen(url,timeout=30) as r:b=r.read()
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        rows.append({'path':rel,'url':url,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'status':'ACQUIRED'})
    except Exception as e:rows.append({'path':rel,'url':url,'status':'FAILED','error':str(e)})
(D/'sources/ABI_SOURCE_MANIFEST.json').write_text(json.dumps({'commit':commit,'rows':rows},indent=2),encoding='utf-8')
print(json.dumps(rows))
