from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent;C=R/'candidate';p=C/'r01_design.py'
source=p.read_text(encoding='utf-8');cfg=json.loads((C/'design_parameters.json').read_text(encoding='utf-8'))
snap=R/'inputs/R01_CANDIDATE1_SOURCE.json'
if snap.exists():
    assert json.loads(snap.read_text(encoding='utf-8'))['r01_source']==source,'Previous source already changed'
else:snap.write_text(json.dumps(dict(r01_source=source,parameters=cfg,contract=json.loads((C/'results/r01_connections.json').read_text(encoding='utf-8'))),ensure_ascii=False,indent=2),encoding='utf-8')
cfg['r01']['revision']='R01_CANDIDATE_2'
cfg['r01']['thermal_passage']={'deck':'lower','center_xy_mm':[-115,0],'diameter_mm':12,'existing_link_envelope_d_mm':10,'nominal_radial_gap_mm':1,'bushing_and_thermal_isolation':'UNKNOWN'}
cfg['r01']['existing_web_screw_clearance']={'deck':'lower','x_mm':[-146,-86,-26,34,94],'z_mm':-94,'diameter_mm':3.4,'purpose':'Clear existing 1 mm screw-tail encroachment; no added clamp/load credit'}
needle_deck='    return s\ndef angle_center'
assert needle_deck in source
source=source.replace(needle_deck, '    if not legacy and deck==R["thermal_passage"]["deck"]:\n        t=R["thermal_passage"];s=cut(s,t["diameter_mm"],7,(*t["center_xy_mm"],0))\n    return s\ndef angle_center',1)
needle='    return s\ndef web_shape'
replacement='    if not legacy and deck==R["existing_web_screw_clearance"]["deck"]:\n        e=R["existing_web_screw_clearance"]\n        for x in e["x_mm"]:\n            if a<x<b:s=cut(s,e["diameter_mm"],7,(x-(a+b)/2,side*3.5,e["z_mm"]-(R["deck_z_mm"][deck]-3)),(0,1,0))\n    return s\n\ndef web_shape'
assert needle in source;source=source.replace(needle,replacement,1)
source=source.replace('    absent_equipment=["equipment_"+e["name"] for e in P["equipment"]]','    absent_equipment=[prefix+e["name"] for e in P["equipment"] for prefix in ["equipment_","adapter_","thermal_interface_"]]')
source=source.replace('JOIN_DECKS_ANGLES_WEBS_AND_FASTENERS_BEFORE_EQUIPMENT_AND_COVERS','JOIN_DECKS_ANGLES_WEBS; INSTALL_WASHERS_THEN_SCREW_THEN_NUT; BEFORE_EQUIPMENT_ADAPTERS_THERMAL_PADS_AND_COVERS')
start=source.index('        c["insertion_paths"]=[');end=source.index('\n        c["mass_owner_policy"]',start)
source=source[:start]+'''        c["insertion_paths"]=[]
        for kind,direction,travel,later in [('washer_head',a,30,['screw','nut']),('washer_nut',[-v for v in a],20,['screw','nut']),('screw',a,30,['nut']),('nut',[-v for v in a],20,[])]:
            c["insertion_paths"].append(dict(id=c['id']+'_'+kind+'_insert',moving_id=c["hardware"][kind],direction_S=direction,travel_mm=travel,assembly_absent_ids=absent+[c['hardware'][n] for n in later],allowed_contact_ids=[]))
''' .rstrip()+source[end:]
p.write_text(source,encoding='utf-8');(C/'design_parameters.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
print('candidate2 local geometry and explicit installation phases written')
