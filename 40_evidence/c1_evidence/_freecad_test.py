import faulthandler
import json
import os
import sys
import time
import traceback

faulthandler.enable()
faulthandler.dump_traceback_later(300, repeat=True)

LOG_PATH = r'F:\Space-Embodied-Robot-HAG_A_20260804\05_link_ownership\test_freecad.log'

def mark(stage, **data):
    record = {'time': time.strftime('%Y-%m-%dT%H:%M:%S'), 'pid': os.getpid(), 'stage': stage}
    record.update(data)
    line = json.dumps(record, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
        f.flush()
        os.fsync(f.fileno())

mark('BEFORE_FREECAD_IMPORT')
import FreeCAD as App
mark('AFTER_FREECAD_IMPORT', version=str(App.Version()))
print('FREECAD_IMPORT_OK')