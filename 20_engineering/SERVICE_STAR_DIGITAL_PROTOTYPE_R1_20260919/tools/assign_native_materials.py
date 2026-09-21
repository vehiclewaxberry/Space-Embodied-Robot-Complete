"""Assign source-bound physical materials to owned copies and cold-read them."""
from native_integrate import *
import xml.etree.ElementTree as ET

def make_database(plan):
    root=ET.Element('mstns:materials',{'xmlns:mstns':'http://www.solidworks.com/sldmaterials',
        'xmlns:msdata':'urn:schemas-microsoft-com:xml-msdata','xmlns:xsi':'http://www.w3.org/2001/XMLSchema-instance',
        'xmlns:sldcolorswatch':'http://www.solidworks.com/sldcolorswatch','version':'2008.03'})
    curve=ET.SubElement(root,'curves',{'id':'curve0'})
    for x in ['1.0','2.0','3.0']:ET.SubElement(curve,'point',{'x':x,'y':'1.0'})
    cls=ET.SubElement(root,'classification',{'name':'Ground prototype candidates - not as-built'})
    for row in plan['materials']:
        mat=ET.SubElement(cls,'material',{'name':row['sw_material_name'],
            'description':row['material_id']+'; ground design candidate. See NATIVE_MATERIAL_PLAN.json; strength and flight qualification not implied.'})
        props=ET.SubElement(mat,'physicalproperties')
        ET.SubElement(props,'DENS',{'displayname':'Density','value':str(row['density_kg_m3'])})
    target=OUT/'native/GROUND_CANDIDATE_MATERIALS.sldmat'
    ET.indent(root)
    ET.ElementTree(root).write(target,encoding='utf-16',xml_declaration=True)
    return target

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start',type=int,default=0);ap.add_argument('--end',type=int,default=None);ap.add_argument('--tag',default='r2');ap.add_argument('--plan',default='NATIVE_MATERIAL_PLAN.json');args=ap.parse_args()
    planpath=OUT/'inputs'/args.plan;plan=read(planpath); db=make_database(plan)
    import_sources={str(Path(q['native_path']).resolve()).casefold():q for q in read(OUT/'inputs/ALL_IMPORT_PLAN.json')['parts']}
    rp=OUT/'results'/f'MATERIAL_NATIVE_{args.start}_{args.end}_{args.tag}.json'
    assert not rp.exists(),'Receipt already exists'
    report={'status':'RUNNING','progress':[],'parts':[], 'plan_path':str(planpath),'plan_sha256':m.sha(planpath),
            'database_path':str(db),'database_sha256':m.sha(db),'whole_spacecraft_mass_kg':None,
            'whole_design_complete':False,'as_built_materials_verified':False}
    configure_com(); b=PrototypeBuilder(rp,report); sw=b.sw
    # swFileLocationsMaterialDatabases=28, read from installed swconst.tlb.
    old_material_locations=sw.GetUserPreferenceStringValue(28)
    try:
        assert sw.SetUserPreferenceStringValue(28,old_material_locations+';'+str(db.parent))
        sw.DocumentVisible(False,1)
        rows=plan['parts'][args.start:args.end]
        for i,row in enumerate(rows,args.start):
            p=Path(row['native_path']);assert p.resolve().is_relative_to(OUT/'native') and p.suffix.lower()=='.sldprt'
            before_native_sha256=m.sha(p)
            source=import_sources.get(str(p.resolve()).casefold())
            if source: assert m.sha(source['step_path'])==source['source_sha256']
            opened=sw.OpenDoc6(str(p),1,1,'',0,0);assert opened[0] is not None and opened[1]==0,(str(p),opened[1:])
            doc=b.wrap(opened[0],'IModelDoc2');part=b.wrap(doc,'IPartDoc');ext=b.wrap(doc.Extension,'IModelDocExtension')
            props=b.wrap(ext.CustomPropertyManager(''),'ICustomPropertyManager')
            assigned=row['assignment_action']=='ASSIGN_NATIVE_BULK_MATERIAL'
            before=part.GetMaterialPropertyName2('')
            if assigned:
                part.SetMaterialPropertyName2('',str(db),row['sw_material_name'])
                after=part.GetMaterialPropertyName2('')
                assert after[0]==row['sw_material_name'],(row,after)
            else:
                # No artificial material or zero-density marker is written to
                # composite envelopes. An existing name is explicitly recorded.
                after=before
            for name,value in {'DP_MATERIAL_STATUS':row['status'],'DP_MATERIAL_ID':row['material_id'] or 'UNKNOWN_COMPOSITE',
                 'DP_DENSITY_KG_M3':str(row['density_kg_m3']) if assigned else 'UNKNOWN',
                 'DP_MATERIAL_EVIDENCE':'../inputs/'+args.plan,
                 'DP_AS_BUILT':'NOT_VERIFIED','DP_PHYSICAL_MASS_AUTHORITY':'PARTIAL_CANDIDATE_ONLY',
                 'DP_PROCUREMENT_NOTE':row['procurement_material_note']}.items(): props.Add3(name,30,str(value),2)
            saved=doc.Save3(1,0,0);assert saved[0] and saved[1]==0,(p,saved)
            title=m.val(doc,'GetTitle');sw.CloseDoc(title)
            opened=sw.OpenDoc6(str(p),1,3,'',0,0);assert opened[0] is not None and opened[1]==0
            cold=b.wrap(opened[0],'IModelDoc2');coldpart=b.wrap(cold,'IPartDoc')
            actual=coldpart.GetMaterialPropertyName2('')
            rho=None;mass=None;volume=None
            if assigned:
                assert actual[0]==row['sw_material_name'],actual
                e=b.wrap(cold.Extension,'IModelDocExtension');v=e.GetMassProperties2(1,0,False)
                # Generated wrapper returns (properties, status); source API
                # properties index 3 volume[m^3], index 5 mass[kg].
                a=v[0];volume=float(a[3]);mass=float(a[5]);assert volume>0
                rho=mass/volume
                assert abs(rho-row['density_kg_m3'])<=max(1e-5,abs(row['density_kg_m3'])*1e-6),(p,rho,row['density_kg_m3'])
            sw.CloseDoc(m.val(cold,'GetTitle'))
            report['parts'].append({'path':str(p),'instance_ids':row['instance_ids'],'assigned':assigned,'before':before,
                'before_native_sha256':before_native_sha256,'source_STEP_sha256':source['source_sha256'] if source else None,
                'cold_material':actual,'density_kg_m3':rho,'candidate_geometry_mass_kg':mass,'volume_m3':volume,
                'status':row['status'],'sha256':m.sha(p),'open_errors':opened[1],'open_warnings':opened[2]})
            if (i+1)%10==0 or i==args.start:b.checkpoint('native_material_saved_and_cold_read',completed=len(report['parts']),index=i)
        report['status']='PASS_NATIVE_MATERIAL_WRITE_AND_COLD_READ_FOR_DECLARED_SUBSET'
        b.checkpoint('complete',count=len(report['parts']),assigned=sum(x['assigned'] for x in report['parts']))
    except Exception as e:
        report.update(status='FAILED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
    finally:
        assert sw.SetUserPreferenceStringValue(28,old_material_locations)
        sw.DocumentVisible(True,1);b.pythoncom.CoUninitialize()

if __name__=='__main__': main()
