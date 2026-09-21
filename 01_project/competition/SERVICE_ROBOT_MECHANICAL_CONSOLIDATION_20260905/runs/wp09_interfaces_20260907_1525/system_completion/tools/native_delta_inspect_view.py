"""Record actual pixel inspection; API image success is not a useful model view."""
from pathlib import Path
import hashlib,json
from PIL import Image
C=Path(__file__).resolve().parents[1]
source=C/'results/NATIVE_DELTA_VIEW_service.json'
j=json.loads(source.read_text());p=Path(j['native_view_capture']['path'])
assert j['status']=='PASS_ACTUAL_NATIVE_LARGE_DESIGN_REVIEW_IMAGE'
def sha(x):return hashlib.sha256(x.read_bytes()).hexdigest()
assert sha(p)==j['native_view_capture']['sha256']
with Image.open(p) as im:
 rgb=im.convert('RGB');extrema=rgb.getextrema();uniform=all(lo==hi for lo,hi in extrema)
 assert uniform,'Observed image differs from manually inspected pure gray result'
 r={'status':'REJECT_BLANK_NATIVE_VIEW_NO_MODEL_GRAPHICS','state':'service','image':str(p),'image_sha256':sha(p),'source_api_receipt':str(source),'source_api_receipt_sha256':sha(source),'size_pixels':list(rgb.size),'rgb_extrema':extrema,'all_pixels_identical':uniform,'manual_visual_inspection':'Actual BMP viewed by agent: entire image is uniform gray with no model visible.','accepted_as_model_view':False,'native_save_and_cold_read_credit_changed':False,'probable_cause_inference':'LDR display cache unavailable after hidden native assembly save; inference only, not independently diagnosed.'}
out=C/'results/NATIVE_DELTA_VIEW_REVIEW_service.json';assert not out.exists();out.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
