import sys,importlib.util
sys.dont_write_bytecode=True
from pathlib import Path
spec=importlib.util.spec_from_file_location('functional_ports',Path(__file__).with_name('functional_ports.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def gen_step():return m.build()[2]
