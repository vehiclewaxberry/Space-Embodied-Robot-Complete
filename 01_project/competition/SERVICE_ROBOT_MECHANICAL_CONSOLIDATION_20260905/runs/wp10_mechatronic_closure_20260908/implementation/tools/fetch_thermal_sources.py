"""Archive read-only public thermal sources; rejected fetches remain explicit."""
from pathlib import Path
import datetime, hashlib, json, urllib.request
A=Path(__file__).resolve().parents[1]
manifest=A/'sources/FIXED_HEAT_PATH_SOURCE_MANIFEST.json'
old={r['file']:r for r in json.loads(manifest.read_text())} if manifest.exists() else {}
rows=[]
for name,url in [
 ('az93_oem.html','https://www.aztechnology.com/product/1/az-93'),
 ('nasa_thermal_soa_2026.html','https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/'),
 ('hydro_6061_2019.pdf','https://www.hydro.com/globalassets/01-products--services/extruded-profiles/americas/ena-resources/alloy-data-sheets/hydro_2019_data_sheet_6061.pdf'),
 ('ats_d10l300s66w_170.pdf','https://www.qats.com/DataSheet/ATS-HP-D10L300S66W-170'),
 ('ats_heat_pipe_bender.pdf','https://www.qats.com/DataSheet/Bender-Heat-Pipes'),
 ('boyd_copper_water_heatpipes.pdf','https://info.boydcorp.com/hubfs/Thermal/Two-Phase-Cooling/Boyd-Copper-Water-Heat-Pipes.pdf')]:
    if name in old and (A/'sources'/name).exists():
        assert hashlib.sha256((A/'sources'/name).read_bytes()).hexdigest()==old[name]['sha256']
        rows.append(old[name]);continue
    row=dict(file=name,url=url,accessed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'WP10 engineering source archive'})
        with urllib.request.urlopen(req,timeout=25) as response: data=response.read(2_000_001)
        assert len(data)<=2_000_000,'Response exceeded bounded archive size'
        (A/'sources'/name).write_bytes(data)
        row.update(status='ACQUIRED_CONTENT_REVIEW_REQUIRED',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    except Exception as e: row.update(status='NOT_ARCHIVED',error=str(e))
    rows.append(row)
manifest.write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps(rows))
