"""Read AUX and STOP footprint geometry back out of KiCad itself.

Runs under the KiCad-bundled interpreter (pcbnew), the same route the MAIN board
readback used, so footprint bounding boxes come from KiCad's own geometry engine
rather than from a text parse of the board file. Read-only: the boards are opened
and never saved.

    G:/Windows_program_file/Kicad/bin/python.exe readback_population.py
"""
import json, hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.dirname(HERE)
BOARDS = [('AUX', 'wp10_aux_protection'), ('STOP', 'wp10_stop_control')]


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    import pcbnew
    nm = 1e6  # KiCad internal units (nm) per mm
    out = {}
    for tag, stem in BOARDS:
        path = os.path.join(D, 'sources', stem + '.kicad_pcb')
        board = pcbnew.LoadBoard(path)
        rows = []
        for fp in board.GetFootprints():
            bb = fp.GetBoundingBox(False, False)
            pos = fp.GetPosition()
            pads = []
            for pad in fp.Pads():
                p = pad.GetPosition()
                drill = pad.GetDrillSize()
                sz = pad.GetSize()
                pads.append(dict(pin=pad.GetNumber(), net=pad.GetNetname(),
                                 xy_mm=[p.x / nm, p.y / nm],
                                 size_mm=[sz.x / nm, sz.y / nm],
                                 drill_mm=[drill.x / nm, drill.y / nm]))
            rows.append(dict(
                ref=fp.GetReference(), value=fp.GetValue(),
                fp_id=str(fp.GetFPID().GetUniStringLibId()),
                xy_mm=[pos.x / nm, pos.y / nm],
                angle_deg=fp.GetOrientationDegrees(),
                bbox_mm=[bb.GetLeft() / nm, bb.GetTop() / nm, bb.GetRight() / nm, bb.GetBottom() / nm],
                models=[m.m_Filename for m in fp.Models()],
                through_hole=bool(fp.HasThroughHolePads()),
                pads=pads))
        rows.sort(key=lambda r: r['ref'])
        stack = board.GetDesignSettings().GetBoardThickness() / nm
        edge = board.GetBoardEdgesBoundingBox()
        out[tag] = dict(
            source=path, source_sha256=sha(path), thickness_mm=stack,
            board_edges_bbox_mm=[edge.GetLeft() / nm, edge.GetTop() / nm,
                                 edge.GetRight() / nm, edge.GetBottom() / nm],
            board_size_mm=[edge.GetWidth() / nm, edge.GetHeight() / nm],
            footprints=rows, footprints_total=len(rows),
            refs_with_model=sum(1 for r in rows if r['models']),
            board_saved_by_this_tool=False)
        print('%-5s %3d footprints, %2d with 3D, board %.2f x %.2f mm, stack %.3f mm' % (
            tag, len(rows), out[tag]['refs_with_model'],
            out[tag]['board_size_mm'][0], out[tag]['board_size_mm'][1], stack), flush=True)
    for tag in out:
        with open(os.path.join(D, 'inputs', '%s_POPULATION_READBACK.json' % tag), 'w', encoding='utf-8') as f:
            json.dump(out[tag], f, ensure_ascii=False, indent=2, allow_nan=False)
    print('kicad', pcbnew.GetBuildVersion(), flush=True)


if __name__ == '__main__':
    main()
