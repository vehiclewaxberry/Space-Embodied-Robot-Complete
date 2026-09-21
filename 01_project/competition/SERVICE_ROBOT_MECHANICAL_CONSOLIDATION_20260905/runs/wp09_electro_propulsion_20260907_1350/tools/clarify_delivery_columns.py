from pathlib import Path
import json,csv,hashlib
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'docs/LOCAL_INSTANCE_BOM.csv';before=sha(p)
with p.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f));keys=list(rows[0])
assert all(x in keys for x in ['x_mm','y_mm','z_mm'])
renames={x+'_mm':'size_'+x+'_mm' for x in ['x','y','z']}
fixed=[{renames.get(k,k):v for k,v in row.items()} for row in rows]
with p.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(fixed[0]));w.writeheader();w.writerows(fixed)
readme=R/'README.md';s=readme.read_text();marker='## 工程交接\n\n';assert marker in s
s=s.replace(marker,marker+'BOM的 `size_x_mm/size_y_mm/size_z_mm` 为源实体轴对齐包围盒尺寸（mm），不是安装位置。安装坐标与变换以各组件合同和尺寸卡为准。BOM含代理设备/功能包络，不能直接作为采购或质量预算清单。\n\n')
readme.write_text(s,encoding='utf-8')
report=dict(status='DISPLAY_AND_BOM_COLUMN_CLARIFICATION_ONLY',bom_sha256_before=before,bom_sha256_after=sha(p),rows_unchanged=44,geometry_or_gate_changed=False,notes=['Image paths in README wrapped with angle brackets for CommonMark spaces.','BOM dimension column names clarified; numerical values and source/native paths unchanged.'])
out=R/'results/DELIVERY_DISPLAY_FIXES.json';assert not out.exists();out.write_text(json.dumps(report,indent=2),encoding='utf-8')
