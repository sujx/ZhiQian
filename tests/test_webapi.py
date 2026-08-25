"""WebAPISource 集成测试（mock 服务器）+ 重试机制测试"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.disable(logging.CRITICAL)

from exporter.config import ExportConfig
from exporter.sources.webapi.auth import WizNoteAuth
from exporter.sources.webapi.client import WizNoteAPIClient
from exporter.sources.webapi.source import WebAPISource


def _fake_auth(base: str) -> WizNoteAuth:
    auth = WizNoteAuth("u", "p", base)
    auth.token = "tok"
    auth.kb_guid = "kb-1"
    auth.kb_server = base
    auth.token_expiry = datetime.now() + timedelta(hours=1)
    return auth


class TestWebAPISource:
    def test_full_chain(self, mock_server):
        src = WebAPISource("test@wiz.local", "secret", mock_server)
        assert src.login()
        kbs = src.discover_sources()
        assert "个人笔记" in kbs
        src.switch_source("个人笔记")
        folders = src.get_folder_list()
        assert "/技术/Python/" in folders
        docs = src.get_all_documents(folders=["/技术/Python/"])
        assert len(docs) == 1
        assert docs[0].title == "Python 并发指南"
        html, _ = src.get_document_html(docs[0].guid)
        assert html and "Python 并发" in html

    def test_end_to_end_export(self, mock_server, tmp_output):
        from exporter.app import WizNoteExporter

        cfg = ExportConfig(
            source_type="webapi", username="u", password="p", as_url=mock_server,
            kb_guid="kb-personal-0001",
            include_folders=["/技术/", "/技术/Python/", "/生活/"],
            output_dir=str(tmp_output), max_workers=2)
        stats = WizNoteExporter(cfg).export_all()
        assert stats.total == 3 and stats.success == 3 and stats.failed == 0
        files = list(tmp_output.rglob("*.md"))
        assert len(files) == 3

    def test_folder_filter(self, mock_server):
        src = WebAPISource("u", "p", mock_server)
        src.login()
        src.switch_source("个人笔记")
        docs = src.get_all_documents(folders=["/生活/"])
        titles = [d.title for d in docs]
        assert titles == ["生活记录"]


class TestRetry:
    """重试机制：5xx 重试、精确 1100 重试、1100 子串不误判"""

    def _make_server(self, handler_cls):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def test_503_retry_then_success(self):
        state = {"hits": 0}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                state["hits"] += 1
                if state["hits"] < 3:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b"Service Temporarily Unavailable")
                else:
                    body = json.dumps({"returnCode": 200, "result": ["/a/"]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

        server = self._make_server(H)
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            client = WizNoteAPIClient(_fake_auth(base), "kb-1", base)
            folders = client.get_all_folders()
            assert folders == ["/a/"]
            assert state["hits"] == 3
        finally:
            server.shutdown()

    def test_1100_substring_not_retried(self):
        """成功响应 JSON 含 '1100' 子串（GUID）时不得重试"""
        state = {"hits": 0}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                state["hits"] += 1
                body = json.dumps({
                    "returnCode": 200, "returnMessage": "OK",
                    "result": [{"kbGuid": "53ab9ae6-1100-465f"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = self._make_server(H)
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            client = WizNoteAPIClient(_fake_auth(base), "kb-1", base)
            resp = client._get("/ks/category/all/kb-1")
            assert resp.status_code == 200
            assert state["hits"] == 1, "含 1100 子串的成功响应不应触发重试"
        finally:
            server.shutdown()

    def test_exact_1100_retried(self):
        """returnCode 精确 == 1100 时重试"""
        state = {"hits": 0}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                state["hits"] += 1
                if state["hits"] < 2:
                    body = json.dumps(
                        {"returnCode": 1100, "returnMessage": "invalid options"}).encode()
                else:
                    body = json.dumps({"returnCode": 200, "result": ["/a/"]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = self._make_server(H)
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            client = WizNoteAPIClient(_fake_auth(base), "kb-1", base)
            client.get_all_folders()
            assert state["hits"] == 2, "精确 1100 应重试一次"
        finally:
            server.shutdown()

    def test_real_2000_options_error_retried(self):
        """真实场景：returnCode=2000 + 'invalid options.start (1100)' 消息应重试"""
        state = {"hits": 0}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                state["hits"] += 1
                if state["hits"] < 2:
                    body = json.dumps({"returnCode": 2000,
                                       "returnMessage": "invalid options.start (1100)"}).encode()
                else:
                    body = json.dumps({"returnCode": 200, "result": ["/a/"]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = self._make_server(H)
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            client = WizNoteAPIClient(_fake_auth(base), "kb-1", base)
            folders = client.get_all_folders()
            assert folders == ["/a/"]
            assert state["hits"] == 2, f"returnCode=2000 应重试一次, 实际 {state['hits']}"
        finally:
            server.shutdown()
