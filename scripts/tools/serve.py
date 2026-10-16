"""Local static server for the project folder. The stock `python -m http.server` keeps a listen backlog of 5,
so hundreds of frame files requested at once get refused connections.
usage: python tools/serve.py [port]   (default 8770) -> http://127.0.0.1:8770/web/index.html
"""
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


class Server(ThreadingHTTPServer):
    request_queue_size = 256
    daemon_threads = True


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.js': 'text/javascript', '.mjs': 'text/javascript',
                      '.webmanifest': 'application/manifest+json', '.hdr': 'application/octet-stream'}

    def log_message(self, *a):
        pass


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
print(f'http://127.0.0.1:{port}/', flush=True)
Server(('127.0.0.1', port), partial(Handler, directory=ROOT)).serve_forever()
