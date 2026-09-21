"""Build bounded solar delta STEP sources, not a native assembly.

This file is prepared for the root's sole CAD writer. It was not executed by the
solar algebra agent. --build is required to import build123d/OCC. Existing N and
all parent STEP/native files are read-only. Output stays under system_completion.
"""
from pathlib import Path
import argparse
import copy
import ctypes
import gc
import hashlib
import itertools
import json
import os
import sys
import threading
import time

C=Path(__file__).resolve().parents[1]
N=C.parent/'reuse_closure'
OUT=C/'solar/generated_parts'
MAX_RSS_MIB=1400
MIN_AVAILABLE_MIB=512


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resource_state():
    if os.name!='nt':raise RuntimeError('Memory guard configured for Windows; supply an audited platform guard before porting.')
    class MS(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(x,ctypes.c_ulonglong) for x in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
    m=MS();m.length=ctypes.sizeof(MS)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise RuntimeError('GlobalMemoryStatusEx failed')
    class PM(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(x,ctypes.c_size_t) for x in ('peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]
    pm=PM();pm.cb=ctypes.sizeof(PM)
    ctypes.windll.kernel32.GetCurrentProcess.restype=ctypes.c_void_p
    process=ctypes.windll.kernel32.GetCurrentProcess()
    get=ctypes.windll.psapi.GetProcessMemoryInfo
    get.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
    if not get(process,ctypes.byref(pm),pm.cb):raise RuntimeError('GetProcessMemoryInfo failed')
    return {'rss_MiB':pm.working/2**20,'available_MiB':m.available/2**20}


def guard():
    r=resource_state()
    if r['rss_MiB']>MAX_RSS_MIB or r['available_MiB']<MIN_AVAILABLE_MIB:
        raise MemoryError(f'SOLAR CAD guard {r}, limits rss<={MAX_RSS_MIB} MiB / available>={MIN_AVAILABLE_MIB} MiB')
    return r


def mul(a,b):return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def moved_bounds(b,old,new):
    pts=[]
    for p in itertools.product(*zip(b['min_mm'],b['max_mm'])):
        local=[sum(old[j][i]*(p[j]-old[j][3]) for j in range(3)) for i in range(3)]
        pts.append([sum(new[i][j]*local[j] for j in range(3))+new[i][3] for i in range(3)])
    lo=[min(p[i] for p in pts) for i in range(3)];hi=[max(p[i] for p in pts) for i in range(3)]
    return {'min_mm':lo,'max_mm':hi,'size_mm':[hi[i]-lo[i] for i in range(3)]}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--build',action='store_true');args=ap.parse_args()
    layout_path=C/'solar/SOLAR_LAYOUT.json';hinge_path=C/'results/SOLAR_HINGE_DELTA.json'
    layout=json.loads(layout_path.read_text(encoding='utf-8'))
    hinge=json.loads(hinge_path.read_text(encoding='utf-8'))
    if not all(r['pass'] for r in hinge['old_formula_native_binding']):raise RuntimeError('Current native binding failed')
    if layout['configuration']['selected_stack_step_mm']!=4.5:raise RuntimeError('Only audited 4.5mm design supported')
    for source_path,expected in hinge['source_sha256'].items():
        if sha(source_path)!=expected:raise RuntimeError(f'Frozen source changed: {source_path}')
    for item in layout['actual_step_source_screen']:
        if sha(item['path'])!=item['sha256']:raise RuntimeError('Frozen substrate STEP changed')
    if not args.build:
        print(json.dumps({'status':'PREPARED_NOT_EXECUTED','step_files_to_generate':10,'replaced_existing_instances':8,'repositioned_other_instances':16,'new_layer_instances':168,'native_assembly_writer':'root/dm_reuse only','command':'<CAD Python> build_solar_delta.py --build','rss_limit_MiB':1400,'minimum_available_MiB':512}))
        return
    before=guard(); stop=threading.Event()
    def monitor():
        while not stop.wait(.5):
            try:guard()
            except Exception as exc:
                print(str(exc),file=sys.stderr,flush=True)
                os._exit(137)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try:
        # CAD imports begin only after explicit --build and global/process guards.
        from build123d import Box,Cylinder,Location,Plane,export_step
        def box(size,c=(0,0,0)):return Box(*size).moved(Location(tuple(c)))
        def cylinder(d,length,c=(0,0,0),axis=(0,0,1)):
            return Cylinder(d/2,length).moved(Plane(origin=tuple(c),z_dir=axis).location)
        def bore(shape,d,length,c=(0,0,0),axis=(0,0,1)):
            return shape-cylinder(d,length,c,axis)
        def rod(a,b,d):
            v=[b[i]-a[i] for i in range(3)];length=sum(x*x for x in v)**.5
            return cylinder(d,length,[(a[i]+b[i])/2 for i in range(3)],v)
        def edge_frame(side,leaf,sx):
            # Directly preserves WP03 spacecraft_model.py lines261,265-272,281-298.
            s=box((4,200,2),(sx*152,0,0))
            um=162 if leaf<3 else 188
            moving=cylinder(8,6,(sx*um,-100,0),(1,0,0))
            moving=moving+rod((sx*um,-100,0),(sx*um,-85,0),3)
            moving=moving+box((um+3-152,4,2),(sx*(152+um+3)/2,-85,0))
            moving=bore(moving,4.4,10,(sx*um,-100,0),(1,0,0))
            s=bore(s+moving,4.4,60,(sx*um,-100,0),(1,0,0))
            # This frame owns its outgoing fixed fork. Child barrel stays at z=0.
            hinge_no=leaf+1
            u1,u2=(156,168) if hinge_no==2 else (182,194)
            axis_z=(-side if hinge_no==2 else side)*4.5
            zoff=-axis_z
            fork=None
            for u in (u1,u2):
                ear=cylinder(8,4,(sx*u,0,0),(1,0,0))
                ear=ear+rod((sx*u,0,0),(sx*u,-15,zoff),3)
                ear=bore(ear,4.4,8,(sx*u,0,0),(1,0,0))
                fork=ear if fork is None else fork+ear
            fork=fork+box((u2+2-152,4,2),(sx*(152+u2+2)/2,-15,zoff))
            return s+fork.moved(Location((0,100,axis_z)))
        OUT.mkdir(parents=True,exist_ok=True)
        emitted={}
        def save(shape,key,role,mass=None):
            guard()
            valid=shape.is_valid
            if callable(valid):valid=valid()
            solids=len(shape.solids())
            if not valid or solids!=1:raise RuntimeError(f'{key} invalid or unexpected solids={solids}')
            p=OUT/(key+'.step');export_step(shape,p)
            b=shape.bounding_box()
            record={'path':str(p),'sha256':sha(p),'solids_actual':solids,'sheets_actual':0,
                    'local_bounds_mm':{'min_mm':list(b.min),'max_mm':list(b.max),'size_mm':list(b.size)},
                    'volume_mm3':float(shape.volume),'geometry_role':role,'assigned_mass_kg':mass,
                    'resource_after':guard()}
            emitted[key]=record;print(json.dumps({'emitted':key,'bytes':p.stat().st_size,'solids':solids}),flush=True)
        for side in (-1,1):
            for leaf in (1,2):
                for sx in (-1,1):
                    key=f'wing_edge_frame_{side}_{leaf}_{sx}'
                    s=edge_frame(side,leaf,sx)
                    save(s,key,'PHYSICAL_EDGE_FRAME_CANDIDATE')
                    del s;gc.collect();guard()
        save(box((40.15,80.15,.29)),'AZUR81442_CIC_RECTANGULAR_PACKAGE','FINITE_THICKNESS_CIC_PACKAGE_PROXY',.0036)
        gc.collect();guard()
        save(box((40.15,80.15,.10)),'CIC_BONDLINE_0_10MM','FINITE_THICKNESS_BONDLINE_DESIGN_GEOMETRY',None)
        identity=[[1.,0,0,0],[0,1.,0,0],[0,0,1.,0],[0,0,0,1.]]
        plans={}
        for state,receipt_name in [('parking','NATIVE_PARKING.json'),('released','NATIVE_RELEASED.json'),('service','NATIVE_SERVICE_RECOVERY_V2.json')]:
            parent_path=N/'results'/receipt_name
            parent=json.loads(parent_path.read_text(encoding='utf-8-sig'))
            rows=copy.deepcopy(parent['rows']); byid={r['id']:r for r in rows}
            frames={r['id']:r for r in hinge['states'][state]['frames']}
            changed=[]
            for side in (-1,1):
                for leaf in (1,2,3):
                    panel=frames[f'wing_{side}_leaf_{leaf}']; new_t=panel['T_local_to_S_mm']
                    ids=[]
                    if leaf in (2,3):ids.append(f'wing_{side}_leaf_{leaf}')
                    for sx in (-1,1):ids.append(f'wing_edge_frame_{side}_{leaf}_{sx}')
                    for ident in ids:
                        r=byid[ident];old_t=r['native_T_local_to_S'];old_bounds=r['world_bounds_mm']
                        r['solar_parent_native_source']={'path':r['native_path'],'sha256':r['native_sha256']}
                        r['T_S_local']=new_t;r['native_T_local_to_S']=new_t
                        r['change']='SOLAR_STACK_4_5MM_TRANSFORM_DELTA'
                        if ident in emitted:
                            part=emitted[ident];r['source_step']={'path':part['path'],'sha256':part['sha256']}
                            r['step_path']=part['path'];r['source_sha256']=part['sha256'];r['source_revision']='SOLAR_STACK_4_5MM_FIXED_FORK_REBUILD'
                            r['native']=None;r['native_path']=None;r['native_sha256']=None
                            r['expected_solids']=part['solids_actual'];r['change']='REPLACE_EDGE_FRAME_STEP_REQUIRES_NATIVE_IMPORT'
                            r['world_bounds_mm']=moved_bounds(part['local_bounds_mm'],identity,new_t)
                            r['mass_source']='CAD_ESTIMATE_AL2700_UNQUALIFIED';r['source_mass_kg']=part['volume_mm3']*2.7e-6
                        else:r['world_bounds_mm']=moved_bounds(old_bounds,old_t,new_t)
                        changed.append(ident)
                    if leaf in (2,3):
                        for sx in (-1,1):
                            ident=f'wing_hinge_pin_{side}_{leaf}_{sx}';r=byid[ident]
                            old_t=r['native_T_local_to_S'];new_pin=copy.deepcopy(old_t)
                            new_pin[0][3]=sx*(162 if leaf==2 else 188)
                            new_pin[1][3]=panel['root_S_mm'][1];new_pin[2][3]=panel['root_S_mm'][2]
                            r['world_bounds_mm']=moved_bounds(r['world_bounds_mm'],old_t,new_pin)
                            r['T_S_local']=new_pin;r['native_T_local_to_S']=new_pin;r['change']='SOLAR_SERIAL_HINGE_PIN_POSE_DELTA';changed.append(ident)
            added=[]
            for cell in layout['cells']:
                for kind,key,tkey,mass in [('CIC','AZUR81442_CIC_RECTANGULAR_PACKAGE','CIC_T_local_to_S_mm',.0036),('BOND','CIC_BONDLINE_0_10MM','ADHESIVE_T_local_to_S_mm',None)]:
                    part=emitted[key];ident=cell['id']+'_'+kind;t=cell['states'][state][tkey]
                    row={'id':ident,'part_key':key,'pn':'AZUR_81442' if kind=='CIC' else 'WP09F_BONDLINE_REQUIREMENT',
                         'T_S_local':t,'native_T_local_to_S':t,'world_bounds_mm':moved_bounds(part['local_bounds_mm'],identity,t),
                         'representation_role':'PACKAGE_BOUNDING_SOLID' if kind=='CIC' else 'BONDLINE_DESIGN_SOLID',
                         'product_role':'ONBOARD_CANDIDATE','parent_assembly':'SOLAR_WING','mount_interface':cell['parent_leaf']+'_SOLAR_FACE',
                         'source_revision':'AZUR_DB00010891-01_PACKAGE_ONLY' if kind=='CIC' else 'DESIGN_0_05_TO_0_15MM_NOT_SELECTED_MATERIAL',
                         'mass_source':'VENDOR_MEAN_REFERENCE' if kind=='CIC' else 'UNKNOWN_POSITIVE',
                         'source_mass_kg':mass,'qualification_status':'NOT_EVALUATED','expected_solids':1,'expected_sheets':0,
                         'source_step':{'path':part['path'],'sha256':part['sha256']},'step_path':part['path'],'source_sha256':part['sha256'],
                         'native':None,'native_path':None,'native_sha256':None,'change':'ADD_FINITE_THICKNESS_SOLAR_LAYER',
                         'physical_tests':0,'manufacturing_release':False,'geometry_limit':'Supplier tab/corner geometry or selected bond material not implied by box.'}
                    rows.append(row);added.append(ident)
            if len(set(r['id'] for r in rows))!=len(rows):raise RuntimeError('Duplicate solar identity')
            plan={'identity':'SOLAR_DELTA_NATIVE_IMPORT_PLAN_V1','state':state,'parent_receipt':str(parent_path),'parent_receipt_sha256':sha(parent_path),
                  'parent_native':parent.get('native_save'),'rows':rows,'expected_component_count':len(rows),
                  'changed_existing_ids':sorted(set(changed)),'new_instance_ids':added,
                  'expected_solid_count':sum(r['expected_solids'] for r in rows),
                  'scope':'Source/import plan only; cold native acceptance is required from sole CAD writer.',
                  'candidate_deployment_path':layout['deployment_path'],
                  'build_approved':False,'continuous_motion_verified':False,'manufacturing_release':False}
            plan_path=C/'results'/f'SOLAR_{state.upper()}_INSTANCE_PLAN.json'
            plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            plans[state]={'path':str(plan_path),'sha256':sha(plan_path),'components':len(rows),'changed_existing':len(set(changed)),'added':len(added),'expected_solids':plan['expected_solid_count']}
        manifest={'identity':'SOLAR_DELTA_STEP_BUILD_RECEIPT_V1','status':'STEP_GEOMETRY_EMITTED_NATIVE_IMPORT_NOT_RUN',
             'source_inputs_sha256':{str(layout_path):sha(layout_path),str(hinge_path):sha(hinge_path),str(Path(__file__)):sha(Path(__file__))},
             'emitted_parts':emitted,'instance_plans':plans,'initial_resource':before,'final_resource':guard(),
             'parent_files_modified':False,'build_approved':False,'native_assembly_generated':False,'manufacturing_release':False}
        (C/'results/SOLAR_DELTA_STEP_BUILD.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':manifest['status'],'parts':len(emitted),'plans':plans}),flush=True)
    finally:stop.set()


if __name__=='__main__':main()
