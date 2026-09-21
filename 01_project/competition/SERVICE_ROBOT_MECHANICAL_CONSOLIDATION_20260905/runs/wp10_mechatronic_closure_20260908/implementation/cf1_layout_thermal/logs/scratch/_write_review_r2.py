"""Append the r2 review pass (fresh mechanical + claims lenses, two disposition audits) to results/REVIEW_CF1.json with the
author's r3 dispositions. The r2 refuters and synthesis failed on the session limit, so these are raw lens findings."""
import json
from collections import Counter
from pathlib import Path

JOURNAL = Path(r'C:\Users\stude\.claude\projects\F--China-Graduate-Future-Flight-Vehicle-Innovation-Competition\e07a4e94-c35c-4920-b7e9-d1a872861792\subagents\workflows\wf_6a2c1ff5-e1c\journal.jsonl')
OUT = Path(__file__).resolve().parents[2] / 'results/REVIEW_CF1.json'
rows = [json.loads(l) for l in JOURNAL.read_text(encoding='utf-8').splitlines() if l.strip()]
lenses = {}; audits = []
for r in rows:
    if r.get('type') != 'result':
        continue
    res = r.get('result')
    if isinstance(res, dict) and 'findings' in res:
        fs = res['findings']
        # the mechanical lens leads with the narrowphase/probe files; the claims lens leads with README/DELIVERY or the geometry JSON's web layering
        lens = 'claims' if 'claims' not in lenses and 'mechanical' in lenses else 'mechanical'
        if 'mechanical' in lenses and 'claims' in lenses:
            continue
        lenses[lens] = fs
    elif isinstance(res, dict) and 'verdicts' in res:
        audits.extend(res['verdicts'])
