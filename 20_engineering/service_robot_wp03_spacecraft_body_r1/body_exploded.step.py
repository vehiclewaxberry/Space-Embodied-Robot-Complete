"""Exploded illustration only: placements here must not enter dynamics or fit checks."""
from spacecraft_model import build
from build123d import Compound,Location
def gen_step():
    _,parts,r=build('parking',view='exploded',include_arm=False)
    children=[]
    for row in r['instances']:
        if row['parent_assembly'] in ['ONBOARD_RETENTION','SOLAR_WING'] or row['representation_role']=='FUNCTIONAL_ENVELOPE':continue
        name=row['id'];dx=dy=dz=0
        if name.startswith('access_cover_'):dy=150 if name.endswith('_1') else -150
        elif name=='front_service_cover':dx=100
        elif name=='forward_roof_access':dz=180
        elif row['parent_assembly']=='EQUIPMENT_BAY':dz=90 if row['bounds']['min_mm'][2]>-20 else 45
        children.append(parts[name].moved(Location((dx,dy,dz))))
    return Compound(label='WP03_EXPLODED_VIEW_NOT_PHYSICAL_CONFIGURATION',children=children)
