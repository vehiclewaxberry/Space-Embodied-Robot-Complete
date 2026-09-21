from pathlib import Path
import sys
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
from build123d import import_step,export_step
r=Path(__file__).resolve().parents[1]
s=import_step(r/'sources/RB_longeron_-1_-1_860c564c_service.step')
solid=s.solids()[0]
solid.label='WP05_LONGERON_SINGLE_SOLID'
export_step(solid,r/'sources/SMOKE_SINGLE_SOLID.step')
q=import_step(r/'sources/SMOKE_SINGLE_SOLID.step')
assert q.is_valid and len(q.solids())==1
assert abs(s.volume-q.volume)<1e-5
print('one solid',q.volume)
