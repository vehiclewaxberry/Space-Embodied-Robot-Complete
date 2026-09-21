"""Read-only native-validator/input-contract audit. No CAD, COM or OCC imports."""
from pathlib import Path
import datetime, hashlib, json, math, sys
C=Path(__file__).resolve().parents[1];checks=[];bindings={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    bindings[str(p)]=sha(p)
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ck(k,v):checks.append(dict(id=k,pass_=bool(v)));assert v,k
def matrix_error(a,b):return max(abs(x-y) for ar,br in zip(a,b) for x,y in zip(ar,br))
def main():
    j=read(C/'results/NATIVE_DELTA_INPUTS.json')
    fast=read(C/'mass/R01_GEOMETRY_DELTA_PLAN.json')
    solar=read(C/'solar/SOLAR_LAYOUT.json')
    frame=read(C/'results/SOLAR_HINGE_DELTA.json')
    rids={r['id'] for r in fast['instances']};cids={r['id'] for r in solar['cells']}
    frameids=set(frame['actual_component_changes']['rebuild_edge_frame_geometry_ids'])
    expected_parts=rids|frameids|{'AZUR81442_CIC_GLASS_FOOTPRINT_LAYER','CIC_BONDLINE_0_10MM'}
    ck('138_exact_unique_source_parts',len(j['parts'])==138 and {p['id'] for p in j['parts']}==expected_parts)
    ck('138_distinct_native_files',len({p['native_path'] for p in j['parts']})==138)
    identity=[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]
    states={}
    for state,s in j['states'].items():
        byid={r['id']:r for r in s['rows']};parent={r['id']:r for r in s['parent_rows']}
        changed=set(s['changed_existing_ids']);new=set(s['new_instance_ids']);keep=set(parent)-changed
        ck(state+'_873_unique',len(s['rows'])==len(byid)==873)
        ck(state+'_152_168_553_partition',len(parent)==705 and len(changed)==152 and len(new)==168 and len(keep)==553 and not(changed&new) and set(byid)==set(parent)|new and changed<=set(parent))
        ck(state+'_128_R01_within_changed',rids<=changed)
        ck(state+'_168_finite_layers',new=={x+'_CIC' for x in cids}|{x+'_BOND' for x in cids})
        for ident,r in byid.items():
            ck(state+'_'+ident+'_native_T_primary',r['T_S_local']==r['native_T_local_to_S'])
            if ident in keep:ck(state+'_'+ident+'_retained_T',matrix_error(r['native_T_local_to_S'],parent[ident]['native_T_local_to_S'])<=1e-9)
            if ident in rids:ck(state+'_'+ident+'_R01_source_frame_identity',r['native_T_local_to_S']==identity and r['native_delta_part_id']==ident)
        for cell in solar['cells']:
            panel=byid[cell['parent_leaf']]['native_T_local_to_S']
            side=-1 if cell['parent_leaf'].startswith('wing_-1_') else 1
            for suffix,tkey in [('_CIC','CIC_T_local_to_S_mm'),('_BOND','ADHESIVE_T_local_to_S_mm')]:
                got=byid[cell['id']+suffix]['native_T_local_to_S']
                ck(state+'_'+cell['id']+suffix+'_layout_T_exact',got==cell['states'][state][tkey])
                zlocal=sum(panel[k][2]*(got[k][3]-panel[k][3]) for k in range(3))
                ck(state+'_'+cell['id']+suffix+'_correct_parent_face',side*zlocal>1.25)
            if state=='service':
                got=byid[cell['id']+'_CIC']['native_T_local_to_S']
                ck(state+'_'+cell['id']+'_front_world_plus_Z',max(abs(got[k][2]-[0,0,1][k]) for k in range(3))<1e-12)
        states[state]=dict(components=len(byid),retained_unchanged=len(keep),changed_existing=len(changed),added=len(new),native_T_authority_preserved=True,R01_same_source_frame_identity=True,solar_faces_correct=True,retained_T_max_mm_or_unitless_roundtrip_error=max(matrix_error(byid[i]['native_T_local_to_S'],parent[i]['native_T_local_to_S']) for i in keep))
    for p in [C/'tools/native_delta_prepare.py',C/'tools/native_delta_driver.py',C/'tools/native_delta_pending.py',C/'../tools/integrate_native_v5.py',C/'tools/native_delta_guard.py',C/'tools/native_delta_seal_parts.py',C/'tools/native_delta_delivery.py']:
        bindings[str(p)]=sha(p)
    driver=(C/'tools/native_delta_driver.py').read_text()
    outstanding=[]
    if "q['native_sha256']=m.sha(q['native_path'])" in driver:
        outstanding.append('NV-01: integrate/cold assigned expected new-native SHA from current file. Frozen imported-parts SHA binding is still pending in this inspected version.')
    if "digest=m.sha(target);opened=" in driver and 'integration_receipt' not in driver:
        outstanding.append('NV-02: cold assembly target SHA not yet bound to integration native_save receipt in this inspected version.')
    relocation_source_guard="not D.exists()" in driver and 'original_root_absent_during_cold_open' in driver
    out=dict(schema='READONLY_NATIVE_VALIDATOR_INPUT_REVIEW_V1',generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
      status='INPUT_COORDINATE_COUNTS_PASS__VALIDATOR_FIXES_PENDING' if outstanding else 'INPUT_COORDINATE_COUNTS_PASS__VALIDATOR_FIX_SOURCE_PRESENT_RUNTIME_PENDING',
      check_count=len(checks),checks_passed=sum(c['pass_'] for c in checks),state_checks=states,
      helper_metadata_checks=['all873 unique ComponentReference identities/count','actual component GetPathName normalized to expected file','file SHA compared with expected SHA (expected source must be independently frozen)','actual native16 transform compared to mm-to-m mapped expected T at1e-8 mixed-unit tolerance','each fixed and unsuppressed/resolved-state category','actual all dependency paths exactly equal current expected dependency set and inside requested root'],
      helper_body_readback_scope='measure=False for full assembly; 138 unique new parts must have separate cold-body/import proof. Retained body data must remain hash-bound to parent. No all1254 body reread credit.',
      closed_source_findings=[{'id':'NV-01','finding':'New native expected SHA previously set from current file, making comparison self-referential','resolution':'One-time138 imported-parts snapshot derives expectedSHA from completed import native_save receipts; source/native/frame proof/hash chain checked. Current dependency fileSHA is only compared to frozen expected.'},{'id':'NV-02','finding':'Cold target assembly SHA previously not bound to integration save receipt','resolution':'Cold requires correct-state PASS integration native_saveSHA plus matching inputmanifest and imported-parts snapshot SHA; relocation reads currentfolder/basename using frozen expected digest.'}] if not outstanding else [],
      source_relocation_absence_guard_present=relocation_source_guard,
      actual_relocation_execution_verified=False,actual_native_execution_verified=False,CAD_COM_OCC_executed_by_reviewer=False,
      findings=outstanding,
      source_only_readonly_review_limit='Source presence and input arithmetic do not prove the runtime branches executed. Real move manifest, original-root absence and native cold outputs remain CAD writer responsibilities.',
      source_bindings=bindings,checks=checks)
    (C/'review/NATIVE_VALIDATOR_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['status','check_count','checks_passed','source_relocation_absence_guard_present','findings']}))
if __name__=='__main__':main()
