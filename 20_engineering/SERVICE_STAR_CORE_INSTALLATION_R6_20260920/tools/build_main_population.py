from geometry import *
v36=read(R5/'inputs/V36_SOURCE_MAP.json');v30={r['id']:r for r in read(R5/'inputs/V30_SOURCE_MAP.json')['rows']}
pop=read(D/'inputs/MAIN_POPULATION_READBACK.json');fps={r['ref']:r for r in pop['footprints']}
actual=read(E/'results/reviewer/LOCKED_249_XML_BOARD_AUDIT.json')['boards']['MAIN']
assert len(fps)==43 and len(actual['xml_refs'])==35 and sha(pop['source'])==actual['sha256']
coverage={};shapes=[];T=np.eye(4);T[2,3]=1.595
for r in v36['rows']:
 s=source(r);shapes.append(s)
 if r['id']=='V36_025':continue
 mid=(np.array(r['expected_local_bbox_mm']['min_mm'])+r['expected_local_bbox_mm']['max_mm'])/2
 if r['id'] in ['V36_004','V36_005','V36_006']:ref='C201'
 else:
  ref=min((ref for ref in fps if fps[ref]['models']),key=lambda ref:np.linalg.norm(mid[:2]-np.array([fps[ref]['xy_mm'][0],-fps[ref]['xy_mm'][1]])))
  assert np.linalg.norm(mid[:2]-np.array([fps[ref]['xy_mm'][0],-fps[ref]['xy_mm'][1]]))<3
 coverage.setdefault(ref,{'ref':ref,'MPN':fps[ref]['value'],'geometry_class':'EXISTING_KICAD_MODEL','source_rows':[]})['source_rows'].append(r['id'])
for ref,ident in {'Q201':'V30_002','C202':'V30_006','C211':'V30_007','C212':'V30_008','C213':'V30_009','R201':'V30_014'}.items():
 shapes.append(moved(source(v30[ident]),T));coverage[ref]={'ref':ref,'MPN':fps[ref]['value'],'geometry_class':'PREVIOUS_CATALOGUE_OR_OEM_BODY_REFERENCE','source_row':ident,'source_sha256':v30[ident]['source_sha256'],'Z_translation_mm':1.595,'mounting_pose_qualified':False}
shapes.append(box(41.55,-18.3,1.795,48.45,-11.7,4.945));coverage['R202']={'ref':'R202','MPN':fps['R202']['value'],'geometry_class':'CURRENT_MPN_DIMENSION_ENVELOPE','height_mm_max':3.15,'solder_offset_mm':.2,'source':'https://www.vishay.com/docs/30179/wslp2726.pdf','old_V30_R202_reused':False}
shapes.append(box(14.75,-15.925,1.595,25.25,-14.075,4.895));coverage['F201']={'ref':'F201','MPN':fps['F201']['value'],'geometry_class':'MANUFACTURER_DIMENSION_ENVELOPE','dimensions_max_mm':[10.5,1.85,3.3],'source':'https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/product-aid/eaton-1025hc-fuse-product-aid.pdf'}
for ref in ['D201','D202','U201','U205']:
 f=fps[ref];x0,y0,x1,y1=f['bbox_mm'];shapes.append(box(x0,-y1,1.595,x1,-y0,7.595))
 coverage[ref]={'ref':ref,'MPN':f['value'],'geometry_class':'FOOTPRINT_XY_PLUS_ASSUMED_HEIGHT_RESERVATION','reserved_height_mm':6,'manufacturer_max_height_mm':None,'assumption':'Space reservation only; OEM 3D and real installed height must replace before clearance qualification'}
assert set(coverage)==set(actual['xml_refs']),set(coverage)^set(actual['xml_refs'])
s=compound(shapes);row=emit('R6_MAIN_PCBA_LOCAL',s,'SOURCE_BOUND_MIXED_PCBA_GEOMETRY_NOT_RELEASED',electrical_source_sha256=actual['sha256'],real_component_refs=35,footprints_total=43,all_geometry_OEM=False)
write(D/'inputs/MAIN_GEOMETRY_COVERAGE.json',{'board':row,'local_frame':'KiCad XY mirrored in Y; board base z=0; nominal top component datum z=1.595mm','coverage':list(coverage.values()),'footprints_total':43,'real_parts':35,'covered_refs':len(coverage),'height_assumption_refs':['D201','D202','U201','U205'],'mounting_holes':[f for f in pop['footprints'] if f['ref'].startswith('MH')],'wire_landing_ports':[f for f in pop['footprints'] if f['ref'].startswith('PORT_')],'solder_and_termination_installation_qualified':False,'whole_PCBA_clearance_qualified':False})
print('POPULATION',len(coverage),'refs',row['expected_solids'],'solids')
