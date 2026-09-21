"""Exercise an in-memory hole-coordinate perturbation through both mating bodies."""
from pathlib import Path
import sys,json,copy,hashlib
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
import r01_design as R
from build123d import Location
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def vol(s):return 0 if s is None else sum(x.volume for x in s.solids())
def main():
    path=HERE/'design_parameters.json';before=sha(path);P=R.parameters();Q=copy.deepcopy(P)
    Q['r01']['deck_hole_x_mm'][-1]=138
    checks=[]
    for kind in ['deck','angle']:
        def build(p):
            if kind=='deck':return R.deck_shape(p,'lower').moved(Location((0,0,p['r01']['deck_z_mm']['lower'])))
            return R.angle_shape(p,'lower',1,1).moved(Location(tuple(R.angle_center(p,'lower',1,1))))
        a,b=build(P),build(Q);z=-99.65 if kind=='deck' else -102.65
        new_probe=R.cyl(3.398,2.998,(138,92.65,z));old_probe=R.cyl(3.398,2.998,(140,92.65,z))
        symmetric_delta=vol(a-b)+vol(b-a)
        empty_new=vol(b&new_probe);refilled_old=vol(b&old_probe)
        passed=symmetric_delta>1 and empty_new<1e-5 and refilled_old>1 and a.is_valid and b.is_valid
        checks.append(dict(body=kind,status='PASS' if passed else 'FAIL',x_before_mm=140,x_after_mm=138,symmetric_material_delta_mm3=symmetric_delta,new_axis_material_mm3=empty_new,old_axis_material_mm3=refilled_old))
    result=dict(scope='Two actual mating BReps regenerated in memory only; final parameter file unchanged',checks=checks,parameters_sha256_before=before,parameters_sha256_after=sha(path),status='PASS' if all(x['status']=='PASS' for x in checks) and before==sha(path) else 'FAIL')
    (HERE/'results/PARAMETER_PROPAGATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
