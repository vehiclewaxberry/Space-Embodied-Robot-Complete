"""Continue the one-worker native queue only after each prior job succeeds."""
from pathlib import Path
import json, time
R = Path(__file__).resolve().parents[1]
Q = R / 'queue'

def wait_done(stem, expected_count=None):
    deadline = time.monotonic() + 1500
    p = Q / (stem + '.done')
    while not p.exists():
        if time.monotonic() > deadline:
            raise TimeoutError(stem)
        time.sleep(2)
    result = json.loads(p.read_text(encoding='utf-8-sig'))
    assert result.get('ok') is True, result
    if expected_count is not None:
        assert result['result']['component_count'] == expected_count, result
        assert result['result']['screenshot_saved'] is True, result
    print(json.dumps({'completed': stem, 'ok': True}, ensure_ascii=False), flush=True)

def submit(stem, payload):
    p = Q / (stem + '.json')
    assert not p.exists(), p
    temp = p.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(p)
    print(json.dumps({'queued': stem}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    jobs = json.loads((R / 'results/PLANNED_ASSEMBLY_JOBS.json').read_text(encoding='utf-8'))
    wait_done('024_assembly_parking', 585)
    for stem, index, count in [('025_assembly_released', 2, 585),
                               ('026_assembly_r07', 3, 245),
                               ('027_assembly_b601', 4, 10)]:
        submit(stem, jobs[index])
        wait_done(stem, count)
    submit('028_clean_after_native_assemblies', {'module': 'sw_clean_exit.py'})
    wait_done('028_clean_after_native_assemblies')
