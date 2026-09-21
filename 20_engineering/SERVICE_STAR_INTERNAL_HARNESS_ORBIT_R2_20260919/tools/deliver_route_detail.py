"""Publish the source-bound R2 local view and fixed-pose service assembly.

Only R2 files are written. Native assemblies deliberately reference the pinned
R1 native directory. R2 is a local integration delta, not a portable Pack-and-Go.
"""
from pathlib import Path
import sys, json, math, argparse, importlib, shutil
import numpy as np
from build_internal_passage import D,R1,ROOT,I,read,write,sha,load,moved,bounds,count,volume,common,block

DETAIL_IDS=['WP01-RB-BRIDGE-R2','WP01-MT-M3RA-REUSED','WP01-MT-M3RB-REUSED',
    'ROOT_BUSH_LEFT','ROOT_BUSH_RIGHT','ROOT_KEEPER','ROOT_SCREW_0','ROOT_SCREW_1',
    'WP10_INTERNAL_BATTERY_BYPASS','release_power_data_route_0_1','release_power_data_route_1_1',
    'RB_pillar_tierod_0','RB_pillar_top_washer_0','R07_upper_cap_20_-1',
    'hold_pivot_clevis_0','hold_pivot_clevis_1','hold_roof_lug_0_-94.15','hold_roof_lug_1_-94.15']
PN=D/'inputs/NATIVE_ROUTE_PLAN.json'

def prepare():
    review=read(D/'results/RELEASE_ROUTE_STATIC_CHECK.json'); assert not review['unclassified_collisions']
    data=read(R1/'inputs/INTEGRATED_ASSEMBLY_PLAN.json'); mapping=read(R1/'inputs/NEUTRAL_SOURCE_MAP.json')
    allrows=[r for g in mapping['groups'] for r in g['rows']]; byid={r['id']:r for r in allrows}
    (D/'native').mkdir(exist_ok=True); parts=[]
    for r in review['rows']:
        out=r['output'];p=Path(out['path']); assert sha(p)==out['sha256']
        parts.append({'id':r['id'],'step_path':str(p),'source_sha256':sha(p),
            'native_path':str(D/'native'/(r['id']+'_R2_V2.SLDPRT')),'expected_solids':1,
            'expected_local_bbox_mm':{'min_mm':out['bounds_mm'][0],'max_mm':out['bounds_mm'][1]},
            'expected_volume_mm3':out['volume_mm3'],'T_S_local':I,
            'representation_role':r['representation_role']})
    replaced={r['id']:r for r in parts}; group=next(g for g in data['groups'] if any(r['id'] in replaced for r in g['rows']))
    newgroup={'id':group['id'],'path':str(D/'native/HARNESS_GROUP_R2.SLDASM'),
        'rows':[replaced.get(r['id'],r) for r in group['rows']]}
    tops=[]
    for gid in data['states']['service']['groups']:
        g=next(g for g in data['groups'] if g['id']==gid)
        tops.append({'id':gid,'native_path':newgroup['path'] if gid==group['id'] else g['path'],'T_S_local':I})
    detail=[byid[k] for k in DETAIL_IDS]+parts
    sources={str(Path(r['native_path'])) for r in detail+newgroup['rows']+tops if Path(r['native_path']).is_file()}
    sources.add(str(R1/'native/SERVICE_STAR_SERVICE_R1.SLDASM'))
    plan={'schema':'R2_ROUTE_NATIVE_DELTA_PLAN_V1','parts':parts,'group':newgroup,'top_rows':tops,'detail_rows':detail,
        'source_map_sha256':sha(R1/'inputs/NEUTRAL_SOURCE_MAP.json'),
        'source_native_files':[{'path':p,'sha256':sha(p)} for p in sorted(sources)],
        'source_plan_sha256':sha(R1/'inputs/INTEGRATED_ASSEMBLY_PLAN.json'),
        'expected_full_service_leaf_count':1110,'expected_full_service_solid_count':1513,
        'R1_changed':False,'portable_package':False,'material_policy':'New functional envelopes have no assigned physical material',
        'source_R1_zip_sha256':sha(R1/'SERVICE_STAR_R1_REVIEW_PACKAGE.zip')}
    write(PN,plan); print('prepared',len(detail),'detail parts; one group',len(newgroup['rows']))

