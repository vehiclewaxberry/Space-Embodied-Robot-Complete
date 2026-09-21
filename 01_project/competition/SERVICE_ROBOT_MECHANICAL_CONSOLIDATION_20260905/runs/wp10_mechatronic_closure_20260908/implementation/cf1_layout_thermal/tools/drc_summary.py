"""Print a compact summary of a kicad-cli DRC/ERC JSON report."""
import collections, json, sys
from pathlib import Path

p = Path(sys.argv[1])
d = json.loads(p.read_text(encoding='utf-8-sig'))
if 'sheets' in d:  # ERC
    n = sum(len(s['violations']) for s in d['sheets'])
    print(f'ERC {p.name}: sheets={len(d["sheets"])} violations={n}')
    for s in d['sheets']:
        for v in s['violations'][:10]:
            print(' -', v['type'], v['severity'], v['description'][:100])
    sys.exit(0)
print(f'DRC {p.name}: violations={len(d["violations"])} unconnected={len(d["unconnected_items"])} '
      f'parity={len(d.get("schematic_parity", []))} ignored={[x["key"] for x in d["ignored_checks"]]}')
print(dict(collections.Counter((v['type'], v['severity']) for v in d['violations'])))
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 25
for v in d['violations'][:limit]:
    print(' -', v['type'], v['severity'], v['description'][:90], [(i['description'][:70], i.get('pos')) for i in v.get('items', [])][:2])
for u in d['unconnected_items'][:10]:
    print(' U', [(i['description'][:70], i.get('pos')) for i in u['items']])
