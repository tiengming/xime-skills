import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "xime-index-submit"

ASSET_BYTES = b"xime" * 1000


def closed_port_url(path="/asset.bin"):
    """Return a localhost URL whose port is closed (connection refused)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    finally:
        sock.close()
    return f"http://127.0.0.1:{port}{path}"


def run_cli(args, cwd=None):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/asset.bin":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(ASSET_BYTES)))
            self.end_headers()
            self.wfile.write(ASSET_BYTES)
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/asset.bin")
            self.end_headers()
        elif self.path == "/missing":
            self.send_response(404)
            self.end_headers()
        elif self.path == "/slow":
            time.sleep(3)
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_args):
        pass


class HTTPFixture:
    def __init__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        return self.start()

    def __exit__(self, *_exc):
        self.stop()
