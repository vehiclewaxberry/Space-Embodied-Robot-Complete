"""Bind immutable angle parents before replacing any angle instance."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1];path=A/'thermal/BOTTOM_RADIATOR_MOUNT.json';p=json.loads(path.read_text());plan=json.loads((A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json').read_text())
if 'baseline_angles' not in p:
    p['baseline_angles']={r['id']:dict(path=r['step_path'],sha256=r['source_sha256'],T_S_step=r['T_S_step']) for r in plan['states']['service']['rows'] if r['id'].startswith('lower_deck_angle_')}
    assert len(p['baseline_angles'])==4
    for r in p['baseline_angles'].values():assert hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256']
p.update(mount_centers_xy_mm=[[-140,-93.5],[-140,93.5],[-60,-33],[-60,33],[120,-93.5],[120,93.5]],
 mount_support_z_mm=[-104.15,-104.15,-101.15,-101.15,-104.15,-104.15],
 mount_support_ids=['lower_deck_angle_-1_0','lower_deck_angle_1_0','lower_equipment_deck_B','lower_equipment_deck_B','lower_deck_angle_-1_1','lower_deck_angle_1_1'],
 revision='V3_FOUR_ANGLE_BEARING_TWO_DECK_BEARING__EXACT_CLEARANCE_PENDING',
 support_chain='Four outer bosses bear on drilled existing angle undersides; two inner bosses bear directly on deck. All six bolts clamp to deck top washer/nut.')
path.write_text(json.dumps(p,indent=2),encoding='utf-8');print(p['revision'])