def neutral():
    from OCP.TDocStd import TDocStd_Document
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.XCAFDoc import XCAFDoc_DocumentTool,XCAFDoc_ColorGen
    from OCP.TDataStd import TDataStd_Name
    from OCP.TopLoc import TopLoc_Location
    from OCP.Quantity import Quantity_Color,Quantity_TOC_RGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.Interface import Interface_Static
    from OCP.IFSelect import IFSelect_RetDone
    plan=read(PN); doc=TDocStd_Document(TCollection_ExtendedString('XmlXCAF'))
    st=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main());ct=XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    root=st.NewShape();TDataStd_Name.Set_s(root,TCollection_ExtendedString('INTERNAL_HARNESS_DETAIL_R2'))
    total=0
    for r in plan['detail_rows']:
        assert sha(r['step_path'])==r['source_sha256'];s=moved(load(r['step_path']),r['T_S_local']);total+=count(s)
        pl=st.AddShape(s,False,False);TDataStd_Name.Set_s(pl,TCollection_ExtendedString(r['id']))
        rgb=(.93,.42,.08) if r['id'].endswith('_0') and r['id'].startswith('release_') else (.36,.48,.58)
        ct.SetColor(pl,Quantity_Color(*rgb,Quantity_TOC_RGB),XCAFDoc_ColorGen)
        st.AddComponent(root,pl,TopLoc_Location())
    st.UpdateAssemblies(); w=STEPCAFControl_Writer();w.SetNameMode(True);w.SetColorMode(True)
    Interface_Static.SetCVal_s('write.step.schema','AP242DIS');Interface_Static.SetCVal_s('write.step.unit','MM')
    assert w.Transfer(doc,STEPControl_AsIs)
    p=D/'cad/INTERNAL_HARNESS_DETAIL_R2.step'; assert w.Write(str(p))==IFSelect_RetDone
    actual=load(p);assert count(actual)==total
    write(D/'results/DETAIL_NEUTRAL.json',{'status':'AP242_LOCAL_DETAIL_REOPENED','path':str(p),'sha256':sha(p),
        'leaf_instances':len(plan['detail_rows']),'solids':total,'reopened_solids':count(actual),
        'coordinate_frame':'S_mm; single transform applied before XCAF insertion',
        'full_spacecraft':False,'material_assignment':False})

