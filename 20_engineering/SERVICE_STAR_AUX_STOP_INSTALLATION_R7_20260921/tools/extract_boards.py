"""Decompose the AUX and STOP KiCad STEP exports into per-component solids.

Same XDE walk R5 used for the MAIN board, so the two new boards enter the
mechanical model through one audited path. Board bodies export at the KiCad
dielectric thickness; the nominal total stack is applied later, exactly as R6H
did for MAIN, and is recorded rather than silently absorbed.
"""
from geometry import *
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDataStd import TDataStd_Name
from OCP.XCAFDoc import XCAFDoc_DocumentTool

BOARDS = [
    ('AUX', 'wp10_aux_protection', ['J208', 'J209', 'J211']),
    ('STOP', 'wp10_stop_control', ['J101', 'J102', 'J103', 'J104', 'J105']),
]


def label_name(label):
    a = TDataStd_Name()
    return a.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), a) else ''


def extract(step_path, tag):
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    assert reader.ReadFile(str(step_path)) == 1
    doc = TDocStd_Document(TCollection_ExtendedString('XmlXCAF'))
    assert reader.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    out = []

    def visit(label, T=np.eye(4), instance=''):
        if st.IsReference_s(label):
            ref = TDF_Label()
            assert st.GetReferredShape_s(label, ref)
            tr = st.GetLocation_s(label).Transformation()
            m = np.eye(4)
            for i in range(3):
                for j in range(4):
                    m[i, j] = tr.Value(i + 1, j + 1)
            return visit(ref, T @ m, label_name(label))
        seq = TDF_LabelSequence()
        if st.GetComponents_s(label, seq, False) and seq.Length():
            for i in range(1, seq.Length() + 1):
                visit(seq.Value(i), T)
        else:
            s = moved(st.GetShape_s(label), T)
            ident = '%s_%03d' % (tag, len(out))
            nm = label_name(label) or instance
            r = emit(ident, s, 'SOURCE_GEOMETRY', sub='source/' + tag, source_label=nm,
                     instance_label=instance, source_assembly_sha256=sha(step_path))
            out.append(r)
            print(ident, nm, 'solids', r['expected_solids'],
                  'bbox', r['expected_local_bbox_mm'], flush=True)

    for i in range(1, roots.Length() + 1):
        visit(roots.Value(i))

    full = load(step_path)
    vol = sum(r['expected_volume_mm3'] for r in out)
    # OCP integrates a whole compound differently from summing per-leaf adaptive
    # integrals; compare the reassembled compound against the source compound.
    recombined = g.volume(compound([source(r) for r in out]))
    assert abs(recombined - g.volume(full)) < max(1e-4, recombined * 1e-9)
    return out, vol, recombined, g.volume(full)


if __name__ == '__main__':
    summary = {}
    for tag, stem, missing in BOARDS:
        step_path = D / 'cad' / ('%s_NATIVE_EXPORT.step' % stem)
        rows, vol, recombined, full = extract(step_path, tag)
        summary[tag] = dict(
            source_path=str(step_path), source_sha256=sha(step_path),
            kicad_pcb=str(D / 'sources' / (stem + '.kicad_pcb')),
            kicad_pcb_sha256=sha(D / 'sources' / (stem + '.kicad_pcb')),
            v36_pcb_sha256=sha(V36 / (stem + '.kicad_pcb')),
            rows=rows, component_instances=len(rows),
            solid_occurrences=sum(r['expected_solids'] for r in rows),
            volume_sum_mm3=vol, source_full_volume_mm3=full,
            recombined_compound_volume_mm3=recombined,
            per_leaf_vs_compound_integration_difference_mm3=vol - recombined,
            refs_without_3D_model=missing,
            refs_without_3D_model_count=len(missing),
            all_geometry_OEM=False,
            frame='KiCad board local mm; board base z=0; component transforms applied once')
        write(D / 'inputs' / ('%s_SOURCE_MAP.json' % tag), summary[tag])
        print('==', tag, len(rows), 'components', summary[tag]['solid_occurrences'], 'solids', flush=True)
    write(D / 'inputs/BOARD_EXTRACTION_SUMMARY.json', {
        'schema': 'R7_BOARD_EXTRACTION_V1',
        'boards': {k: {q: v[q] for q in v if q != 'rows'} for k, v in summary.items()},
        'kicad_version': 'KiCad 10.0 kicad-cli pcb export step --subst-models --no-dnp',
        'board_body_thickness_is_kicad_dielectric': True,
        'nominal_total_stack_applied': False,
        'whole_PCBA_clearance_qualified': False})
