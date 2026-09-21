"""Run the same cadgen resolver/renderer in separate guarded processes to release OCP RAM."""
from pathlib import Path
import os,sys,json,hashlib,asyncio,dataclasses
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';sys.path.insert(0,str(A/'tools/cadgen_v30'));os.environ['CADGEN_DAEMON']='0';os.environ['CADGEN_COMPONENT_WORKERS']='1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();step=C/'main_input_lugs_v30.step';before=sha(step);phase=sys.argv[1];packet_file=C/'LUG_RESOLVED_RENDER_PACKET_V30.json'
if phase=='prepare':
 from cadgen.snapshot_cli import resolve_render_job_packet
 from cadgen.snapshot_core import clear_render_output_targets
 job=json.loads((C/'LUG_SNAPSHOT_JOB_V30_snapshot.json').read_text());clear_render_output_targets([job],resolved_cwd=A)
 packet=resolve_render_job_packet(job,cwd=A,kinds=frozenset(['step']));packet_file.write_text(json.dumps(packet));result=dict(prepared=True,packet_sha256=sha(packet_file))
elif phase=='render':
 from cadgen.snapshot_core import render_snapshot
 from cadgen.assets import browser_runtime_dir
 packet=json.loads(packet_file.read_text());result=dataclasses.asdict(asyncio.run(render_snapshot(packet,runtime_dir=browser_runtime_dir(None))))
else:raise ValueError(phase)
assert sha(step)==before
result.update(STEP_before=before,STEP_after=sha(step),same_cadgen_renderer=True,split_process=True)
(C/('LUG_SPLIT_SNAPSHOT_'+phase.upper()+'_V30.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result))
