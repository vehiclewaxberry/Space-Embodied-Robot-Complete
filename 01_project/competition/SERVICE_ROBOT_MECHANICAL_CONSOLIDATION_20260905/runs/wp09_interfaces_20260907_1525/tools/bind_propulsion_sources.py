from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text());o=c['mips_oem']
d=dict(status='REFERENCE_INPUT_PROVENANCE_BOUND',part_number=o['part_number'],revision=o['document_revision'],OEM_pdf=o['source_pdf'],OEM_sha256=o['source_sha256'],input_path=str(R/'results/PROPULSION_CAPABILITY_INPUTS.json'),input_sha256=sha(R/'results/PROPULSION_CAPABILITY_INPUTS.json'),result_path=str(R/'results/PROPULSION_CAPABILITY_BOUNDS.json'),result_sha256=sha(R/'results/PROPULSION_CAPABILITY_BOUNDS.json'),total_impulse_Ns=44,jet_count=5,nominal_single_jet_thrust_N=.01,actual_simultaneous_firing_verified=False,nozzle_vector_configuration_verified=False,ideal_time_scope='OPTIMISTIC_ALL_JETS_TANGENTIAL_SUM; NOT_ACTUAL_ATTAINABLE_TORQUE_OR_MANEUVER_DURATION')
assert sha(o['source_pdf'])==o['source_sha256']
(R/'results/PROPULSION_BOUND_SOURCE_BINDING.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
