"""DEVELOPMENT/TEST ONLY — a tiny imitation of the Telegram Bot API.

Lets the real API server and the real worker be exercised end to end without
reaching api.telegram.org. Never configure this in production.

    python scripts/fake_telegram_api.py --port 8081 --voice /path/voice.ogg

Point the app at it with TELEGRAM_API_BASE=http://localhost:8081.
Recorded calls: GET http://localhost:8081/_calls
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

CALLS: list[dict] = []
VOICE = b""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/_calls":
            return self._json(CALLS)
        if self.path.startswith("/file/bot"):
            self.send_response(200)
            self.send_header("Content-Length", str(len(VOICE)))
            self.end_headers()
            self.wfile.write(VOICE)
            return
        self._json({"ok": False}, 404)

    def do_POST(self):
        method = self.path.rsplit("/", 1)[-1]
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        if ctype.startswith("application/json"):
            data = json.loads(raw or b"{}")
        elif ctype.startswith("multipart/form-data"):
            # Only record what matters: the document size and that it is a PDF
            data = {"multipart_bytes": len(raw), "is_pdf": b"%PDF" in raw}
        else:
            data = {k: v[0] for k, v in parse_qs(raw.decode()).items()}
        CALLS.append({"method": method, "data": data})
        if method == "getFile":
            return self._json({"ok": True, "result": {"file_id": data.get("file_id"), "file_size": len(VOICE),
                                                      "file_path": "voice/file_0.oga"}})
        if method in ("sendMessage", "sendDocument"):
            return self._json({"ok": True, "result": {"message_id": len(CALLS)}})
        return self._json({"ok": True, "result": True})


def main():
    global VOICE
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8081)
    p.add_argument("--voice", required=True)
    a = p.parse_args()
    VOICE = open(a.voice, "rb").read()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