def render():
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRep import BRep_Tool
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.TopLoc import TopLoc_Location
    def mesh(s):
        BRepMesh_IncrementalMesh(s,.15,False,.2,False).Perform();ex=TopExp_Explorer(s,TopAbs_FACE);tris=[]
        while ex.More():
            face=TopoDS.Face_s(ex.Current());loc=TopLoc_Location();tr=BRep_Tool.Triangulation_s(face,loc)
            assert tr is not None
            nodes=np.array([[p.X(),p.Y(),p.Z()] for p in [tr.Node(i).Transformed(loc.Transformation()) for i in range(1,tr.NbNodes()+1)]])
            tris.extend(nodes[np.array(tr.Triangle(i).Get())-1] for i in range(1,tr.NbTriangles()+1));ex.Next()
        return np.array(tris)
    plan=read(PN); report=read(D/'results/RELEASE_ROUTE_STATIC_CHECK.json')
    cutter=block(-124,-124,102,78,-65,137); geometries={};inputs=[]
    for row in plan['detail_rows']:
        if row['id'].startswith('release_power_data_route_') and row['id'].endswith('_0'):continue
        assert sha(row['step_path'])==row['source_sha256'];s=moved(load(row['step_path']),row['T_S_local'])
        clipped=common(s,cutter)
        if count(clipped):geometries[row['id']]=mesh(clipped)
        inputs.append({'id':row['id'],'sha256':row['source_sha256']})
    old=[mesh(moved(load(r['source']['step_path']),r['source']['T_S_local'])) for r in report['rows']]
    new=[mesh(load(r['output']['path'])) for r in report['rows']]
    fig=plt.figure(figsize=(18,10),facecolor='#f4f7fb');plt.rcParams['font.family']='DejaVu Sans'
    fig.suptitle('Internal release harness | source-bound routing correction',fontsize=22,fontweight='bold',y=.96)
    fig.text(.5,.915,'Actual STEP geometry  /  two logical branches  /  fixed endpoints  /  materials and physical junctions remain open',ha='center',fontsize=11,color='#435268')
    for i,title in enumerate(['R1 | detected penetration','R2 | corrected static corridor']):
        ax=fig.add_subplot(2,2,i+1,projection='3d');ax.set_facecolor('#f4f7fb')
        for name,t in geometries.items():
            if name in ['WP10_INTERNAL_BATTERY_BYPASS','release_power_data_route_0_1','release_power_data_route_1_1']:color='#3d8da8';alpha=.42
            elif name=='WP01-MT-M3RB-REUSED':color='#6d7e91';alpha=.6
            else:color='#a6b4c3';alpha=.24
            ax.add_collection3d(Poly3DCollection(t,facecolors=color,edgecolors='none',alpha=alpha))
        for t in old if i==0 else new:ax.add_collection3d(Poly3DCollection(t,facecolors='#d63849' if i==0 else '#eb7f15',edgecolors='none'))
        ax.set_xlim(-125,80);ax.set_ylim(-125,-63);ax.set_zlim(102,139);ax.set_box_aspect((205,62,37));ax.view_init(88,-90);ax.set_proj_type('ortho');ax.set_axis_off();ax.set_title(title,fontweight='bold',fontsize=14)
        ax.text2D(.5,-.025,'Each branch: 456.336 mm3 into M3RB' if i==0 else 'M3RB intersection: 0 | nominal nearest structure: 0.75 mm',transform=ax.transAxes,ha='center',fontsize=11,color='#7c2430' if i==0 else '#296145')
    ax=fig.add_subplot(2,2,3,projection='3d');ax.set_facecolor('#f4f7fb')
    for name,t in geometries.items():
        if name=='WP01-MT-M3RA-REUSED':continue
        ax.add_collection3d(Poly3DCollection(t,facecolors='#7397ad' if name.startswith('ROOT_') else '#97a5b5',edgecolors='none',alpha=.34))
    ax.add_collection3d(Poly3DCollection(new[0],facecolors='#eb7f15',edgecolors='none'))
    ax.set_xlim(-50,80);ax.set_ylim(-116,-65);ax.set_zlim(102,139);ax.set_box_aspect((130,51,37));ax.view_init(23,-72);ax.set_proj_type('ortho');ax.set_axis_off();ax.set_title('R2 | passage, retained bushes and support clearance',fontsize=13,fontweight='bold')
    a=fig.add_subplot(2,2,4);a.axis('off')
    lines=[('STATIC ROUTE CHECK','Two M3RB penetrations removed; no structure cut.\nExisting root bushes and keeper retained.'),
           ('PARAMETERS','Branch 0: 191.645 mm | branch 1: 116.645 mm\nNominal OD 4 mm | minimum arc radius 14 mm\nCommon endpoint S = (65, -80, 118) mm'),
           ('OPEN BEFORE HARNESS MANUFACTURE','Shared logical corridor is not two separated cables.\nConfirm real pins, bundle packing, strain relief,\nconnector access, bend rating and dynamic envelope.')]
    for y,(heading,body) in zip([.85,.56,.24],lines):a.text(.02,y,heading,fontsize=11,fontweight='bold',color='#172c42');a.text(.02,y-.08,body,fontsize=11,va='top',linespacing=1.6,color='#40566b')
    fig.subplots_adjust(left=.03,right=.97,top=.87,bottom=.07,hspace=.16,wspace=.1)
    fig.text(.5,.025,'Local cutaway for inspection, not the full spacecraft. Orange/red are visualization colors, not assigned materials. No power or flight release.',ha='center',fontsize=10,color='#435268')
    p=D/'views/INTERNAL_HARNESS_R2_COMPARISON.png';fig.savefig(p,dpi=140);plt.close(fig)
    write(D/'results/ROUTE_VISUAL.json',{'status':'ACTUAL_STEP_RENDER_PENDING_VISUAL_REVIEW','image':str(p),'sha256':sha(p),
        'pixels':[2520,1400],'input_check_sha256':sha(D/'results/RELEASE_ROUTE_STATIC_CHECK.json'),'context':inputs,'generated_image':False})
    print(str(p))

