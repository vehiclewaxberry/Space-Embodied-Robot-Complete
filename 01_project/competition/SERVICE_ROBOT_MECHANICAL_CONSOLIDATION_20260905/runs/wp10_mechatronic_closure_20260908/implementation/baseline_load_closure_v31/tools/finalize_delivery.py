"""Publish navigation and verify a bounded input/calculation archive, not a CAD release."""
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import csv
import hashlib
import json
import zipfile

P = Path(__file__).resolve().parents[1]
A = P.parent
TOP = A.parents[2]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href')


def main():
    validation = json.loads((P / 'results/VALIDATION.json').read_text(encoding='utf-8'))
    if not validation['passed']:
        raise RuntimeError('V31 validation not passed')
    review = json.loads((P / 'results/INDEPENDENT_REVIEW.json').read_text(encoding='utf-8'))
    for name, expected in review['reviewed_source_sha256'].items():
        if sha(P / name) != expected:
            raise RuntimeError('Reviewed source changed: ' + name)
    page = (P / 'REVIEW.html').read_text(encoding='utf-8')
    if '__DATA__' in page:
        raise RuntimeError('Unrendered page payload')
    payload = page.split('<script>const data=', 1)[1].split(';const $=', 1)[0]
    data = json.loads(payload)
    if (len(data['points']), len(data['ledgers']), len(data['actions'])) != (64, 32, 7):
        raise RuntimeError('Unexpected displayed data counts')
    parser = LinkParser()
    parser.feed(page)
    for link in parser.links:
        parsed = urlsplit(link)
        if not parsed.scheme and parsed.path and not (P / unquote(parsed.path)).is_file():
            raise RuntimeError('Broken report link: ' + link)

    nav = TOP / 'CURRENT_candidate.md'
    pointer = A / 'CURRENT_WORKING_CANDIDATE.json'
    if not nav.is_file() or not pointer.is_file():
        raise RuntimeError('Canonical navigation not found')
    current = json.loads(pointer.read_text(encoding='utf-8-sig'))
    if current['revision'] != 'V30' or current['whole_design_complete'] is not False:
        raise RuntimeError('Unexpected physical candidate identity; review before navigation update')
    history = P / 'history'
    snapshots = {}
    for source, name in [(nav, 'CURRENT_candidate_before_V31.md'), (pointer, 'CURRENT_WORKING_CANDIDATE_before_V31.json')]:
        backup = history / name
        if not backup.exists():
            backup.write_bytes(source.read_bytes())
        snapshots[str(source)] = {'snapshot': backup.relative_to(P).as_posix(), 'before_sha256': sha(backup)}
    marker = '## WP10 V31 输入基线与条件计算（2026-09-11）'
    old_nav = nav.read_text(encoding='utf-8-sig')
    prefix = '''## WP10 V31 输入基线与条件计算（2026-09-11）

最新输入与分析入口：[交互报告](runs/wp10_mechatronic_closure_20260908/implementation/baseline_load_closure_v31/REVIEW.html) / [设计说明](runs/wp10_mechatronic_closure_20260908/implementation/baseline_load_closure_v31/README_ZH.md) / [机器状态](runs/wp10_mechatronic_closure_20260908/implementation/baseline_load_closure_v31/DELIVERY_STATUS_V31.json) / [后续改件表](runs/wp10_mechatronic_closure_20260908/implementation/baseline_load_closure_v31/NEXT_ENGINEERING_ACTIONS.csv)。

已形成974行实例登记、2922行姿态记录、参考任务和DM负载参数接口，完成64个供电点、32个相位能源情景；65项软件/参数检查及7项电气产物断言通过，649个唯一来源与消费输入哈希核对一致。这些数字只代表本输入和条件计算包的验证范围。

**物理候选仍为V30，原生宿主仍为873叶件三态。** 974是完整源计划，V30局部56子件/60实体未回装。本轮没有新建CAD、改ECAD或进行实物试验；完整物性、实际负载、停止/回生、加热支路、热路安装、推进受控接口及4项Kelvin连接仍待工程关闭。全机设计、制造、上电与飞行放行未完成。

下方内容为历史记录，各自的“当前/最新”仅对应记录时刻；不作为V31的现状描述。

---

'''
    if marker not in old_nav:
        nav.write_text(prefix + old_nav, encoding='utf-8')
    current['active_input_closure'] = {
        'revision': 'V31',
        'kind': 'INPUT_BASELINE_AND_CONDITIONAL_CALCULATION',
        'entry': 'baseline_load_closure_v31/REVIEW.html',
        'status': 'baseline_load_closure_v31/DELIVERY_STATUS_V31.json',
        'native_CAD_updated': False,
        'ECAD_updated': False,
        'whole_design_complete': False,
    }
    write_json(pointer, current)
    for path, record in snapshots.items():
        record['after_sha256'] = sha(Path(path))
    write_json(P / 'results/NAVIGATION_UPDATE.json', {
        'time': datetime.now().astimezone().isoformat(),
        'files': snapshots,
        'physical_candidate_revision_preserved': 'V30',
        'legacy_gates_modified': False,
    })
    write_json(P / 'results/REPORT_LINK_CHECK.json', {
        'passed': True,
        'local_report_links_checked': len(parser.links),
        'embedded_data_counts': {'steady': 64, 'phase': 32, 'actions': 7},
        'independently_reviewed_source_hashes_matched': True,
        'check_type': 'Static parsing and data/link verification; not browser visual inspection',
    })

    archive = P / 'WP10_V31_INPUT_AND_LOAD_PACKAGE.zip'
    manifest = P / 'SHA256_V31.csv'
    receipt = P / 'results/PACKAGE_READBACK.json'
    exclusions = {archive, manifest, receipt}
    files = sorted(f for f in P.rglob('*') if f.is_file() and f not in exclusions
                   and '__pycache__' not in f.parts and f.suffix.lower() not in {'.pyc', '.log'})
    records = [{'path': f.relative_to(P).as_posix(), 'bytes': f.stat().st_size, 'sha256': sha(f)} for f in files]
    with manifest.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['path', 'bytes', 'sha256'])
        w.writeheader()
        w.writerows(records)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in files + [manifest]:
            z.write(f, f.relative_to(P).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError('ZIP CRC check failed')
        for r in records:
            if hashlib.sha256(z.read(r['path'])).hexdigest() != r['sha256']:
                raise RuntimeError('ZIP content mismatch: ' + r['path'])
        if z.read(manifest.name) != manifest.read_bytes():
            raise RuntimeError('ZIP manifest mismatch')
    result = {
        'passed': True,
        'archive': archive.name,
        'archive_bytes': archive.stat().st_size,
        'archive_sha256': sha(archive),
        'payload_files': len(records),
        'archive_entries_including_manifest': len(records) + 1,
        'all_crc_and_payload_hashes_matched': True,
        'scope': 'Input baseline and conditional analysis; original workspace CAD and source dependencies are not bundled.',
        'excluded': ['Archive itself', 'This external archive receipt', '__pycache__', '*.pyc', '*.log'],
        'manifest_scope': 'All payload files; excludes manifest itself and external archive receipt.',
    }
    write_json(receipt, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
