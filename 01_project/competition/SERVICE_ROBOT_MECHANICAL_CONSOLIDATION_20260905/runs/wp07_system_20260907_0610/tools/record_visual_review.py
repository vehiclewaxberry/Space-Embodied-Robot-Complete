"""Record root's actual image review; never infer engineering release from images."""
from pathlib import Path
import hashlib
import json
from datetime import datetime

R = Path(__file__).resolve().parents[1]
def pin(p):
    return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
def main():
    groups = []
    for prefix, observation in (
        ('retention0_', 'Four actual PNGs reviewed. Mast, two guide rods, split lower collars, saddle and nominal retaining hardware are visible. Opposite view is distinct. Orthographic overlap is expected; images do not prove clearance or load capacity.'),
        ('retention1_', 'Four actual PNGs reviewed. Second station has its own mast and guide span. Lower collar, paired guide rods and upper retaining hardware are visible. Its source/native measured checks provide the dimensional evidence.'),
        ('pcb_reference_', 'Four actual PNGs reviewed. Four separated bare reference boards, outline notches, holes and internal cutouts are visible. Thin edge-on front view is expected. This display layout is not an installed spacecraft PCB assembly or a routed electrical design.'),
    ):
        paths = sorted((R/'results/snapshots').glob(prefix+'*.png'))
        assert len(paths) == 4
        groups.append({'id': prefix.rstrip('_'), 'reviewed': True, 'status': 'REVIEWED_DISPLAY_ONLY', 'images': [pin(p) for p in paths], 'observations': observation})
    out = R/'results/VISUAL_REVIEW.json'
    assert not out.exists()
    out.write_text(json.dumps({'schema': 'WP07_ROOT_VISUAL_REVIEW_V1', 'recorded_local': datetime.now().astimezone().isoformat(), 'status': 'LOCAL_IMAGES_REVIEWED__WHOLE_IMAGE_PENDING', 'groups': groups, 'whole_service_reviewed': False, 'engineering_release': False, 'scope': 'Actual root view_image review of the 12 named PNGs. Numerical CAD validation is separately recorded; image appearance does not certify physical assembly, strength, continuous motion or electrical readiness.'}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'output':str(out), 'images_reviewed':12}))
if __name__ == '__main__':
    main()
