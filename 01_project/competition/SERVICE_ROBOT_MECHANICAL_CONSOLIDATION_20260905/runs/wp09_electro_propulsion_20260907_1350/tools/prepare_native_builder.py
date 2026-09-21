from pathlib import Path
R=Path(__file__).resolve().parents[1]
old=R.parent/'wp08_retention_delta_20260907_1228/tools/build_rear_native.py'
text=old.read_text()
block=text[text.index('class RearBuilder'):text.index('\ndef main():')]
block=block.replace('RearBuilder','ModuleBuilder').replace('WP08','WP09')
block=block.replace("result['coordinate_frame']='S_WORLD_MM_IDENTITY'","result['coordinate_frame']=self.report['coordinate_frame']")
block=block.replace("'S_WORLD_MM_IDENTITY_ASSEMBLY'","self.report['coordinate_frame']").replace("'S_WORLD_MM'","self.report['coordinate_frame']")
head="""from pathlib import Path
import sys,json,re,traceback,importlib.util,argparse
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
FROZEN=R.parent/'wp07_system_20260907_0610/tools/build_retention_native.py'
ADAPTER=R.parent/'wp08_retention_delta_20260907_1228/tools/build_rear_native.py'
s=importlib.util.spec_from_file_location('wp09_frozen_builder',FROZEN)
frozen=importlib.util.module_from_spec(s);s.loader.exec_module(frozen)
require,sha,normalized,val=frozen.require,frozen.sha,frozen.normalized,frozen.val
TEMPLATES,IDENTITY16=frozen.TEMPLATES,frozen.IDENTITY16
bbox_max_error,job_linear_tolerance_mm=frozen.bbox_max_error,frozen.job_linear_tolerance_mm
"""
p=R/'tools/build_module_native.py';assert not p.exists()
p.write_text(head+block+'\n'+(R/'tools/native_main.fragment.txt').read_text(),encoding='utf-8')
print(p)

