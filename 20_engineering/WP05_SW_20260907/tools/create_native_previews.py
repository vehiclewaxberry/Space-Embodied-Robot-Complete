"""Losslessly convert actual SolidWorks SaveBMP output to displayable PNG."""
from pathlib import Path
import hashlib, json
from PIL import Image
R = Path(__file__).resolve().parents[1]
NAMES = ['WP05_ROBOT_SERVICE', 'WP05_ROBOT_PARKING', 'WP05_ROBOT_RELEASED',
         'WP05_R07_CONNECTIONS', 'WP05_B601_SERVICE']

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    rows = []
    for name in NAMES:
        receipt = R / 'results' / (name + '_COLD.json')
        data = json.loads(receipt.read_text(encoding='utf-8'))
        assert data['screenshot_saved'] is True
        source = R / 'screenshots' / (name + '.bmp')
        target = source.with_suffix('.png')
        assert Path(data['screenshot']).resolve() == source.resolve()
        with Image.open(source) as image:
            size, mode, pixels = image.size, image.mode, image.tobytes()
            image.save(target, format='PNG')
        with Image.open(target) as check:
            assert check.mode == mode and check.size == size and check.tobytes() == pixels
        rows.append({'name': name, 'source': str(source), 'source_sha256': sha(source),
                     'target': str(target), 'target_sha256': sha(target), 'size': size,
                     'pixel_identical': True, 'cold_receipt_sha256': sha(receipt)})
    result = {'status': 'PASS_LOSSLESS_FORMAT_CONVERSION_ONLY', 'previews': rows,
              'geometry_modified': False, 'visual_inspection_performed_by_script': False}
    (R / 'results/PREVIEW_CONVERSION.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'converted': len(rows), 'pixel_identical': True}))

if __name__ == '__main__':
    main()
