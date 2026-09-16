#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != '/chat':
            self.send_response(404); self.end_headers(); return
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b'{}'
        try:
            body = json.loads(raw or b'{}')
        except Exception:
            body = {}
        msg = body.get('message', '')
        reply = f"收到：{msg}\n\n（这是本地回显后端，接你自己的 LLM 只需替换此函数。）"
        data = json.dumps({'reply': reply}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print("[server]", fmt % args)

if __name__ == '__main__':
    print("AETHER backend on http://localhost:8001")
    HTTPServer(('0.0.0.0', 8001), Handler).serve_forever()
