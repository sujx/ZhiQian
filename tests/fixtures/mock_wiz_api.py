"""Mock 为知笔记 Web API 服务器（测试用）

模拟: /as/user/login, /ks/category/all, /ks/note/list/category,
      /ks/note/download, /ks/attachment/list, /ks/attachment/download,
      /as/api/biz/joined

用法: 从测试代码导入 start_mock_server() 获取 (server, base_url)
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Tuple

KB_GUID = "kb-personal-0001"
KB_NAME = "个人笔记"
FOLDERS = ["/", "/技术/", "/技术/Python/", "/生活/"]

NOTES = {
    "/": [
        {"docGuid": "doc-root-1", "title": "根目录笔记",
         "categoryPath": "/", "dataModified": "2026-01-01T10:00:00",
         "attachmentCount": 0},
    ],
    "/技术/": [
        {"docGuid": "doc-tech-1", "title": "技术笔记一",
         "categoryPath": "/技术/", "dataModified": "2026-02-01T10:00:00",
         "attachmentCount": 2},
    ],
    "/技术/Python/": [
        {"docGuid": "doc-py-1", "title": "Python 并发指南",
         "categoryPath": "/技术/Python/", "dataModified": "2026-03-01T10:00:00",
         "attachmentCount": 0},
    ],
    "/生活/": [
        {"docGuid": "doc-life-1", "title": "生活记录",
         "categoryPath": "/生活/", "dataModified": "2026-04-01T10:00:00",
         "attachmentCount": 1},
    ],
}

NOTE_HTML = {
    "doc-root-1": "<html><body><h1>根目录笔记</h1><p>内容A</p></body></html>",
    "doc-tech-1": "<html><body><h2>技术笔记</h2><pre><code class=\"language-python\">x = 1</code></pre></body></html>",
    "doc-py-1": "<html><body><h1>Python 并发</h1><ul><li>线程</li><li>协程</li></ul></body></html>",
    "doc-life-1": "<html><body><h1>生活</h1><p>今天天气不错</p></body></html>",
}

ATTACHMENTS = {
    "doc-tech-1": [
        {"guid": "att-001", "name": "report.pdf",
         "size": 1024, "documentGuid": "doc-tech-1"},
        {"guid": "att-002", "name": "data.csv",
         "size": 256, "documentGuid": "doc-tech-1"},
    ],
    "doc-life-1": [
        {"guid": "att-003", "name": "photo.jpg",
         "size": 2048, "documentGuid": "doc-life-1"},
    ],
}

ATTACHMENT_CONTENT = {
    "att-001": b"%PDF-1.4 mock pdf content",
    "att-002": b"col1,col2\nval1,val2\n",
    "att-003": b"\xff\xd8\xff\xe0 mock jpeg data",
}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静默
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/as/user/login":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not payload.get("userId") or not payload.get("password"):
                self._send_json({"returnCode": 400, "returnMessage": "缺少账号"})
                return
            self._send_json({
                "returnCode": 200,
                "result": {
                    "token": "mock-token-123",
                    "kbGuid": KB_GUID,
                    "kbServer": f"http://{self.server.server_address[0]}:{self.server.server_address[1]}",
                    "userGuid": payload["userId"],
                },
            })
        else:
            self._send_json({"returnCode": 404, "returnMessage": "not found"}, 404)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/as/api/biz/joined":
            self._send_json({"returnCode": 200, "result": []})
            return

        if "/ks/category/all/" in path:
            self._send_json({"returnCode": 200, "result": FOLDERS})
            return

        if "/ks/note/list/category/" in path:
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(self.path).query)
            category = qs.get("category", ["/"])[0]
            notes = NOTES.get(category, [])
            self._send_json({"returnCode": 200, "result": notes, "total": len(notes)})
            return

        if "/ks/note/download/" in path:
            doc_guid = path.rsplit("/", 1)[-1]
            html = NOTE_HTML.get(doc_guid, "<html><body>empty</body></html>")
            resp_data = {
                "html": html, "guid": doc_guid,
                "title": f"笔记 {doc_guid}",
            }
            atts = ATTACHMENTS.get(doc_guid)
            if atts:
                resp_data["attachments"] = atts
            self._send_json({"returnCode": 200, "result": resp_data})
            return

        if "/ks/attachment/list/" in path:
            parts = path.split("/")
            doc_guid = parts[-1]
            atts = ATTACHMENTS.get(doc_guid, [])
            self._send_json({"returnCode": 200, "result": atts})
            return

        if "/ks/attachment/download/" in path:
            att_guid = path.rsplit("/", 1)[-1]
            content = ATTACHMENT_CONTENT.get(att_guid)
            if content:
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json(
                    {"returnCode": 404, "returnMessage": "attachment not found"},
                    404)
            return

        self._send_json({"returnCode": 404, "returnMessage": "not found"}, 404)


def start_mock_server() -> Tuple[ThreadingHTTPServer, str]:
    """启动 mock 服务器，返回 (server, base_url)"""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    host, port = server.server_address
    base = f"http://{host}:{port}"
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, base
