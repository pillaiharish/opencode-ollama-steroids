from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from json import dumps


def response_for_path(path: str) -> tuple[int, dict[str, str]]:
    if path == "/":
        return 200, {"message": "tiny app"}
    if path == "/health":
        return 200, {"status": "ok"}
    return 404, {"error": "not found"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        status, payload = response_for_path(self.path)
        body = dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return
