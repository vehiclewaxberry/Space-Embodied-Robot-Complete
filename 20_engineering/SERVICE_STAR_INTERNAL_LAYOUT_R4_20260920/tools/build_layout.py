"""Parametric R4 installation candidates; preserve old models and negative trials."""
from geometry import *
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge,BRepBuilderAPI_MakeWire,BRepBuilderAPI_MakeFace
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
from OCP.GC import GC_MakeArcOfCircle
from OCP.gp import gp_Circ,gp_Ax2,gp_Dir
import math

def validate_contract(contract):
    # This revision is a frozen geometric contract, not a JSON-driven CAD generator.
    # Change the geometry equations AND the contract in a new reviewed revision.
    expected={'hole_diameter_mm':3.4,'spacer_height_mm':5.,'spacer_OD_mm':6.,'spacer_bore_mm':3.4,
        'bolt_nominal':'M3x16','bolt_shank_diameter_mm':3.,'bolt_head_diameter_mm':5.5,'bolt_head_height_mm':3.,
        'washer_OD_mm':7.,'washer_thickness_mm':.5,'nut_AF_mm':5.5,'nut_height_mm':2.4}
    for k,v in expected.items():
        if contract.get('PCB_mount',{}).get(k)!=v:raise ValueError(f'FROZEN_DIMENSION_CONTRACT_MISMATCH: PCB_mount.{k}')
    for k,v in {'local_nominal_clearance_target_mm':2.,'R3_port_shift_Y_mm':-4.,'R3_module_shift_Z_mm':.1}.items():
        if contract.get(k)!=v:raise ValueError(f'FROZEN_DIMENSION_CONTRACT_MISMATCH: {k}')
    return True

def local_route(x0,x1,y0=-24,z=5.1):
    r=2.;sgn=1 if x1>x0 else -1;ym=y0+3;yturn=ym+2
    pts=[(x0,y0,z),(x0,y0+1,z),(x0+sgn*r,ym,z),(x1-sgn*r,ym,z),(x1,yturn,z),(x1,-13,z)]
    w=BRepBuilderAPI_MakeWire()
    def line(a,b):w.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*a),gp_Pnt(*b)).Edge())
    def arc(a,m,b):w.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(gp_Pnt(*a),gp_Pnt(*m),gp_Pnt(*b)).Value()).Edge())
    line(pts[0],pts[1]);arc(pts[1],(x0+sgn*(r-r/math.sqrt(2)),y0+1+r/math.sqrt(2),z),pts[2]);line(pts[2],pts[3])
    arc(pts[3],(x1-sgn*(r-r/math.sqrt(2)),yturn-r/math.sqrt(2),z),pts[4]);line(pts[4],pts[5])
    c=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(*pts[0]),gp_Dir(0,1,0)),1.5)).Edge()).Wire()
    p=BRepOffsetAPI_MakePipe(w.Wire(),BRepBuilderAPI_MakeFace(c).Face());p.Build();assert p.IsDone();return p.Shape()

def build_mount():
    contract=read(D/'inputs/DESIGN_CONSTRAINTS.json');validate_contract(contract)
    rows=state_rows();rr={r['id']:r for r in rows['service']};old=read(R3/'inputs/BOARD_RESERVATION.json')
    pcb=box(-130,-68,-1.5,-70,-28,.1);height=box(-130,-68,.1,-70,-28,18.1)
    adapter=source(rr['adapter_arm_drive']);deck=source(rr['upper_equipment_deck_B']);tim=source(rr['thermal_interface_arm_drive'])
    additions=[];interfaces=[]
    for n,(x,y,_) in enumerate(old['PCB_hole_centers_S_mm'],1):
        hole=cyl(1.7,-20,22,x,y);pcb=cut(pcb,hole);adapter=cut(adapter,hole);deck=cut(deck,hole)
        tim=cut(tim,cyl(3.2,-7,-5,x,y));height=cut(height,cyl(4.0,0,19,x,y))
        spacer=cut(cyl(3,-6.5,-1.5,x,y),hole)
        bolt=union(cyl(1.5,-15.4,.6,x,y),cyl(2.75,.6,3.6,x,y))
        wt=cut(cyl(3.5,.1,.6,x,y),hole);wb=cut(cyl(3.5,-12,-11.5,x,y),hole);nut=hex_nut(x,y,-14.4,2.4,5.5)
        for kind,s in [('SPACER',spacer),('BOLT',bolt),('TOP_WASHER',wt),('BOTTOM_WASHER',wb),('NUT',nut)]:
            ident=f'R4_IF_{kind}_{n}';additions.append(emit(ident,s,'INSTALLATION_CANDIDATE',installation_group='ARM_INTERFACE_MOUNT',material_candidate='Al6061' if kind=='SPACER' else 'stainless_steel_unspecified_strength',material_qualified=False))
        interfaces.append({'point_S_mm':[x,y],'PCB_through_hole_mm':3.4,'spacer_z_mm':[-6.5,-1.5],
            'adapter_z_mm':[-8.5,-6.5],'deck_z_mm':[-11.5,-8.5],'top_washer_z_mm':[.1,.6],
            'bottom_washer_z_mm':[-12,-11.5],'nut_z_mm':[-14.4,-12],'bolt_end_z_mm':-15.4,
            'nut_protrusion_mm':1.0,'thread_mode':'unthreaded geometric cylinders; engagement and preload not qualified'})
    pieces=[pcb,height]
    for port in old['reserved_ports']:
        c=np.array(port['center'],dtype=float);c[2]+=.1
        if port['name'] in ('JHOST','JARM'):
            c[1]-=4;c[0]={'JHOST':-86.,'JARM':-114.}[port['name']]
        half=np.array(port['size'])/2;pieces.append(box(*(c-half),*(c+half)))
    pieces += [local_route(-114,-108.5),local_route(-86,-104.5)]
    replacements=[emit('equipment_arm_drive',compound(pieces),'FUNCTIONAL_ENVELOPE',PCB_MPN=None),
        emit('adapter_arm_drive',adapter,'PHYSICAL_GEOMETRY_DESIGN_MODIFIED'),
        emit('upper_equipment_deck_B',deck,'PHYSICAL_GEOMETRY_DESIGN_MODIFIED'),
        emit('thermal_interface_arm_drive',tim,'THERMAL_INTERFACE_CANDIDATE')]
    write(D/'inputs/MOUNT_LAYOUT.json',{'schema':'R4_MOUNT_LAYOUT_V1','replacements':replacements,'additions':additions,'interfaces':interfaces,
        'source_board_reservation_sha256':sha(R3/'inputs/BOARD_RESERVATION.json'),
        'PCB_Z_shift_mm':.1,'JHOST_JARM_Y_shift_mm':-4,'JHOST_JARM_X_mm':[-86,-114],
        'route_terminal_X_mm':[-104.5,-108.5],'nominal_fastener_quantity':20,'installed_preload_qualified':False,
        'tool_keepouts':'Four radius4mm vertical keepouts removed from component-height reservation; full insertion path still to check'})
    print('MOUNT',len(replacements),'replacements',len(additions),'additions',flush=True)

if __name__=='__main__':build_mount()
