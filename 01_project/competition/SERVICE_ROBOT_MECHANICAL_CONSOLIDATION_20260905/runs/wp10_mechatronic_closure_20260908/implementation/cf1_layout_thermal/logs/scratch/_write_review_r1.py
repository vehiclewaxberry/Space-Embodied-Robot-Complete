"""Collect the r1 adversarial-review findings from the workflow journal and record each disposition."""
import json
from collections import Counter
from pathlib import Path

JOURNAL = Path(r'C:\Users\stude\.claude\projects\F--China-Graduate-Future-Flight-Vehicle-Innovation-Competition\e07a4e94-c35c-4920-b7e9-d1a872861792\subagents\workflows\wf_9f31674e-948\journal.jsonl')
OUT = Path(__file__).resolve().parents[2] / 'results/REVIEW_CF1.json'

rows = [json.loads(l) for l in JOURNAL.read_text(encoding='utf-8').splitlines() if l.strip()]
lenses = {}
for r in rows:
    if r.get('type') != 'result':
        continue
    res = r.get('result')
    if isinstance(res, dict) and 'findings' in res:
        first = res['findings'][:3]
        lens = 'pcb' if any('pcb' in (f.get('file', '') + f.get('location', '')).lower() or 'CURRENT_DENSITY' in f.get('file', '') for f in first) else 'thermal'
        lenses[lens] = res['findings']

DISP = {
    'thermal-1': ('FIXED', '+Y lug moved to the probed web skin at S y 101.15 (WEB_FACE_PROBE_CF1.json: contact 1080 mm2, distance 0); strap lengthened to 57.15 mm; verify check lug_outer_faces_on_probed_web_skin added'),
    'thermal-2': ('FIXED', '-Y lug moved to S y -101.15 and shifted +2 mm in x, clear of the 1 mm rib; contact 1000 mm2 (100 %); web-through term booked'),
    'thermal-3': ('FIXED_AS_DISCLOSED_GAP', 'unassigned_heat_sensitivity block (0/5/10/22/33.3 W, all four environments) added; continuous_thermal_closure=false; +X skin fallback at 22 W reported (passes); README section 1 states the gap'),
    'thermal-4': ('FIXED', 'lug-through, web-through (skin / stiffener gap / half plate from the probe) and a 1-D carrier-spreading term added; terms itemised in strap_R_terms_K_W; verify recomputes from the geometry file with its own arithmetic (term list shared, disclosed)'),
    'thermal-5': ('FIXED', 'all four environments run at 5 mm; worst_env_by_criterion and min_margins_C reported; passes requires every environment; verify checks per criterion'),
    'thermal-6': ('FIXED', 'ACCEPTANCE_FIELD_CF1.json stores T/area/incoming/heat; verify recomputes radiated-vs-input from the field (independent of solver totals) and shows a +1 K perturbation is detected; node link heats recomputed from the field vectors'),
    'thermal-7': ('FIXED', 'the two built-in behaviours relabelled sanity_checks; three real negative controls added (wrong patch face moves 5.4 W between the Y faces; off-face patch refused; zero strap R refused)'),
    'thermal-8': ('FIXED', 'replay at both the 25.2 V and 20 V points; input, Q201 and CHB each asserted; known omissions (startup 0.25 W, cap leakage 0.07 W) recorded and the tolerance tied to them'),
    'thermal-9': ('FIXED', 'Q201 x1 axis added (128 cases); the 22/29.4 V omission recorded in axes_note with its rationale'),
    'thermal-10': ('FIXED', 'heater 20 W x 0.8 = 16 W; standby 60 W tier per plan; cold passes=null with criterion NONE_DECLARED'),
    'thermal-11': ('FIXED', 'conditional_on list in THERMAL_ACCEPTANCE_CF1.json; R_TIM_per_interface_K_W (four values) in the matrix header'),
    'thermal-12': ('FIXED', 'block_diag rebuilt via COO row/col; finite-positive R asserted for links and node links'),
    'pcb-1': ('FIXED_AS_OPEN_ITEM', 'necks modelled as MAIN_FORWARD_NECK; worst neck 62.9 A/mm2 reported; VALIDATION check forward_current_density_le_35_including_Q201_pad_entry_necks now FAILS by design; band-only 29.1 A/mm2 reported separately; open item in DELIVERY_STATUS'),
    'pcb-2': ('FIXED', 'necks booked to the pad centre (V29 convention): R20 3.818 mOhm, reduction 55.5 % (bands-only 57.4 % also shown); thermal_cf1.py consumes the corrected R20'),
    'pcb-3': ('FIXED', 'parity re-run on the delivered board (2026-09-17 06:25:32), refusal text captured in MAIN_INPUT_DRC_PARITY.log; verify asserts source, freshness and refusal text; schematic_parity field in DELIVERY_STATUS'),
    'pcb-4': ('FIXED_AS_DISCLOSED', 'four spec deviations listed in DELIVERY_STATUS_CF1.json pcb.spec_deviations and README section 3 with rationale, accepted_by_owner=false'),
    'pcb-5': ('PARTIALLY_FIXED', 'via threshold unified to >=12 (spec) in falsify and verify; control (d) relabelled arithmetic and a segment-selection control (e) added; the substituted negative case is stated in README and the verify note; control (d) still operates in memory'),
    'pcb-6': ('FIXED', 'check renamed pad_geometry_and_net_fingerprint_identical_to_parent with the attribute/courtyard/library deltas listed; README says 43 footprints'),
    'pcb-7': ('FIXED_AS_DISCLOSED', 'README and verify notes: footprint_filters_mismatch not evaluated without parity; ERC ran with 4 default-ignored checks (empty wp10_system.kicad_pro)'),
    'pcb-8': ('FIXED', 'current_density_cf1.py reads the stackup block and asserts F.Cu == B.Cu thickness; verify checks the value used'),
    'pcb-9': ('FIXED', 'wording corrected (vias omitted: slightly optimistic; RHO20 matches V29 to 6e-5)'),
    'pcb-10': ('NO_CHANGE_NEEDED', 'reviewer confirmed consistency; the JSON note now says outline 704 / fill 703.98'),
    'pcb-11': ('FIXED', 'results/REVIEW_CF1.json written; DELIVERY_STATUS regenerated after review'),
    'pcb-12': ('FIXED', 'dead branch removed; _patch/_probe files moved to logs/scratch; orphan .kicad_prl deleted; inherited V32 negative fixtures remain in ecad/ and are named as inherited-not-rerun'),
}
out = dict(schema='CF1_ADVERSARIAL_REVIEW',
           r1=dict(date='2026-09-17',
                   method='Workflow: four read-only lenses (pcb, thermal, mechanical, claims) -> 3 refuters per finding -> synthesis. '
                          'The mechanical and claims lenses, every refuter and the synthesis failed on the session token limit, '
                          'so the r1 findings below are raw reviewer output that was triaged by the author, not machine-verified.',
                   lenses_completed=sorted(lenses), findings=[]))
for lens, fs in lenses.items():
    for i, f in enumerate(fs, 1):
        fid = '%s-%d' % (lens, i); d = DISP.get(fid, ('UNDISPOSED', ''))
        out['r1']['findings'].append(dict(id=fid, severity=f['severity'], file=f['file'], location=f['location'], claim=f['claim'], defect=f['defect'],
                                          evidence=f['evidence'], suggested_fix=f['suggested_fix'], disposition=d[0], disposition_note=d[1]))
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('written', len(out['r1']['findings']), 'findings; dispositions', dict(Counter(f['disposition'] for f in out['r1']['findings'])))
