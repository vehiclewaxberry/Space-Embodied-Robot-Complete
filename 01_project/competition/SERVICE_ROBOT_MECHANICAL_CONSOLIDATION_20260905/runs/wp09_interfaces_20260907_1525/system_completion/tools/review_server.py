"""Loopback-only delivery preview. No CAD invocation or external network binding."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from functools import partial
C=Path(__file__).resolve().parents[1]
ThreadingHTTPServer(('127.0.0.1',3252),partial(SimpleHTTPRequestHandler,directory=str(C))).serve_forever()
