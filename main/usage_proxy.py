from __future__ import annotations

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from usage_logger import log_usage

TARGET_HOST = "api.deepseek.com"
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 52848

logger = logging.getLogger(__name__)


class _Handler(BaseHTTPRequestHandler):
    proxy_ref: "UsageProxy | None" = None

    def _forward(self, method: str):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""

        api_key = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        is_chat = method == "POST" and "/chat/completions" in self.path

        is_streaming = False
        if body and is_chat:
            try:
                is_streaming = json.loads(body).get("stream", False)
            except Exception:
                pass

        target = self.proxy_ref._target_host if self.proxy_ref else TARGET_HOST

        fwd_headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ("host", "content-length", "connection",
                                 "keep-alive", "proxy-connection")
        }

        import http.client
        conn = http.client.HTTPSConnection(target, timeout=120)
        try:
            conn.request(method, self.path, body=body, headers=fwd_headers)
            resp = conn.getresponse()

            self.send_response(resp.status)

            if is_streaming and is_chat:
                for k, v in resp.getheaders():
                    if k.lower() not in ("transfer-encoding", "content-length", "connection"):
                        self.send_header(k, v)
                self.send_header("Connection", "close")
                self.end_headers()

                usage_text = ""
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    if api_key:
                        usage_text += chunk.decode("utf-8", errors="replace")

                if api_key and usage_text:
                    for line in reversed(usage_text.split("\n")):
                        if line.startswith("data: ") and "usage" in line and "[DONE]" not in line:
                            try:
                                d = json.loads(line[6:])
                                if isinstance(d.get("usage"), dict):
                                    log_usage(api_key, d["usage"])
                            except Exception:
                                pass
                            break
            else:
                resp_body = resp.read()
                for k, v in resp.getheaders():
                    if k.lower() not in ("transfer-encoding",):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)

                if is_chat and api_key:
                    try:
                        d = json.loads(resp_body)
                        if isinstance(d.get("usage"), dict):
                            log_usage(api_key, d["usage"])
                    except Exception:
                        pass
        finally:
            conn.close()

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def do_PUT(self):
        self._forward("PUT")

    def do_DELETE(self):
        self._forward("DELETE")

    def do_PATCH(self):
        self._forward("PATCH")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def log_message(self, format, *args):
        pass


class UsageProxy:
    def __init__(self, host: str = PROXY_HOST, port: int = PROXY_PORT, target_host: str = TARGET_HOST):
        self._host = host
        self._port = port
        self._target_host = target_host
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        if self._server is not None:
            return

        class _HandlerWithRef(_Handler):
            proxy_ref = self

        self._server = HTTPServer((self._host, self._port), _HandlerWithRef)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="UsageProxy",
        )
        self._thread.start()

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server = None
            self._thread = None

    @property
    def proxy_url(self) -> str:
        return f"http://{self._host}:{self._port}/v1"
