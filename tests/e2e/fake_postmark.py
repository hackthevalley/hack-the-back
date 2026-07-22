import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MESSAGES: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/messages":
            self._json(200, MESSAGES)
        else:
            self._json(404, {"error": "not found"})

    def do_DELETE(self):
        if self.path == "/messages":
            MESSAGES.clear()
            self._json(204, None)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/email":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        MESSAGES.append(json.loads(self.rfile.read(length) or b"{}"))
        self._json(200, {"Message": "OK", "MessageID": str(len(MESSAGES))})

    def _json(self, status: int, body):
        payload = b"" if body is None else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format, *_args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