DISP = {
    'mechanical-1': ('FIXED', 'r3 models the wall as built: 2 mm inner web as its own non-radiating sheet, coupled to the 8 mm panel only at the probed gap-layer bridges (WEB_FACE_PROBE_CF1.json gap_bridges); lug patches on the web sheets; the r2 skin/stiffener/half-plate term withdrawn; acceptance re-run'),
    'mechanical-2': ('FIXED', 'narrowphase drivers use an explicit registered-envelope allow-list; every other role incl. *_PROXY rejects; file status is now the parent ruling with a separate physical_only_view; per-state field renamed parent_status'),
    'mechanical-3': ('FIXED', 'carrier node defined at the arch shelf; plus_Y books riser-A conduction to the paddle centroid (13.1 mm, 40x5), minus_Y books riser-A descent (37.1 mm) + plate spreading; Q201 case->node budget 1.5 K/W = TIM 0.54 + riser B 0.47 + shelf 0.32 recorded'),
    'mechanical-4': ('FIXED', 'probe re-written at 0.25 mm y resolution: web 2.0 / gap 2.0 / panel 8.0, outer face 113.15, zero slabs kept, layers listed'),
    'mechanical-5': ('FIXED_AS_DISCLOSED', 'shear_web_1 dual binding (V27 wall_navigation_bosses.step vs RADIATOR_OBSTACLE_BOUNDS fixed_heat_wall_pos.step) recorded in the geometry file source_discrepancies and in the probe receipt thermal_side_binding'),
    'mechanical-6': ('FIXED', 'field renamed carrier_plate_and_arch_S_mm; module_bbox_S_mm added with the exact-test note'),
    'mechanical-7': ('FIXED', 'README states the half-open grid (dy 0..-6, dz 0..+6, dx 0)'),
    'mechanical-8': ('FIXED', 'module-self check added to narrowphase_cf1.py: common volume of the five solids with the V30 module STEP (0), contact slabs 704 / 1000 / 810 mm2, TIM gap empty'),
    'mechanical-9': ('NO_CHANGE_NEEDED', 'reviewer closed the arithmetic'),
    'claims-1': ('FIXED', 'same as mechanical-1'),
    'claims-2': ('FIXED', 'with the web sheets the +Y strap heat can only reach the panel through the CHB bridge patch; the model now carries that path and the CHB case temperature includes both heats on the same seat'),
    'claims-3': ('FIXED', 'verify_thermal_cf1.py checks the web model against the probe receipt (thickness, bridges, zero gap under the lug, non-radiating webs, patch sheets) rather than against the solver copy'),
    'claims-4': ('FIXED', 'README cell reworded: 3.00 W is the 24.44 A battery-current bound; the thermal replica books copper at I_m (23.15 A)'),
    'claims-5': ('FIXED', 'spec-5 fallbacks run whenever nominal or spec-listed closure fails: full +X skin, Q201 11 mOhm, both, and the minimum skin area fraction by bisection; -Y patch z 35..75 vs spec z 40..90 recorded as a thermal spec deviation'),
    'claims-6': ('FIXED', 'file status = parent ruling (REJECTED on the battery D-max envelope); physical_only_view separate; README wording changed'),
    'claims-7': ('FIXED', 'README says 2 of 4 lenses completed and author-triaged for r1; verify checks all 84 locked sources; +5.4 / -5.2 W'),
    'claims-8': ('FIXED', 'register_cf1_navigation.py: --force removed, sentences composed from DELIVERY_STATUS fields, listed in the product map and manifest'),
    'claims-9': ('FIXED', 'DELIVERY_STATUS thermal block reports per-criterion worst values and the by-env table'),
}
AUDIT_DISP = {
    'pcb-4': 'verify_pcb_cf1.py now carries spec-conformance checks (4.2 F201 land 10 mm, 4.3 parallel copper at F201/R201/R202, 4.4 pours >= 2400 mm2) that FAIL until the owner accepts the deviations',
    'pcb-5': 'accepted as partial: control (d) remains an in-memory arithmetic control, labelled as such',
    'pcb-9': 'accepted as partial: wording only',
    'pcb-11': 'r2 and r3 sections added to this file',
    'pcb-12': 'README lists the inherited V32 negative fixtures as inherited-not-rerun',
    'thermal-4': 'superseded by the r3 web-sheet model (mechanical-1)',
    'thermal-8': 'accepted as partial: tolerance tied to the known omissions',
}
rev = json.loads(OUT.read_text(encoding='utf-8'))
rev['r2'] = dict(date='2026-09-17',
                 method='Workflow: fresh mechanical + claims lenses on the r2 files, two disposition audits over the 24 r1 findings, 2 refuters per new blocker/major, synthesis. '
                        'The four review/audit agents completed; every refuter and the synthesis failed on the session token limit, so the new findings are raw lens output triaged by the author.',
                 lenses_completed=sorted(lenses), findings=[], r1_disposition_audit=[])
for lens, fs in lenses.items():
    for i, f in enumerate(fs, 1):
        fid = '%s-%d' % (lens, i); d = DISP.get(fid, ('UNDISPOSED', ''))
        rev['r2']['findings'].append(dict(id=fid, severity=f['severity'], file=f['file'], location=f['location'], claim=f['claim'], defect=f['defect'],
                                          evidence=f['evidence'], suggested_fix=f['suggested_fix'], r3_disposition=d[0], r3_disposition_note=d[1]))
for v in audits:
    rev['r2']['r1_disposition_audit'].append(dict(id=v['id'], status=v['status'], residual_severity=v.get('residual_severity'), evidence=v['evidence'],
                                                  r3_action=AUDIT_DISP.get(v['id'], 'none needed' if v['status'] == 'RESOLVED' else 'see r3 findings')))
rev['r3'] = dict(date='2026-09-17', status='NOT_MACHINE_REVIEWED',
                 note='r3 corrections (web-sheet model, arch path terms, role allow-list, spec-conformance checks, receipts) were self-checked by the verify scripts only; no third review pass was run.')
OUT.write_text(json.dumps(rev, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('r2 written:', {k: len(v) for k, v in lenses.items()}, 'audits', len(audits), 'dispositions', dict(Counter(f['r3_disposition'] for f in rev['r2']['findings'])))
