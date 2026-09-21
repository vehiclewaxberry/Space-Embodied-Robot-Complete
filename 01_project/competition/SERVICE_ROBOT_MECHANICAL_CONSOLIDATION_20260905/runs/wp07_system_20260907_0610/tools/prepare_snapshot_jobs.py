"""Write explicit review jobs; this creates no rendered or validated artifact."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
dest=R/'results/snapshots';dest.mkdir(exist_ok=True)
targets={'service':R/'viewer/WP07_SERVICE_BREP_REVIEW_V3.glb',
         'retention0':R/'candidate/retention_station0.step.py',
         'retention1':R/'candidate/retention_station1.step.py'}
for name,target in targets.items():
    output=R/'inputs'/('SNAPSHOT_'+name.upper()+'.json')
    assert not output.exists()
    views=[('iso','iso'),('opposite',{'direction':[-1,1,-0.8]}),('top','top'),('front','front')]
    job=dict(input=str(target),mode='view',outputs=[dict(path=str(dest/(name+'_'+label+'.png')),camera=camera) for label,camera in views],render=dict(viewLabels=True,padding=.12,width=1400,height=1000,sizeProfile='diagnostic'))
    output.write_text(json.dumps(job,indent=2),encoding='utf-8')
    print(str(output))
