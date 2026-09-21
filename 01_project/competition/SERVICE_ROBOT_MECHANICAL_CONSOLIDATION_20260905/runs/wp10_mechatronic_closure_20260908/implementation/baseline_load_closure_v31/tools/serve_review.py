"""Loopback-only, read-only static preview. No model generation or hardware IO."""
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    server=ThreadingHTTPServer(('127.0.0.1',3291),partial(SimpleHTTPRequestHandler,directory=str(root)))
    server.serve_forever()
