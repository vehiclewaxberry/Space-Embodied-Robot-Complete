"""Parametric WP09 bay candidate; full parent remains linked by integration manifest."""
import importlib.util,sys
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('wp09_bay_detail',r'F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/candidate/integration_detail.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def gen_step():return m.build()[2]
