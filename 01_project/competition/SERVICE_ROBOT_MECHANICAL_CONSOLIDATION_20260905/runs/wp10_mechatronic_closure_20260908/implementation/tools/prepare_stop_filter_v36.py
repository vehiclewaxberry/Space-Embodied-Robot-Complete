"""Prepare bounded physical filter delta, preserving the240-ref checkpoint."""
from pathlib import Path
import hashlib,json,urllib.request
from erc_source_contract import parse,children,properties
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';P=A/'results/stop_v36/pcb';R=P/'thermal_filter_20260916'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    parent=json.loads((P/'native_checkpoint_20260916/CHECKPOINT_VERIFICATION.json').read_text())
    assert all(sha(Path(p))==h for p,h in parent['source_bindings'].items()),'Reconcile other writer first'
    R.mkdir(exist_ok=False)
    dump(R/'PARENT_BINDING.json',dict(source_bindings=parent['source_bindings'],checkpoint=str(P/'native_checkpoint_20260916/CHECKPOINT_VERIFICATION.json'),checkpoint_sha256=sha(P/'native_checkpoint_20260916/CHECKPOINT_VERIFICATION.json'),
        preceding_handoff_zip_sha256=sha(A/'coupled_closure/WP10_CLAUDE_HANDOFF_20260916.zip')))
    rows={};plans=[]
    for i in range(1,4):
        sheet=f'wp10_power_{i+6}.kicad_sch'
        actual={properties(s)['Reference'] for s in children(parse((D/sheet).read_text()),'symbol')}
        rr=f'R{i+349}';ca=f'C{2*i+312}';cb=f'C{2*i+313}'
        assert not actual&{rr,ca,cb}
        components=[];connections={};fields={}
        for ref,symbol,value,mpn,fp,url,pos in [
            (rr,'Device:R','1k','CRCW06031K00FKEA','Resistor_SMD:R_0603_1608Metric','https://www.vishay.com/docs/20035/dcrcwe3.pdf',(30.48,236.22)),
            (ca,'Device:C','1nF','C0603C102F5GACTU','Capacitor_SMD:C_0603_1608Metric','https://search.kemet.com/component-documentation/download/specsheet/C0603C102F5GACTU',(129.54,236.22)),
            (cb,'Device:C','1nF','C0603C102F5GACTU','Capacitor_SMD:C_0603_1608Metric','https://search.kemet.com/component-documentation/download/specsheet/C0603C102F5GACTU',(228.6,236.22))]:
            components.append(dict(symbol=symbol,reference=ref,value=value,footprint=fp,position=dict(x=pos[0],y=pos[1]),rotation=0))
            rows[ref]=dict(MPN=mpn,manufacturer='Vishay' if ref[0]=='R' else 'KEMET',footprint=fp,source_url=url,sheet=sheet,value=value,placement_owner='STOP_CONTROL_AND_THERMAL_BOARD',scope='0..50C engineering prototype filter; not qualified hardware')
            fields[ref]=dict(properties=dict(MPN=mpn,Manufacturer=rows[ref]['manufacturer'],Datasheet=url,Footprint=fp,Physical_Owner='STOP_CONTROL_AND_THERMAL_BOARD',PCB_Selection_Revision='V36_FILTER',Tolerance='1%',Temperature_Coefficient='100ppm/K' if ref[0]=='R' else '30ppm/K',**({} if ref[0]=='R' else dict(Dielectric='C0G',Voltage='50V'))))
        raw=f'WP10_BRAKE_TEMP_{i}';filtered=f'WP10_BRAKE_TEMP_IN_{i}';op=f'WP10_BRAKE_TEMP_OPEN_{i}'
        connections={rr:{'1':raw,'2':filtered},ca:{'1':filtered,'2':'WP10_ARM_RETURN'},cb:{'1':op,'2':'WP10_ARM_RETURN'},f'U{310+i}':{'3':filtered}}
        plans.append(dict(sheet=sheet,channel=i,old_label=raw,new_label=filtered,old_position=dict(x=50.8,y=38.1),components=components,connections=connections,fields=fields))
    dump(R/'DELTA_PARTS.json',rows);dump(R/'MCP_PLAN.json',plans)
    urls={'C0603C102F5GACTU.pdf':'https://search.kemet.com/component-documentation/download/specsheet/C0603C102F5GACTU','kem_c1003_c0g_smd.pdf':'https://content.kemet.com/datasheets/kem_c1003_c0g_smd.pdf'}
    archive=[]
    for name,url in urls.items():
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=20) as r:b=r.read()
            assert b.startswith(b'%PDF')
            p=P/'sources'/name;p.write_bytes(b);archive.append(dict(url=url,path=str(p),sha256=sha(p),bytes=len(b),status='ARCHIVED_PRIMARY_PDF'))
        except Exception as e:archive.append(dict(url=url,status='DOWNLOAD_FAILED',error=str(e)))
    dump(R/'SOURCE_ARCHIVE.json',archive)
    print(json.dumps(dict(new_parts=len(rows),channels=len(plans),archive=archive)))
if __name__=='__main__':main()
