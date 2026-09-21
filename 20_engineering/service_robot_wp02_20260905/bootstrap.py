"""Pin local WP01 inputs without mutating their sources."""
from pathlib import Path
import hashlib,json,shutil,datetime
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
WP01=HERE.parent/'service_robot_wp01_20260905'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    files=[WP01/n for n in ['CAD_BRIEF.md','README.md','DESIGN_INPUTS.md','NEXT_PARTS.md','ASSEMBLY_AND_TEST_PLAN.md','interface_requirements.csv','design_parameters.json','SOURCE_INPUTS.json','kinematics.py','service_robot_common.py','results/DELIVERY_RECEIPT.json','results/INTERFACE_GEOMETRY.json','results/TRANSFORM_TRANSFER.json','results/stowed_build_receipt.json','results/STRUCTURE_CONTACT_CHECK.json','results/SOURCE_TOPOLOGY_REPAIR_PROBE.json']]
    files += [Path('C:/Users/stude/Downloads/WP02_KEY_ASSEMBLY_DESIGN_PROMPT_ZH (1).md'),Path('C:/Users/stude/.codex/attachments/c56f0c4c-b0c5-412b-9516-f62c6c2b37a6/pasted-text.txt')]
    rows=[]
    for f in files:
        data=f.read_bytes()
        rows.append({'path':str(f),'bytes':len(data),'sha256':sha(f),'coverage':'COMPLETE_MACHINE_READ; engineering interpretation in task reports','role':'USER_SUPPLIED_REFERENCE_NOT_AUTHORITY' if str(f).startswith('C:') else 'WP01_INPUT'})
    for n in ['m3r_a.step','m3r_b.step']:
        src=WP01/'inputs'/n;dst=HERE/'inputs'/n
        if not dst.exists():shutil.copy2(src,dst)
        rows.append({'path':str(src),'copy':str(dst.relative_to(HERE)),'bytes':src.stat().st_size,'sha256':sha(src),'copy_sha256':sha(dst),'coverage':'REUSED_NOMINAL_BREP'})
    for n in ['design_parameters.json','kinematics.py']:
        shutil.copy2(WP01/n,HERE/'inputs'/('wp01_'+n))
    (HERE/'INPUT_PROVENANCE.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'units':'mm; STL source m scaled once by 1000; q deg','rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Pinned',len(rows),'input records')
if __name__=='__main__':main()
