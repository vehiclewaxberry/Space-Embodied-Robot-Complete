"""Collect current, hash-bound executed evidence; never upgrade earlier receipts."""
from pathlib import Path
import json,hashlib,csv,datetime,urllib.parse
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def item(p):
    p=Path(p).resolve();return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
def link(label,p):return f'[{label}](<{Path(p).resolve().as_posix()}>)'
def dump(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def url(folder,name):return 'http://127.0.0.1:3245/'+urllib.parse.quote(Path(folder).as_posix(),safe='/:')+'?file='+urllib.parse.quote(name,safe='')
def main():
    out=R/'results/DELIVERY_STATUS.json';readme=R/'README.md'
    if out.exists() or readme.exists():raise ValueError('Existing delivery protected')
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    m=read(R/'results/INTEGRATION_MANIFEST.json');states={};pinned={};observed={}
    evidence=['results/BASELINE_CURRENT_CHECK.json','results/INTEGRATION_MANIFEST.json','results/rear_rib/EMISSION.json',
              'results/rear_rib/CHECK.json','results/REAR_RIB_NATIVE.json','results/REAR_RIB_NATIVE_ROUNDTRIP_CHECK_V3.json',
              'results/EXISTING_FOLD_STOP_CHECK.json','viewer/DISPLAY_DELTA_CHECK_V3.json']
    for state,receipt in [('service','NATIVE_SERVICE.json'),('parking','NATIVE_PARKING_RECOVERY_V2.json'),('released','NATIVE_RELEASED.json')]:
        np=R/'results'/receipt;cp=R/'results'/f'NATIVE_CHECK_{state.upper()}.json';n,c=read(np),read(cp)
        assert n['status']=='PASS_NATIVE_FIXED_POSE_DELTA_COLD_REOPEN'
        assert c['status']=='PASS_SCOPED_NATIVE_DELTA_AND_EXACT_MEMBERSHIP'
        assert c['manifest_sha256']==sha(R/'results/INTEGRATION_MANIFEST.json')
        assert sha(c['native_path'])==c['native_sha256']==n['native_save']['sha256']
        counts={k:c['checks'][k] for k in ('component_count','solid_count','unique_dependencies')}
        assert list(counts.values())==[625,1006,473]
        states[state]=dict(**counts,native=item(c['native_path']),execution_receipt=item(np),independent_check=item(cp),
            fixed_pose_only=True,retained=591,replaced=6,added=28,save_api_acknowledgement=n.get('save_api_acknowledgement','RECORDED_IN_EXECUTION_RECEIPT'),
            body_and_transform_evidence='Actual cold component reads, not inferred from displayed mesh count')
        evidence.extend([str(np),str(cp)])
    for rel in evidence:
        p=R/rel;d=read(p);observed[str(p)]=item(p)
        for field in ('input_sha256_before','input_sha256_after','input_sha256','source_sha256'):
            mapping=d.get(field,{})
            if isinstance(mapping,dict):
                for path,digest in mapping.items():
                    if not isinstance(digest,str) or len(digest)!=64:continue
                    canonical=str(Path(path).resolve())
                    if canonical in pinned and pinned[canonical]!=digest:raise ValueError('Conflicting pin '+canonical)
                    pinned[canonical]=digest
    changed=[p for p,h in pinned.items() if not Path(p).is_file() or sha(p)!=h]
    if changed:raise ValueError('Changed inputs: '+repr(changed))
    rear=read(R/'results/rear_rib/CHECK.json');native=read(R/'results/REAR_RIB_NATIVE.json');rt=read(R/'results/REAR_RIB_NATIVE_ROUNDTRIP_CHECK_V3.json')
    assert rear['status']=='PASS_LOCAL_REAR_RIB_NOMINAL_GEOMETRY_ONLY'
    assert native['status']=='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY'
    assert rt['status']=='PASS_LOCAL_NATIVE_STEP_MATERIAL_EQUIVALENCE' and len(rt['checks'])==11
    assert all(c['status']=='PASS' for c in rt['checks'])
    for a in [native['assembly_save'],native['roundtrip_export'],*[x['native_save'] for x in native['parts']]]:assert sha(a['path'])==a['sha256']
    snapshot=read(R/'logs/rear_rib_snapshots_v2.stdout.log')
    assert snapshot['ok'] and len(snapshot['outputs'])==4
    images=[item(x['path']) for x in snapshot['outputs']]
    visual=dict(schema='WP08_ACTUAL_VISUAL_REVIEW',utc=now,reviewed_saved_snapshots=images,
        review='Root visually inspected all four saved PNGs: opposite faces show the single side rib and two fastener stations; axial view shows two-station alignment and intact frame opening; top view shows the nominal stacked plates. Geometry checks provide the numerical fit evidence.',
        full_png_saved=False,whole_snapshot_attempt=item(R/'logs/whole_snapshot.run.json'),
        whole_snapshot_error='Page.evaluate: Target page, context or browser has been closed',
        individual_bored_part_snapshot_status='Attempt stopped by available-memory guard; no individual part PNG credit',
        individual_attempt=item(R/'logs/rear_bored_parts_snapshots.run.json'),
        whole_interactive_reviewed=True,local_interactive_reviewed=True,
        interactive_basis='CUA actually loaded and displayed whole GLB and local 11-instance STEP tree; both tabs marked deliverable. Interactive view is separate from saved snapshot validation.',
        visual_review_does_not_prove_strength_or_assembly=True)
    dump(R/'results/VISUAL_REVIEW.json',visual)
    wholeurl=url(R/'viewer','WP08_SERVICE_RETENTION_DELTA_V3.glb');rearurl=url(R,'candidate/rear_rib_connection.step.py')
    display=read(R/'viewer/DISPLAY_DELTA_CHECK_V3.json')
    assert display['status']=='PASS_DISPLAY_DELTA_ONLY'
    handoff=dict(schema='WP08_VIEWER_HANDOFF',utc=now,status='BOTH_ACTUALLY_LOADED_AND_VISUALLY_REVIEWED',
        server_port=3245,whole=dict(file=item(R/'viewer/WP08_SERVICE_RETENTION_DELTA_V3.glb'),url=wholeurl,tab_id='1'),
        rear=dict(file=item(R/'candidate/rear_rib_connection.step.py'),url=rearurl,tab_id='2'),
        directory_exception='Viewer catalog omits the viewer-named subdirectory; common-root whole URL actually returned FILE DOES NOT EXIST, so whole GLB uses its verified parent as root. Local generated model uses the run root.',
        startup='Existing font-guard bootstrap from WP06 and explicit Anaconda interpreter scoped to this launch; no installed runtime or global Python settings changed',
        native_session='Saved files verified, then twelve hash-bound clean documents closed; empty SolidWorks session exited gracefully for memory. Native files are not currently open.')
    dump(R/'results/VIEWER_HANDOFF.json',handoff)
    module_rows=list(csv.DictReader((R/'results/MECHANICAL_MODULE_EXECUTION_STATUS.csv').open(encoding='utf-8-sig',newline='')))
    assert len(module_rows)==16
    report=dict(schema='WP08_DELIVERY_FACT_SNAPSHOT',utc=now,status='RETENTION_THREE_STATE_INTEGRATED__ONE_REAR_RIB_LOCAL_VERIFIED__WHOLE_ENGINEERING_OPEN',
        goal='可装配工程样机候选',native_states=states,
        stage_one_retention_delta='EXECUTED_SCOPED_PASS',stage_two_structure='ONE_LOCAL_CONNECTION_VERIFIED_NOT_INTEGRATED',
        rear=dict(instances=11,solids=11,replacements=2,new_hardware=8,context=1,integrated_into_three_state=False,
            native=item(native['assembly_save']['path']),step=item(R/'candidate/rear_rib_connection.step'),native_roundtrip=item(native['roundtrip_export']['path']),
            nominal_geometry_check=item(R/'results/rear_rib/CHECK.json'),native_roundtrip_check=item(R/'results/REAR_RIB_NATIVE_ROUNDTRIP_CHECK_V3.json'),
            max_symmetric_difference_mm3=max(x['symmetric_difference_mm3'] for x in rt['checks'])),
        display_check=item(R/'viewer/DISPLAY_DELTA_CHECK_V3.json'),visual_review=item(R/'results/VISUAL_REVIEW.json'),viewer_handoff=item(R/'results/VIEWER_HANDOFF.json'),
        module_count=16,source_input_sha256=pinned,source_input_count=len(pinned),source_inputs_current_and_unchanged=True,evidence_files=observed,
        full_mechanical_design_complete=False,electrical_design_complete=False,whole_STEP_verified=False,whole_geometry_equivalence_verified=False,
        continuous_motion_verified=False,physical_assembly_completed=False,strength_verified=False,manufacturing_release=False,power_on_release=False,
        mass_recalculated=False,mast_park_locked=None,positive_fold_retention_verified=False,
        inherited_B601_geometry_hold='PRESERVED_4_FAIL_6_INCOMPLETE',
        limitations=['213 physical geometry, 375 simplified proxies, 37 functional envelopes per state; none imply hardware qualification',
                     '625 instances do not contain the two bored rear replacement parts or eight new rear fasteners',
                     'Single-way local 90-degree fold stop does not establish a folded retention lock',
                     'Imported native solids with source-driven parameters; no claim of full native sketch feature history or mechanical motion mates',
                     'Actual B601 drive, boards, EPS, battery, connector dimensions and pins remain unbound',
                     'Original failures and interrupted receipts retained; immutable preparation/emission statuses not overwritten'])
    dump(out,report)
    L=[
      '# WP08 机械收束实际交付 · 2026-09-07','',
      '本轮完成两站保持机构在三个实际 SolidWorks 整机装配中的增量回装，并完成一处 +Y 后竖肋两点紧固的局部实体设计。目标仍为可装配工程样机候选；整星全部结构、运动机构和电气设计尚未完成。','',
      f'直接查看：[整星三维预览]({wholeurl}) · [后肋局部三维预览]({rearurl})。两个页面均已实际加载并审阅。整星预览是625实例显示模型，后肋候选尚未并入其中。','',
      '| 可打开的实际装配 | 本轮证据 |','|---|---|']
    for state,title in [('service','服务态'),('parking','停放态'),('released','释放态')]:
        L.append('| '+link(title+' SLDASM',states[state]['native']['path'])+' | 625实例 / 1006实体；完整冷重开、实例/依赖/位置独立核对通过 |')
    L.extend([
      '| '+link('后肋局部 SLDASM',native['assembly_save']['path'])+' | 11实例 / 11实体；逐件原生冷重开和导出STEP逐体材料比较通过 |','',
      '整机每态保留591实例、替换6实例、新增28实例。每态473个不同原生依赖，三态合计488个不同依赖文件；依赖分布在已有WP05–WP07目录，请保留当前目录结构。37个原有功能包络的隐藏状态予以保留。','',
      '停放态保存时曾触发内存保护；SolidWorks随后留下的实际文件通过重新完整只读冷检。原保存调用的API返回仍未知，采用恢复V2及独立检查作为当前证据，不将旧中断日志改写为成功。','',
      '**本轮新增的后肋实体**：两个原件各增加两处Ø3.4名义通孔，轴线位于S系Y=90、Z=±50 mm；采用两套目录M3×16螺钉、双垫圈和螺母，共8件硬件。局部包还包含1个原有端框用于检查，端框不属于新增随星零件。所有局部STEP为S世界系毫米，原生装配采用恒等放置。','',
      link('后肋主 STEP',R/'candidate/rear_rib_connection.step')+' · '+link('原生回导 STEP',native['roundtrip_export']['path'])+' · '+link('参数与源件合同',R/'inputs/REAR_RIB_DESIGN_CONTRACT.json')+' · '+link('后肋零件清单',R/'results/REAR_RIB_LOCAL_BOM.csv'),' ',
      '独立局部几何检查179项通过：核对源件保形、通孔、承压接触、55对局部材料交叠、三态14952组新增硬件—保留邻件筛查及7596组声明工具包络筛查。后两类采用AABB排除后对候选执行BRep精查，不能理解为全部进行了BRep布尔。','',
      '11个原生回导实体逐一与源实体比较，对称材料差均为0 mm³（检查容差1e-5 mm³）。前侧工具包络到端框为7.15 mm，但与内垫圈末端面存在零距离、零体积接触；这不是全通道最小正间隙。螺纹、防松、预紧、实际工具适配、装配工序和连接强度尚未确认。','',
      '**对已有结构的更正**：两站现有叉座已具有90°附近的名义单向越程止挡，每站实际接触约109.361 mm²。该检查仅取89.9°、90°、90.1°；折叠后保持锁扣、传感靶标及其真实状态仍缺，`mast_park_locked=null`。','',
      '**结构查看图**（本轮后肋局部，已审阅）：','',
      '!['+'后肋连接两面装配'+'](<'+Path(images[1]['path']).as_posix()+'>)','',
      '四视图：'+' · '.join(link(n,im['path']) for n,im in zip(['等轴','反向','轴向','俯视'],images))+'.','',
      '整机PNG导出因渲染浏览器关闭失败，已保留日志；补充两改件单独出图也触发内存保护，未取得单件PNG。上面的四张局部装配图及交互显示不改写这些结果。局部11实例的CAD refs与validate已执行，validate为0失败。','',
      '**继续执行入口**：'+link('16模块实际执行表',R/'results/MECHANICAL_MODULE_EXECUTION_STATUS.csv')+' · '+link('下一批实体执行单',R/'docs/NEXT_MECHANICAL_EXECUTION.md')+' · '+link('完整结构缺项核对',R/'docs/STRUCTURAL_COMPLETENESS.md')+'.','',
      '下一批优先处理主枢轴/盖轴轴向防脱、锁销机械捕获，以及已验证后肋的三态差量集成；随后补其余肋、盖板、太阳翼另一端保持、设备载体、线束端接与工装。后肋集成后的633实例/1014实体仅是下一批验收目标，不是当前交付数量。','',
      '实际B601/驱动、PCB、EPS、电池和连接器尚未完整选型并绑定孔系/电流/针脚；四块参考PCB不计为已装星电路。B601原有4项FAIL和6项INCOMPLETE保留。质量预算、连续运动、强度与实物装配未重新完成，当前不能用于宣称制造或通电放行。','',
      '**文件与证据**：'+link('625实例BOM',R/'results/ASSEMBLY_BOM_SERVICE.csv')+' · '+link('488项原生依赖',R/'results/NATIVE_DEPENDENCIES.csv')+' · '+link('实际交付机器记录',out)+' · '+link('局部179项检查',R/'results/rear_rib/CHECK.json')+' · '+link('局部原生回导检查',R/'results/REAR_RIB_NATIVE_ROUNDTRIP_CHECK_V3.json')+'.','',
      f'交付时重新核对{len(pinned)}个已绑定输入，当前哈希一致。SolidWorks原生文件已保存；为释放缓存，已核对并关闭12个本轮无修改文档，再正常退出空会话，可用内存由约0.9 GiB恢复到约3.1 GiB。交互查看服务保持开启。','',
      '本轮原生零件主要为导入实体，参数修改入口在源模型与设计合同；固定姿态装配不等于完整SolidWorks运动配合模型。历史科学Gate、accepted URDF及L2辅助研究模型保持其既有结论。',''])
    readme.write_text('\n'.join(L),encoding='utf-8')
    print(json.dumps(dict(status=report['status'],verified_inputs=len(pinned),states=3,rear_solids=11,readme=str(readme)),ensure_ascii=False))
if __name__=='__main__':main()
