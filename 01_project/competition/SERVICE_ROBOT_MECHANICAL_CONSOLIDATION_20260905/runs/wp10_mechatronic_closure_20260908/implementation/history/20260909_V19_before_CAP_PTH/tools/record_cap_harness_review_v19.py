"""Record the completed read-only agent's stated scope and exact reviewed bytes."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1]
reviewed={
 'power/CAP_HARNESS_DEFINITION_V19.json':'c8403a5722a17fd018e13fc3767389d33f25ce1a16d3a04064da9af7395964f8',
 'mechanical/cap_harness_path.py':'ba3352b3fe336de85c27081f9e8a0921dfb88197bbf8af42d858170a61be3405',
 'mechanical/cap_harness_common.py':'60f428ca21911d5af319024d47f623ead207e6e39083b24b0cd91db3b60ada1b',
 'mechanical/cap_harness_plus.step.py':'b1cd427e787a6e98c4b4276bb00dff10e3f579376a8111c1cc871e427064e5bb',
 'mechanical/cap_harness_minus.step.py':'2585b2c75e14bf619b9a258581836f2f5b014a2b81af89994a2c64ab0f83fe74',
 'tools/check_cap_harness_path_v19.py':'cc50e13ac3475fc86bc149a8bb9b803c576d29506ce24168a198e34e714fe99b',
 'results/CAP_HARNESS_PATH_V19.json':'846aad4f3ff5c6657e4b339172625c65a5fcbd17b0c1457b49027e0093f75d67',
 'mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json':'223573605b907ef2cad95890c1902083f199af422770406e4faa91baf07e7632'}
assert all(hashlib.sha256((A/f).read_bytes()).hexdigest()==h for f,h in reviewed.items())
out=dict(status='PASS_SCOPED_ANALYTIC_SOURCE_REPAIR',reviewer='/root/cap_terminal_review',method='Read-only source and JSON review; independent polyline-minus-circular-corner length arithmetic; lightweight in-memory counterexamples. No CAD/OCP/KiCad or images loaded.',
 independent_cut_length_mm=52.76307712195816,checks=22,faults_rejected=10,rebind_review='After actual WIRE PTH edit, independent reviewer confirmed only source hashes changed in route definition/result; all route values and scope unchanged.',
 prior_concerns=['Conductor may terminate inside PCB if negative projection metadata is changed consistently','Wire R20 may be changed to zero without checking OEM parameter values','Redundant tip metadata may differ from real path'],
 repairs_verified=['Both board-interior termination cases rejected by positive projection and through-board-span predicates','Manufacturer wire definition equality required','Tip metadata tied to analytic endpoints','Board faces derived from current definitions'],
 not_reviewed=['Exact interference','Strain relief','Solder process','CAD visual inspection','V19 publisher and source-metadata repair'],reviewed_files=reviewed,whole_design_complete=False)
(A/'results/CAP_HARNESS_READONLY_REVIEW_V19.json').write_text(json.dumps(out,indent=2));print('Recorded scoped independent analytic review,8 file hashes verified')
