from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=R/'docs/ELECTRO_PROPULSION_MECHANICAL_WORK_PACKAGE_ZH.md';s=p.read_text()
s=s.replace('BATTERY_MOUNT_CONTRACT.json','BATTERY_MOUNT_CONTRACT_V2.json').replace('results/battery_mount/EMISSION.json','results/battery_mount_v2/EMISSION.json')
s=s.replace('电池沉头几何按实际目录件形成虚拟口径6.4 mm、90°锥、深1.5 mm，2 mm载板剩余直孔壁厚0.5 mm。','电池沉头名义标注为虚拟口径6.4 mm、90°锥、深1.5 mm，2 mm载板剩余直孔壁厚约0.5 mm；V2数字座面匹配目录实际半角0.785398 rad、顶半径3.199999444449 mm、深1.4999999346412434 mm，修正原候选的零接触，名义加工尺寸不变。')
p.write_text(s,encoding='utf-8')
p=R/'docs/DIMENSIONS_AND_ASSEMBLY_SEQUENCE_ZH.md';s=p.read_text();s=s.replace('后三处位置由图示对称性推导','其中(62,3)为图中明确标注角孔，其余三处由图示对称性推导')
p.write_text(s,encoding='utf-8')
print('Updated V2 work-package references and identified OEM explicit corner.')

