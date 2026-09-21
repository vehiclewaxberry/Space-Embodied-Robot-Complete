"""Independent exported STEP review of WP04 R07 nominal connections.

Only --execute-geometry imports CAD. Root owns serial execution/resource guards.
The reviewer reuses its own frozen R01 geometry primitives, never producer PASS
functions. Thread-core proxy intersections are spatially bounded UNKNOWN.
"""
from __future__ import annotations
import argparse
import gc
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
PRIOR = RUN.parent / 'wp03_bounded_20260906_161431'
BASE = PRIOR / 'review/review_r01.py'
spec = importlib.util.spec_from_file_location('independent_prior_review', BASE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
LIN_TOL, VOL_TOL, AREA_TOL = base.LIN_TOL, base.VOL_TOL, base.AREA_TOL
sha256, progress = base.sha256, base.progress
vec, unit, plus, minus, scale, dot, norm = base.vec, base.unit, base.plus, base.minus, base.scale, base.dot, base.norm
PHYSICAL = {'PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY'}


def item(name, ok, **details):
    return dict(check=name, status='PASS' if ok else 'FAIL', **details)


def expected_axes():
    rows = {}
    for side in (-1, 1):
        for level in (-1, 1):
            for x in (15, 164, -164):
                rows[f'R07_RAIL_{side}_{level}_{x}'] = (x, side*107.15, level)
    for k, x in enumerate((-115, -40)):
        for side in (-1, 1):
            for outer in (False, True):
                rows[f'R07_HOLD_{k}_{side}_' + ('OUTER' if outer else 'INNER')] = (x-3 if outer else x, side*(107.15 if outer else 94.15), 1)
    return rows


def expected_bores(key):
    """Independent selected dimensions, including every load-path counterpart."""
    x,y,sign=expected_axes()[key]
    rows={}
    if key.startswith('R07_RAIL_'):
        side,level,hx=map(int,key.removeprefix('R07_RAIL_').split('_'))
        z=level*107.15
        rows[f'RB_longeron_{side}_{level}']=(z,12)
        if hx==15:rows[key+'_sleeve']=(z,8)
        else:rows[f'RB_end_plug_{1 if hx>0 else -1}_{side}_{level}']=(z,7.8)
        if hx!=-164:
            rootx=20 if hx==15 else 160
            idx={(20,-1):0,(20,1):1,(160,-1):2,(160,1):3}[(rootx,side)]
            rows[f'R07_upper_cap_{rootx}_{side}' if level>0 else f'RB_lower_spacer_{idx}']=(114.65 if level>0 else -99.65,3)
        if level<0 and hx!=15:rows[f'wing_root_fork_{side}_{1 if hx>0 else -1}']=(-114.15,2)
    else:
        k,side,which=key.removeprefix('R07_HOLD_').split('_');k,side=int(k),int(side)
        outer=which=='OUTER'
        rows[f'hold_roof_lug_{k}_{side*94.15}']=(115.65,5) if outer else (112.15,12)
        if outer:
            rows[f'RB_longeron_{side}_1']=(107.15,12)
            rows[key+'_sleeve']=(107.15,8)
        else:rows[f'hold_crossbeam_{k}']=(101.15,10)
        if side<0:rows[f'hold_pivot_clevis_{k}']=(119.4,2.5)
    return {name:dict(origin_mm=(x,y,z),axis=(0,0,1),length_mm=h,diameter_mm=4.5) for name,(z,h) in rows.items()}


def load_inputs(args):
    raw = json.loads(args.contract.read_text(encoding='utf-8-sig'))
    receipt = json.loads(args.receipt.read_text(encoding='utf-8-sig'))
    oldpath = PRIOR / 'candidate/results/service_structure_instances.json'
    old = json.loads(oldpath.read_text(encoding='utf-8-sig'))
    ids = [r['id'] for r in receipt['instances']]
    reg = {r['id']: r for r in receipt['instances']}
    oldreg = {r['id']: r for r in old['instances']}
    changed = set(ids) - set(oldreg)
    for key in set(ids) & set(oldreg):
        if any(reg[key].get(k) != oldreg[key].get(k) for k in ('volume_mm3', 'bounds', 'T_S_local', 'representation_role')):
            changed.add(key)
    # Explicitly inspect each intended modified interface, even if a producer
    # accidentally leaves an unchanged shape/receipt and thus no numerical delta.
    changed.update(k for k in ids if k.startswith(('R07_', 'RB_longeron_', 'RB_lower_spacer_', 'RB_pillar_tierod_', 'RB_pillar_top_washer_', 'RB_end_screw_', 'shear_web_', 'wing_root_fork_', 'hold_roof_lug_', 'hold_pivot_clevis_')))
    checks = [item('units_frame_schema', raw.get('units') == 'mm' and raw.get('frame') == 'S' and raw.get('schema') == 'WP04_R07_CONNECTIONS_V1'),
              item('receipt_unique_ids', len(ids) == len(set(ids))),
              item('original_nonarm_inventory_retained', set(oldreg) <= set(ids), missing=sorted(set(oldreg)-set(ids))),
              item('contract_affected_covers_geometry_changes', changed <= set(raw.get('affected_instance_ids', [])), missing=sorted(changed-set(raw.get('affected_instance_ids', []))))]
    local_ids=raw.get('local_instance_ids',[])
    checks.append(item('explicit_local_inventory_covers_affected',bool(local_ids) and len(local_ids)==len(set(local_ids)) and set(local_ids)<=set(ids) and set(raw.get('affected_instance_ids',[]))<=set(local_ids)))
    conns = raw['connections']
    byid = {c['connection_id']: c for c in conns}
    expected = expected_axes()
    checks.append(item('20_unique_expected_connections', len(conns) == 20 and set(byid) == set(expected)))
    used = set()
    for key, (x, y, sign) in expected.items():
        c = byid.get(key, {})
        p, a = c.get('origin_mm', [0, 0, 0]), c.get('axis', [0, 0, 0])
        checks.append(item('axis:'+key, abs(p[0]-x)<LIN_TOL and abs(p[1]-y)<LIN_TOL and a == [0, 0, sign]))
        hardware = list(c.get('hardware', {}).values())
        checks.append(item('independent_hardware:'+key, len(hardware)==4 and len(set(hardware))==4 and not used.intersection(hardware) and set(hardware)<=set(ids)))
        used.update(hardware)
        checks.append(item('member_identity:'+key, bool(c.get('body_ids')) and set(c.get('body_ids', []))<=set(ids) and {b['instance_id'] for b in c.get('bore_segments', [])}==set(c.get('body_ids', []))))
        expected_members=expected_bores(key)
        actual_bores=c.get('bore_segments',[])
        bore_map={b['instance_id']:b for b in actual_bores}
        valid=set(expected_members)==set(bore_map) and len(bore_map)==len(actual_bores)
        for member,expect in expected_members.items():
            actual=bore_map.get(member,{})
            for field in ('length_mm','diameter_mm'):
                valid=valid and abs(actual.get(field,-1)-expect[field])<LIN_TOL
            for field in ('origin_mm','axis'):
                value=actual.get(field,())
                valid=valid and len(value)==3 and all(abs(a-b)<LIN_TOL for a,b in zip(value,expect[field]))
        checks.append(item('independent_complete_bore_contract:'+key,valid,expected_members=sorted(expected_members)))
    checks.append(item('80_distinct_standard_parts', len(used)==80))
    sleeves = [c.get('sleeve_id') for c in conns if c.get('sleeve_id')]
    checks.append(item('8_unique_compression_sleeves', len(sleeves)==8 and len(set(sleeves))==8))
    paths = [p for c in conns for p in c.get('paths', [])]
    checks.append(item('128_unique_paths_including_8_sleeves', len(paths)==128 and len({p.get('path_id') for p in paths})==128))
    data = dict(step=dict(path=str(args.step.resolve()), sha256=sha256(args.step)), connections=conns,
                instances=[dict(instance_id=r['id'], step_label=r['id'], role=r['representation_role']) for r in receipt['instances']])
    source=RUN/'candidate/r07_design.py'
    checks.append(item('producer_source_sha256_binding',raw.get('source_sha256')==sha256(source)))
    inputs=(args.contract,args.receipt,args.step,args.local_step,oldpath,BASE,Path(__file__),source,
            RUN/'candidate/root_structure.py',RUN/'candidate/spacecraft_model.py',RUN/'candidate/design_parameters.json')
    bindings = {str(p.resolve()):sha256(p) for p in inputs}
    return raw, receipt, data, checks, changed, bindings


class Review(base.GeometryReview):
    def bore(self, row, shape=None):
        key = row['instance_id']; shape = self.shapes[key] if shape is None else shape
        origin, axis = vec(row['origin_mm']), unit(row['axis'])
        radius, length = float(row['diameter_mm'])/2, float(row['length_mm'])
        matching = []
        for face in shape.faces():
            surf = self.Adaptor(face.wrapped, True)
            if surf.GetType() != self.CYL: continue
            cy = surf.Cylinder(); p = vec((cy.Location().X(),cy.Location().Y(),cy.Location().Z()))
            d = vec((cy.Axis().Direction().X(),cy.Axis().Direction().Y(),cy.Axis().Direction().Z()))
            if abs(cy.Radius()-radius)<LIN_TOL and abs(abs(dot(d,axis))-1)<LIN_TOL and base.axis_distance(p,origin,axis)<LIN_TOL:
                matching.append(float(face.area))
        void = self.cylinder(radius-.001, origin, axis, -length/2+.001, length/2-.001)
        blocked = self.overlap(shape, void)
        # Hollow rails need full support only through their two 2 mm walls.
        # End plugs have a crossing tapped-core hole; their end rings remain
        # independently closed while the central wall interruption is explicit.
        spans = [(-length/2, length/2)]
        if key.startswith('RB_longeron_'): spans=[(-6,-4),(4,6)]
        elif key.startswith('RB_end_plug_'): spans=[(-3.9,-1.7),(1.7,3.9)]
        wallrows=[]
        for lo,hi in spans:
            ring=self.annulus(radius+.001,radius+.051,origin,axis,lo+.001,hi-.001)
            required=self.volume(ring); actual=self.volume(shape & ring)
            wallrows.append(dict(interval_mm=[lo,hi], required_mm3=required, actual_mm3=actual, status='PASS' if abs(actual-required)<=max(VOL_TOL,required*1e-5) else 'FAIL'))
        return dict(status='PASS' if matching and blocked<=VOL_TOL and all(r['status']=='PASS' for r in wallrows) else 'FAIL', actual_axis_cylinder_areas_mm2=matching, void_material_mm3=blocked, support_wall_spans=wallrows)

    def support(self, row):
        a,b=self.shapes[row['hardware_id']], self.shapes[row['member_id']]
        p,n=vec(row['point_mm']),unit(row['normal'])
        facesa,facesb=self.planar_faces(a,p,n),self.planar_faces(b,p,n)
        area=0.0
        for fa in facesa:
            for fb in facesb:
                common=fa & fb
                if common is not None: area+=float(common.area)
        inner,outer=float(row['inner_d_mm'])/2,float(row['outer_d_mm'])/2
        expected=math.pi*(outer**2-inner**2)
        ok=0<inner<outer and abs(area-expected)<=max(AREA_TOL,expected*1e-5)
        return dict(status='PASS' if ok else 'FAIL', contact_area_mm2=area, expected_annulus_mm2=expected, scope='Nominal planar material support only, no bearing stress/preload credit')

    def local_equivalence(self, path, local_ids):
        from build123d import import_step
        progress('local_step_import_start',path=str(path)); tree=import_step(path)
        local={}
        def visit(n):
            if getattr(n,'children',()):
                for c in n.children:visit(c)
            elif getattr(n,'label',''):
                label=n.label
                if label in local:raise ValueError('Duplicate local STEP label: '+label)
                loc=n.global_location; bare=type(n)(n.wrapped)
                if bare.parent is not None or getattr(bare,'children',()):raise ValueError('Local detach failed')
                local[label]=bare.located(loc)
        visit(tree);del tree;gc.collect()
        rows=[]
        expected={base.imported_label(k):k for k in local_ids}
        rows.append(item('local_inventory_equals_explicit_contract',set(local)==set(expected),missing=sorted(set(expected)-set(local)),extra=sorted(set(local)-set(expected))))
        for label in set(local)&set(expected):
            key=expected[label];a,b=local[label],self.shapes[key]
            delta=self.volume(a-b)+self.volume(b-a)
            rows.append(item('local_global_material_equivalence:'+key,delta<=VOL_TOL,symmetric_difference_mm3=delta))
        del local;gc.collect();progress('local_step_equivalence_done',checked=len(rows))
        return rows

    def sleeves(self, cs):
        rows=[]
        for c in cs:
            key=c.get('sleeve_id')
            if not key:continue
            s=self.shapes[key];p=c['origin_mm'];z=107.15 if c['axis'][2]>0 else -107.15
            expected=self.annulus(2.25,3.25,(p[0],p[1],z),(0,0,1),-4,4)
            delta=self.volume(s-expected)+self.volume(expected-s)
            rail=next(k for k in c['body_ids'] if k.startswith('RB_longeron_'))
            bearing=[]
            for lev in (-1,1):
                area=0.0;point=(p[0],p[1],z+lev*4)
                for fa in self.planar_faces(s,point,(0,0,1)):
                    for fb in self.planar_faces(self.shapes[rail],point,(0,0,1)):
                        common=fa&fb
                        if common is not None:area+=float(common.area)
                bearing.append(area)
            target=math.pi*(3.25**2-2.25**2)
            rows.append(item('sleeve_geometry_and_two_faces:'+key,delta<=VOL_TOL and all(abs(a-target)<=AREA_TOL for a in bearing),symmetric_difference_mm3=delta,actual_end_support_mm2=bearing,expected_each_mm2=target))
        return rows

    def pillar_stack(self):
        rows=[]
        for idx,(x,side) in enumerate(((20,-1),(20,1),(160,-1),(160,1))):
            p=(x,side*94.15,114.65);cap=f'R07_upper_cap_{x}_{side}'
            row=dict(instance_id=cap,origin_mm=p,axis=(0,0,1),length_mm=3,diameter_mm=4.5)
            rows.append(dict(check='shared_pillar_cap_bore:'+cap,**self.bore(row)))
            rod=f'RB_pillar_tierod_{idx}';lo,hi=self.bounds[rod]
            rows.append(item('single_231mm_pillar_rod:'+rod,abs(lo[2]+113.85)<LIN_TOL and abs(hi[2]-121.15)<LIN_TOL,actual_bounds_mm=[lo,hi]))
            face=dict(hardware_id=f'RB_pillar_top_washer_{idx}',member_id=cap,point_mm=(x,side*94.15,116.15),normal=(0,0,1),inner_d_mm=4.5,outer_d_mm=9)
            rows.append(dict(check='pillar_top_bearing:'+cap,**self.support(face)))
        return rows

    def rear_and_axial(self):
        rows=[]
        rear=[k for k in self.shapes if 'rear' in k.lower() and 'bulkhead' in k.lower()]
        for side in (-1,1):
            for level in (-1,1):
                for sign in (-1,1):
                    screw=f'RB_end_screw_{sign}_{side}_{level}'
                    if screw not in self.shapes:continue
                    lo,hi=self.bounds[screw];tip=lo[0] if sign>0 else hi[0]
                    wanted=169 if sign>0 else -168
                    rows.append(item('axial_screw_tip_clear_of_transverse:'+screw,abs(tip-wanted)<LIN_TOL,tip_x_mm=tip,expected_mm=wanted))
                    transverse=f'R07_RAIL_{side}_{level}_{sign*164}_screw'
                    overlap=self.overlap(self.shapes[screw],self.shapes[transverse])
                    rows.append(item('perpendicular_screws_no_crossing:'+screw,overlap<=VOL_TOL,overlap_mm3=overlap))
                washer=f'R07_rear_axial_washer_{side}_{level}'
                if len(rear)!=1:
                    rows.append(dict(check='rear_bulkhead_identity',status='UNKNOWN',matching_ids=rear));continue
                member=rear[0];p=(-189,side*107.15,level*107.15)
                # Current chosen revision reduces internal corner clearance bores
                # to D4.5. Launch-provider hole pattern remains outside this check.
                bore=dict(instance_id=member,origin_mm=(-186,p[1],p[2]),axis=(1,0,0),length_mm=6,diameter_mm=4.5)
                rows.append(dict(check='rear_corner_bore:'+washer,**self.bore(bore)))
                face=dict(hardware_id=washer,member_id=member,point_mm=p,normal=(-1,0,0),inner_d_mm=4.5,outer_d_mm=8)
                rows.append(dict(check='rear_washer_support:'+washer,**self.support(face)))
        return rows

    def static(self,affected):
        ids=[r['instance_id'] for r in self.data['instances'] if r['role'] in PHYSICAL]
        total=narrow=0; findings=[]; thread=[]
        for i,a in enumerate(ids):
            for b in ids[i+1:]:
                if a not in affected and b not in affected:continue
                total+=1; amin,amax=self.bounds[a];bmin,bmax=self.bounds[b]
                if any(min(x,y)-max(u,v)<=LIN_TOL for x,y,u,v in zip(amax,bmax,amin,bmin)):continue
                narrow+=1
                if narrow%50==0:progress('static_pairs',broad=total,narrow=narrow)
                common=self.shapes[a]&self.shapes[b];volume=self.volume(common)
                if volume<=VOL_TOL:continue
                pair={a,b}; screw=next((k for k in pair if k.startswith('RB_end_screw_')),None)
                plug=next((k for k in pair if k.startswith('RB_end_plug_')),None)
                if screw and plug and screw.removeprefix('RB_end_screw_')==plug.removeprefix('RB_end_plug_'):
                    sign,side,level=map(int,screw.removeprefix('RB_end_screw_').split('_'))
                    # Only the independently known axial tap-core engagement is
                    # UNKNOWN, never the full pair. Positive material elsewhere fails.
                    lo,hi=(169,177) if sign>0 else (-177,-168)
                    region=self.cylinder(2.001,(0,side*107.15,level*107.15),(1,0,0),lo-.001,hi+.001)
                    residual=self.volume(common-region)
                    if residual<=VOL_TOL:
                        thread.append(dict(ids=[a,b],status='UNKNOWN',reason='THREADLESS_M4_IN_D3p3_TAP_CORE',overlap_mm3=volume,allowed_x_interval_mm=[lo,hi],residual_outside_region_mm3=residual));continue
                findings.append(dict(ids=[a,b],status='FAIL',material_overlap_mm3=volume))
        return dict(status='FAIL' if findings else 'UNKNOWN' if thread else 'PASS',expected_pair_count=total,narrow_pair_count=narrow,findings=findings,thread_geometry_unknown=thread)

    def assembly_path(self,p,c):
        if 'assembly_absent_ids' not in p:
            return dict(status='UNKNOWN',reason='No explicit per-path assembly-phase identity set')
        physical={r['instance_id'] for r in self.data['instances'] if r['role'] in PHYSICAL}
        absent=set(p['assembly_absent_ids'])
        if not absent<=set(self.shapes):return dict(status='FAIL',reason='Absent phase IDs not in final registry',unknown_ids=sorted(absent-set(self.shapes)))
        expected_present=physical-absent-{p.get('moving_id')}
        if 'present_instance_ids' in p and set(p['present_instance_ids']) != expected_present:
            return dict(status='FAIL',reason='Phase present/absent sets do not cover the final physical inventory',missing=sorted(expected_present-set(p['present_instance_ids'])),extra=sorted(set(p['present_instance_ids'])-expected_present))
        row=dict(p,absent_instance_ids=sorted(absent),present_instance_ids=sorted(physical-absent),allowed_target_ids=[])
        if p['kind'] in ('TOOL_CYLINDER','TOOL_TUBE'):
            row.update(kind='CYLINDRICAL_TOOL',radius_mm=p['outer_d_mm']/2,inner_radius_mm=p.get('inner_d_mm',0)/2)
        elif p['kind']=='PART_TRANSLATION':
            row['kind']='AXIS_ALIGNED_TRANSLATION' if p.get('moving_id')==c.get('sleeve_id') else 'AXIAL_FASTENER_TRANSLATION'
        return super().path(row)

    def reliefs_and_counterbores(self,cs):
        rows=[]
        for side in (-1,1):
            for x in (15,165):
                # Actual lower edge is open; inspect the precise nominal .25 mm
                # clearance window rather than requiring an enclosed hole.
                probe=self.Box(12.5-.002,2-.002,3.25-.002).moved(self.Location((x,side*102.15,(-101.15-97.9)/2)))
                v=self.overlap(probe,self.shapes[f'shear_web_{side}'])
                rows.append(item(f'lower_web_notch_{side}_{x}',v<=VOL_TOL,material_mm3=v,nominal_wing_edge_gap_mm=.25))
        for c in cs:
            cb=c.get('counterbore')
            if not cb:continue
            x,y,_=c['origin_mm']
            row=dict(instance_id=cb['member_id'],origin_mm=(x,y,122.9),axis=(0,0,1),length_mm=4.5,diameter_mm=8)
            rows.append(dict(check='D8_recess:'+c['connection_id'],**self.bore(row)))
            head=self.shapes[c['hardware']['screw']];_,hi=self.get_bounds(head)
            rows.append(item('head_flush_below_mast:'+c['connection_id'],abs(hi[2]-125.15)<LIN_TOL,head_top_z_mm=hi[2],scope='Remaining 2.5 mm floor and actual tool fit strength remain UNKNOWN'))
        cover=self.shapes['front_service_cover']
        expected=[('X',y,z,1.7) for y in (-101.0,101.0) for z in (-101.0,101.0)]
        expected += [('X',y,z,4.0) for y in (-107.15,107.15) for z in (-107.15,107.15)]
        actual=self.cylinder_axis_inventory(cover)
        rows.append(item('front_cover_exact_4_original_holes_4_corner_reliefs',set(actual)==set(expected),actual_axes=actual,expected_axes=sorted(expected)))
        target=((183,-107,-107),(185,107,107));bounds=self.get_bounds(cover)
        rows.append(item('front_cover_original_outer_bounds',max(abs(a-b) for aa,bb in zip(bounds,target) for a,b in zip(aa,bb))<LIN_TOL,actual_bounds=bounds))
        for side in (-1,1):
            for level in (-1,1):
                screw=f'RB_end_screw_1_{side}_{level}'
                distance=float(cover.distance_to(self.shapes[screw]))
                overlap=self.overlap(cover,self.shapes[screw])
                rows.append(item('front_cover_head_relief:'+screw,distance>=.5-LIN_TOL and overlap<=VOL_TOL,minimum_distance_mm=distance,overlap_mm3=overlap,required_nominal_mm=.5))
        return rows

    def candidate5_reliefs(self):
        """Explicit fixes derived from C4 actual intersections, never a pair waiver."""
        rows=[]
        for side in (-1,1):
            for sx in (-1,1):
                key=f'wing_root_fork_{side}_{sx}';shape=self.shapes[key]
                p=(sx*164,side*107.15,0)
                channel=self.cylinder(4.499,p,(0,0,1),-125.151,-115.151)
                v=self.overlap(channel,shape)
                rows.append(item('fork_D9_below_pad:'+key,v<=VOL_TOL,channel_material_mm3=v,upper_boundary_z_mm=-115.15))
                old=f'shear_rail_screw_{side}_{sx*150}_-94'
                distance=float(shape.distance_to(self.shapes[old]))
                inventory=self.cylinder_axis_inventory(shape)
                expected_axis=('Z',float(sx*150),float(side*106.15),3.25)
                rows.append(item('fork_D6p5_legacy_head_relief:'+key,expected_axis in inventory and distance>=.5-LIN_TOL,actual_minimum_distance_mm=distance,axis_found=expected_axis in inventory,nominal_net_ligament_to_existing_x144_hole_mm=math.hypot(6,1)-3.25-1.7,structural_acceptance='NOT_EVALUATED'))
                solids=list(shape.solids())
                rows.append(item('fork_not_disconnected:'+key,len(solids)==1,solid_count=len(solids)))
            lug=f'hold_roof_lug_1_{side*94.15}';old=f'shear_rail_screw_{side}_-30_94'
            expected_axis=('Z',-30.0,float(side*106.15),3.25)
            inventory=self.cylinder_axis_inventory(self.shapes[lug]);distance=float(self.shapes[lug].distance_to(self.shapes[old]))
            rows.append(item('hold_lug_D6p5_edge_relief:'+lug,expected_axis in inventory and distance>=.5-LIN_TOL,axis_found=expected_axis in inventory,actual_minimum_distance_mm=distance))
            for z in (-94,94):
                key=f'shear_web_screw_{side}_150_{z}';lo,hi=self.bounds[key]
                inward=lo[1] if side>0 else -hi[1]
                outward=hi[1] if side>0 else -lo[1]
                pillar=f'RB_pillar_{2 if side<0 else 3}'
                dist=float(self.shapes[key].distance_to(self.shapes[pillar]))
                rows.append(item('shortened_legacy_side_screw:'+key,abs(inward-101.15)<LIN_TOL and abs(outward-110.15)<LIN_TOL,inward_abs_y_mm=inward,outward_abs_y_mm=outward,pillar_distance_mm=dist,selected_nominal_gap_mm=0,positive_assembly_clearance='NOT_ESTABLISHED',scope='Selected common-plane proxy truncation only; full static intersection remains checked. Actual screw head/thread fastening and physical tolerance unresolved'))
        return rows

    def controls(self,cs):
        c=next(c for c in cs if c['connection_id']=='R07_RAIL_-1_1_15')
        row=next(b for b in c['bore_segments'] if b['instance_id'].startswith('R07_upper_cap_'))
        orig=self.shapes[row['instance_id']];p=row['origin_mm'];a=row['axis'];h=row['length_mm']/2
        filled=orig+self.cylinder(2.25,p,a,-h,h)
        nohole=self.bore(row,filled);wrongaxis=self.bore(row,orig.moved(self.Location((1,0,0))))
        washer=self.shapes[c['hardware']['washer_head']].moved(self.Location((0,0,-.25)))
        volume=self.overlap(washer,orig)
        # Original 22 mm front axial shank crossed the new transverse bolt.
        old=self.cylinder(2,(183,-107.15,107.15),(1,0,0),-22,0)
        cross=self.overlap(old,self.shapes['R07_RAIL_-1_1_164_screw'])
        sleeve_id=c['sleeve_id'];actual_sleeve=self.shapes[sleeve_id]
        short=actual_sleeve & self.Box(20,20,7.8).moved(self.Location((15,-107.15,107.15)))
        try:
            self.shapes[sleeve_id]=short
            short_result=self.sleeves([c])[0]
        finally:self.shapes[sleeve_id]=actual_sleeve
        old_cover=self.Box(2,214,214).moved(self.Location((184,0,0)))
        old_corner=self.overlap(old_cover,self.shapes['RB_end_screw_1_-1_1'])
        rows=[dict(id='filled_actual_mating_hole',rejected=nohole['status']=='FAIL',evidence=nohole),dict(id='shift_actual_axis_1mm',rejected=wrongaxis['status']=='FAIL',evidence=wrongaxis),dict(id='washer_driven_into_member',rejected=volume>VOL_TOL,overlap_mm3=volume),dict(id='legacy_22mm_axial_screw_crossing',rejected=cross>VOL_TOL,overlap_mm3=cross),dict(id='short_sleeve_loses_two_wall_support',rejected=short_result['status']=='FAIL',evidence=short_result),dict(id='old_front_cover_corner_hits_actual_screw_head',rejected=old_corner>VOL_TOL,overlap_mm3=old_corner,scope='Independent analytic original rectangular cover corner fixture')]
        return dict(status='PASS' if all(r['rejected'] for r in rows) else 'FAIL',cases=rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--contract',type=Path,default=RUN/'candidate/results/R07_CONNECTION_CONTRACT.json')
    ap.add_argument('--receipt',type=Path,default=RUN/'candidate/results/service_structure_instances.json')
    ap.add_argument('--step',type=Path,default=RUN/'candidate/servicer_structure_service.step')
    ap.add_argument('--local-step',type=Path,default=RUN/'candidate/r07_local.step')
    ap.add_argument('--output',type=Path,default=RUN/'review/R07_REVIEW.json')
    ap.add_argument('--execute-geometry',action='store_true')
    args=ap.parse_args();started=time.monotonic()
    out=dict(schema='WP04_R07_INDEPENDENT_REVIEW_V1',status='NOT_RUN',parent_issue_closed=False,physical_assembly_completed=False,manufacturing_release=False,unknown=['Actual threads, fastener selection, preload, locking, tolerances and load ratings','Sleeve longitudinal insertion and retention','Moving arm, complete mechanism action and launch interface','Rear reinforcement rib anchorage','Future equipment/cover installation paths'])
    try:
        raw,receipt,data,checks,affected,bindings=load_inputs(args)
        out.update(contract_checks=checks,input_sha256_before=bindings,independently_affected_ids=sorted(affected),scope='Service-state affected R07 vs full registered non-arm physical/proxy context; nominal geometry only')
        if any(r['status']=='FAIL' for r in checks):out['status']='CONTRACT_FAIL_GEOMETRY_NOT_RUN'
        elif not args.execute_geometry:out['status']='CONTRACT_PASS_GEOMETRY_NOT_RUN'
        else:
            progress('runtime_bootstrap');out['runtime_bootstrap']=base.bootstrap_cad_runtime()
            review=Review(data,args.contract);out['import_metadata']=review.import_metadata
            out['validity']=review.validity()
            out['local_final_equivalence']=review.local_equivalence(args.local_step,set(raw['local_instance_ids']))
            out['holes']=[];out['bearing_faces']=[];out['paths']=[]
            for c in raw['connections']:
                progress('connection',id=c['connection_id'])
                for b in c['bore_segments']:out['holes'].append(dict(connection=c['connection_id'],**b,**review.bore(b)))
                for b in c['bearing_faces']:out['bearing_faces'].append(dict(connection=c['connection_id'],**b,**review.support(b)))
                for p in c['paths']:out['paths'].append(dict(connection=c['connection_id'],path_id=p['path_id'],**review.assembly_path(p,c)))
            out['sleeves']=review.sleeves(raw['connections'])
            out['shared_pillar_stack']=review.pillar_stack()
            out['rear_and_axial']=review.rear_and_axial()
            out['reliefs_and_counterbores']=review.reliefs_and_counterbores(raw['connections'])
            out['candidate5_explicit_reliefs']=review.candidate5_reliefs()
            out['affected_static_pairs']=review.static(affected)
            out['negative_controls']=review.controls(raw['connections'])
            # Reapply established original R01 hole inventories on actual final
            # WP04 geometry; no inherited PASS substitutes for this readback.
            out['r01_deck_inventory_regression']=review.deck_hole_axis_inventory()
            out['r01_angle_inventory_regression']=review.angle_hole_axis_inventory()
            statuses=[r['status'] for k in ('validity','local_final_equivalence','holes','bearing_faces','paths','sleeves','shared_pillar_stack','rear_and_axial','reliefs_and_counterbores','candidate5_explicit_reliefs','r01_deck_inventory_regression','r01_angle_inventory_regression') for r in out[k]]
            statuses += [out['affected_static_pairs']['status'],out['negative_controls']['status']]
            out['status']='SCOPED_GEOMETRY_FAIL' if 'FAIL' in statuses else 'SCOPED_GEOMETRY_WITH_UNKNOWN' if 'UNKNOWN' in statuses else 'SCOPED_NOMINAL_GEOMETRY_PASS_PARENT_OPEN'
        out['input_sha256_after']={p:sha256(p) for p in bindings}
        if out['input_sha256_after']!=bindings:out['status']='INPUT_DRIFT_FAIL'
    except Exception as exc:
        import traceback
        out.update(status='REVIEW_ERROR_FAIL_CLOSED',error=str(exc),traceback=traceback.format_exc())
    out['elapsed_s']=time.monotonic()-started
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(status=out['status'],output=str(args.output)),ensure_ascii=False),flush=True)
    return 1 if 'FAIL' in out['status'] or 'ERROR' in out['status'] else 0


if __name__=='__main__':sys.exit(main())