def native():
    sys.path.insert(0,str(R1/'tools'))
    import native_integrate as ni
    ni.OUT=D
    import build_integrated as bi
    bi.OUT=D
    plan=read(PN);rp=D/'results/NATIVE_ROUTE_DELIVERY_V2.json';assert not rp.exists()
    report={'status':'RUNNING','progress':[],'parts':[],'save_attempts':[],'coordinate_frame':'SOURCE_LOCAL_MM_AND_S_MM_SINGLE_T',
        'input_plan_sha256':sha(PN),'whole_design_complete':False,'ground_power_ready':False,'flight_ready':False}
    ni.configure_com();b=ni.PrototypeBuilder(rp,report);sw=b.sw
    prefs={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)}
    try:
        for s in plan['source_native_files']:assert sha(s['path'])==s['sha256']
        for k in prefs:sw.SetUserPreferenceToggle(k,k==111)
        sw.DocumentVisible(False,1)
        for row in plan['parts']:
            assert not Path(row['native_path']).exists(); b.import_part(row)
            fact=report['parts'][-1]['part_cold_reopen']['facts']
            assert abs(fact['volume_mm3']-row['expected_volume_mm3'])<row['expected_volume_mm3']*1e-5
        for tag,rows,target in [('group',plan['group']['rows'],Path(plan['group']['path'])),
              ('detail',plan['detail_rows'],D/'native/INTERNAL_HARNESS_DETAIL_R2.SLDASM'),
              ('service',plan['top_rows'],D/'native/SERVICE_STAR_SERVICE_R2.SLDASM')]:
            sw.DocumentVisible(False,2);sw.CommandInProgress=True
            saved=bi.make(b,rows,target,tag);sw.CommandInProgress=False
            opened=sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0
            doc=b.wrap(opened[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc')
            lookup=b.identity_inventory(asm,rows)
            for row in rows:
                comp=lookup[row['id']];assert ni.m.normalized(ni.m.val(comp,'GetPathName'))==ni.m.normalized(row['native_path'])
                actual=list(b.wrap(comp.Transform2,'IMathTransform').ArrayData)
                assert max(abs(x-y) for x,y in zip(actual,ni.h.t16(row['T_S_local'])))<1e-8 and comp.IsFixed()
            leaves=[]
            if tag=='service':
                for raw in asm.GetComponents(False) or []:
                    comp=b.wrap(raw,'IComponent2');p=ni.m.val(comp,'GetPathName')
                    if Path(p).suffix.lower()=='.sldprt':leaves.append(comp.ComponentReference)
                assert len(leaves)==len(set(leaves))==1110
                assert all(p['id'] in leaves for p in plan['parts'])
            report[tag]={'saved':saved,'cold_errors':opened[1],'cold_warnings':opened[2],
                'direct_children':len(rows),'full_leaf_count':len(leaves) if tag=='service' else len(rows),
                'needs_rebuild2':int(b.wrap(doc.Extension,'IModelDocExtension').NeedsRebuild2)}
            b.close_own_saved(doc,target,saved['sha256']);b.checkpoint('native_delta_cold_read',tag=tag)
        report.update(status='PASS_LOCAL_NATIVE_DELTA_COLD_READ_FIXED_POSE',
            R1_sources_unchanged=all(sha(x['path'])==x['sha256'] for x in plan['source_native_files']),
            existing_R1_native_directory_required=True,new_material_assignment=False,
            native_material_reason='Functional composite route envelopes, not physical homogeneous wires')
        assert report['R1_sources_unchanged'];b.checkpoint('complete')
    except Exception as e:
        import traceback
        report.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
    finally:
        for k,v in prefs.items():sw.SetUserPreferenceToggle(k,v)
        sw.CommandInProgress=False;sw.DocumentVisible(True,1);sw.DocumentVisible(True,2)
        if report.get('status','').startswith('PASS_') and report['session']['new_process'] and not b.documents():
            sw.ExitApp();report['own_empty_session_exited']=True;b.checkpoint('own_empty_session_exited')
        b.pythoncom.CoUninitialize()

def recover():
    # Close only the exact saved task part left open by the failed bbox assertion.
    # No generic CloseAllDocuments, process termination or changes to user docs.
    sys.path.insert(0,str(R1/'tools'));import native_integrate as ni
    import pythoncom,win32com.client
    from win32com.client import gencache
    ni.OUT=D;ni.configure_com();pythoncom.CoInitialize()
    rp=D/'results/NATIVE_ROUTE_DELIVERY.json';r=read(rp);assert r['status']=='FAILED_CLOSED'
    b=object.__new__(ni.PrototypeBuilder);b.pythoncom=pythoncom
    b.types=gencache.GetModuleForTypelib('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,32,0)
    try:raw=win32com.client.GetActiveObject('SldWorks.Application')
    except Exception:raw=win32com.client.DispatchEx('SldWorks.Application')
    b.sw=b.wrap(raw,'ISldWorks')
    assert int(ni.m.val(b.sw,'GetProcessID'))==r['session']['pid']
    own={ni.m.normalized(x['native_save']['path']):x['native_save']['sha256'] for x in r['parts'] if x.get('native_save')}
    observed=[]
    for doc,meta in b.documents():
        p=Path(meta['path']);key=ni.m.normalized(p)
        if key not in own:continue
        assert p.resolve().is_relative_to(D.resolve()) and sha(p)==own[key] and not meta['dirty']
        b.sw.CloseDoc(meta['title']);observed.append(meta)
    assert all(ni.m.normalized(m['path']) not in own for _,m in b.documents())
    for key,digest in own.items():
        p=next(Path(x['native_save']['path']) for x in r['parts'] if x.get('native_save') and ni.m.normalized(x['native_save']['path'])==key)
        dst=p.with_name(p.stem+'_FAILED_BBOX_01'+p.suffix)
        assert p.resolve().is_relative_to(D.resolve()) and dst.resolve().is_relative_to(D.resolve()) and not dst.exists() and sha(p)==digest
        p.rename(dst)
    archived=rp.with_name('NATIVE_ROUTE_ATTEMPT_01_REJECTED.json');assert not archived.exists();rp.rename(archived)
    # Current plan is already the corrected revision; do not mislabel it as the
    # missing historical input snapshot. The failed receipt retains its hash.
    other=D/'results/NATIVE_ROUTE_DELIVERY_V2.json'
    if other.exists():
        o=read(other);assert not o.get('parts') and o['session']['pid']==r['session']['pid']
        o['status']='FAILED_CLOSED_ATTACH_GUARD_NO_IMPORT';o['error']='Saved task part was conservatively treated as unknown at entry; now explicitly verified by path/hash/PID.'
        write(other,o);other.rename(D/'results/NATIVE_ROUTE_ATTEMPT_02_ATTACH_GUARD.json')
    write(D/'results/NATIVE_ROUTE_RECOVERY.json',{'status':'OWN_SAVED_FAILED_IMPORT_CLOSED_AND_ARCHIVED',
        'closed_documents':observed,'failure_receipt':str(archived),'failure_sha256':sha(archived),
        'R1_modified':False,'tolerance_relaxed':False,'original_plan_snapshot_available':False,
        'original_plan_sha256':r['input_plan_sha256'],'pid':r['session']['pid'],
        'fix':'Replace conservative Add_s expected box with AddOptimal exact source box'})
    pythoncom.CoUninitialize()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','neutral','render','native','recover']);a=ap.parse_args()
    globals()[a.mode]()
