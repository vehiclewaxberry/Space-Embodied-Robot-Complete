"""Loopback-only static review of this project's engineering run artifacts."""
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
RUNS=Path(__file__).resolve().parents[2]
if __name__=='__main__':
    ThreadingHTTPServer(('127.0.0.1',3253),partial(SimpleHTTPRequestHandler,directory=str(RUNS))).serve_forever()
