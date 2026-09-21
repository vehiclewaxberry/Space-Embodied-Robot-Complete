from pathlib import Path
R=Path(__file__).resolve().parents[1];source=R/'tools/build_module_native_bounded.py';text=source.read_text()
old="ap.add_argument('--batch',type=int,required=True);a=ap.parse_args()"
new="ap.add_argument('--batch',type=int,required=True);ap.add_argument('--local-check',type=Path);a=ap.parse_args()"
assert old in text;text=text.replace(old,new,1)
old="ep=R/'results'/kind/'EMISSION.json';cp=R/'results'/kind/'CHECK.json'"
new="ep=R/'results'/kind/'EMISSION.json';cp=a.local_check or R/'results'/kind/'CHECK.json'"
assert old in text;text=text.replace(old,new,1)
p=R/'tools/build_module_native_bounded_v2.py';assert not p.exists();p.write_text(text,encoding='utf-8');print(p)

