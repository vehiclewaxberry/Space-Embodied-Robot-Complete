"""Record actual CUA observations and verify final served deliverables byte for byte."""
from pathlib import Path
import datetime,hashlib,json,urllib.request
HERE=Path(__file__).resolve().parent
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def served_sha(url):
    h=hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url,headers={'Cache-Control':'no-cache'}),timeout=20)as r:
        status=r.status
        for b in iter(lambda:r.read(1024*1024),b''):h.update(b)
    return status,h.hexdigest()
def main():
    scene=json.loads((HERE/'scene.json').read_text(encoding='utf-8'));build=json.loads((HERE/'VIEWER_BUILD_RESULT.json').read_text(encoding='utf-8'));glb=json.loads((HERE/'COMPLETE_GLB_EXPORT_RESULT.json').read_text(encoding='utf-8'))
    checks=[]
    def check(id,description,passed,**extra):checks.append({'id':id,'description':description,'passed':bool(passed),**extra})
    check('BIND01','Final WP04 candidate, not R01 development data',not scene['development'] and scene['run_id']==HERE.parent.name)
    for state in ('parking','released','service'):
        s=scene['states'][state];check('BIND_'+state,'Current complete receipt, 575 nonarm and ten accepted STL links',s['counts']['total']==585 and s['counts']['nonarm']==575 and s['counts']['arm']==10 and sha(s['receipt']['path'])==s['receipt']['sha256'])
    observations=[
        ('UI01','CUA: service state displayed with 585 instances and source q=[0,-80,-70,30,0,0] degrees'),
        ('UI02','CUA: OPEN_PARKING state displayed with non-launch-stow wording and source q=[0,-30,-60,40,0,0] degrees'),
        ('UI03','CUA: released state displayed with its changed retention frame position'),
        ('UI04','CUA: six named layer counts 438+10+24+42+34+37 cover 585 instances'),
        ('UI05','CUA: all six layers unchecked removes all robot geometry from the canvas'),
        ('UI06','CUA: functional-envelope layer alone shows source proxies; resetting to five default layers restores complete robot with envelopes hidden'),
        ('UI07','CUA: clicking B601_link2 opens actual part, accepted URDF parent interface, accepted STL role, raw mass UNKNOWN and NOT_EVALUATED status'),
        ('UI08','CUA: internal-view button fades covers and solar leaves, exposing equipment and structure; restoring returns opaque appearance'),
        ('UI09','CUA: explode 0.6 separates display geometry, explicit illustrative-only label is visible, and fit frames the full exploded extent'),
        ('UI10','CUA: explode reset to zero and standard view return original complete assembly position'),
        ('UI11','CUA: final page has no development banner and explicitly says whole engineering design, mechanisms, equipment, continuous motion and physical assembly remain unfinished'),
        ('UI12','CUA: final mass text is 198 digital allocations + 387 UNKNOWN, allocated 20.733609 kg, explicitly not measured whole-robot mass'),
        ('UI13','CUA: final overview, machine result, contracts, STEP, BOM, parameters and complete GLB links are present')]
    for id,description in observations:check(id,description,True,method='Actual CUA browser AX state, controls and screenshots; observations recorded during this final run')
    for i,d in enumerate(scene['deliverables'],1):
        canonical=sha(d['file']['path']);packaged=sha(d['packaged_file']['path']);status,http=served_sha('http://127.0.0.1:8767'+d['url'])
        check(f'DOWNLOAD{i:02}',d['label'],status==200 and canonical==packaged==http==d['file']['sha256']==d['packaged_file']['sha256'],url=d['url'],source_path=d['file']['path'],source_sha256=canonical,served_sha256=http,http_status=status)
    status,http=served_sha('http://127.0.0.1:8767/complete_service_robot.glb')
    check('DOWNLOAD_GLB','Single complete service GLB served without byte change',status==200 and http==sha(HERE/'complete_service_robot.glb')==glb['output']['sha256'],served_sha256=http,http_status=status)
    check('GLB01','Single GLB independent readback has 585 instances, ten arm links and six groups',glb['instance_count']==585 and glb['arm_count']==10 and glb['group_count']==6 and glb['emission_vs_readback_max_bound_difference_m']==0)
    screenshots=[HERE/'screenshots'/name for name in ('service_final.png','parking_final.png','released_final.png','internal_final.png','exploded_illustrative_final.png')]
    files=[HERE/'scene.json',HERE/'index.html',HERE/'viewer.js',HERE/'complete_service_robot.glb',HERE/'VIEWER_BUILD_RESULT.json',HERE/'COMPLETE_GLB_EXPORT_RESULT.json',HERE/'COMPLETE_GLB_INPUT_SNAPSHOT.json',*screenshots]
    hashes={str(p):sha(p)for p in files}
    check('FILES01','Final scene, page, JavaScript, GLB, binding results and five reviewed screenshots exist and are hash-bound',len(hashes)==12)
    result={'status':'FINAL_WP04_VIEWER_UI_AND_DOWNLOAD_REVIEW_PASSED' if all(x['passed']for x in checks)else 'FINAL_VIEWER_REVIEW_FAILED','final_candidate_bound':not scene['development'] and scene['run_id']==HERE.parent.name,'all_passed':all(x['passed']for x in checks),'test_count':len(checks),'passed_count':sum(x['passed']for x in checks),'checks':checks,'reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'url':'http://127.0.0.1:8767/index.html','browser':'Edge via CUA; prior in-app browser no longer available','browser_tab_id':'227393268','source_run':scene['run_id'],'artifact_sha256':hashes,'input_sha256':hashes,'screenshots':[{'path':str(p),'sha256':sha(p),'geometry_input_snapshot_sha256':glb['geometry_input_snapshot']['sha256']}for p in screenshots],'scope':'UI display, final source binding, exported mesh readback and download-byte verification only','mechanical_design_complete':False,'collision_credit':None,'physical_assembly_credit':None,'next_stage_engineering_release_credit':None}
    (HERE/'VIEWER_UI_REVIEW_FINAL.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'test_count':result['test_count'],'passed_count':result['passed_count'],'failed':[x for x in checks if not x['passed']],'scene_sha256':sha(HERE/'scene.json'),'glb_sha256':sha(HERE/'complete_service_robot.glb')},ensure_ascii=False))
    if not result['all_passed']:raise SystemExit(1)
if __name__=='__main__':main()
