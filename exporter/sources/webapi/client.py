"""为知笔记 Web API 客户端：文件夹 / 笔记列表 / 笔记下载"""

from __future__ import annotations

import logging
import threading
import time
from functools import wraps
from typing import Dict, Generator, List, Optional

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 60
_MAX_RETRIES = 3  # 5xx/网络异常重试次数

# 限流装饰器共享锁（多 worker 并发下保证原子性，防止限流失效触发服务端封禁）
_RATE_LOCK = threading.Lock()


def _rate_limit(calls_per_second: int = 8):
    """简单限流装饰器（线程安全：通过共享锁保证 last 时间戳原子更新）"""
    last = [0.0]
    interval = 1.0 / calls_per_second

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with _RATE_LOCK:
                wait = interval - (time.time() - last[0])
                if wait > 0:
                    time.sleep(wait)
                last[0] = time.time()
            result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator


class WizNoteAPIClient:
    """为知笔记官方 API 封装"""

    def __init__(self, auth, kb_guid: str, kb_server: str):
        self.auth = auth
        self.kb_guid = kb_guid
        self.kb_server = kb_server.rstrip("/")

    # ---------- 工具 ----------

    def _get(self, endpoint: str, params: Optional[dict] = None):
        url = f"{self.kb_server}{endpoint}"
        # 调试：打印完整请求（含参数），-v 可见，用于排查服务端参数校验错误
        logger.debug(f"GET {url} params={params}")

        resp = self._request_with_retry(url, params)
        logger.debug(f"<- {resp.status_code} {resp.text[:500]}")
        return resp

    def _request_with_retry(self, url: str, params: Optional[dict] = None):
        """带重试的 GET：仅对 HTTP 5xx / 网络异常 / returnCode==1100 重试

        注意：不能用 "1100" in text 之类子串判断——响应里的 GUID
        可能包含该子串导致误判（曾引发无谓重试）。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = requests.get(url, headers=self.auth.get_headers(),
                                    params=params, timeout=_TIMEOUT)
                if resp.status_code == 401:
                    logger.info("Token 失效，重新登录后重试")
                    if self.auth.login():
                        resp = requests.get(url, headers=self.auth.get_headers(),
                                            params=params, timeout=_TIMEOUT)

                # 重试条件：HTTP 5xx，或服务端参数校验错误（1100/2000，
                # 多实例负载均衡下时好时坏，重试可恢复）
                should_retry = resp.status_code >= 500
                if not should_retry:
                    try:
                        data = resp.json()
                        if isinstance(data, dict):
                            rc = data.get("returnCode")
                            msg = data.get("returnMessage") or ""
                            if rc in (1100, 2000) \
                                    or "invalid options.start" in msg:
                                should_retry = True
                    except ValueError:
                        pass

                if should_retry:
                    last_exc = requests.HTTPError(
                        f"{resp.status_code} {resp.text[:120]}", response=resp)
                    wait = 1.5 * (2 ** attempt)
                    logger.warning(f"服务端异常({resp.status_code})，"
                                   f"{wait:.0f}s 后重试 ({attempt + 1}/{_MAX_RETRIES + 1})")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                last_exc = e
                wait = 1.5 * (2 ** attempt)
                logger.warning(f"请求异常({e.__class__.__name__})，"
                               f"{wait:.0f}s 后重试 ({attempt + 1}/{_MAX_RETRIES + 1})")
                time.sleep(wait)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("请求失败")

    @staticmethod
    def _result(resp) -> Optional[dict]:
        """解析统一响应 {returnCode, result, returnMessage}"""
        try:
            data = resp.json()
        except ValueError:
            return None
        if isinstance(data, dict) and data.get("returnCode") == 200:
            return data.get("result")
        if isinstance(data, dict):
            logger.error(f"API 错误: {data.get('returnMessage')}"
                         f" (returnCode={data.get('returnCode')})")
            return None
        return data  # 直接数组等

    # ---------- 文件夹 ----------

    @_rate_limit()
    def get_all_folders(self) -> List[str]:
        """GET /ks/category/all/:kbGuid → 文件夹路径列表"""
        resp = self._get(f"/ks/category/all/{self.kb_guid}")
        result = self._result(resp)
        if result is None:
            return []
        folders = result if isinstance(result, list) else result.get("result", [])
        return [f if isinstance(f, str) else f.get("categoryPath", f.get("path", "/"))
                for f in folders] or ["/"]

    # ---------- 笔记 ----------

    @_rate_limit()
    def get_notes_in_folder(self, folder: str, start: int = 0,
                            count: int = 100) -> Dict:
        """GET /ks/note/list/category/:kbGuid 分页拉取笔记列表"""
        # 参数集保持最小（部分服务端实例对 withAbstract 等扩展参数校验严格）
        params = {"category": folder, "start": start, "count": count,
                  "orderBy": "modified", "ascending": "desc"}
        resp = self._get(f"/ks/note/list/category/{self.kb_guid}", params)
        result = self._result(resp)
        if result is None:
            return {"notes": [], "total": 0}
        if isinstance(result, list):
            return {"notes": result, "total": len(result)}
        return {"notes": result.get("result", []),
                "total": result.get("total", len(result.get("result", [])))}

    def get_all_notes_in_folder(self, folder: str) -> Generator[dict, None, None]:
        """自动分页遍历文件夹全部笔记"""
        start, count = 0, 100
        while True:
            data = self.get_notes_in_folder(folder, start, count)
            notes = data["notes"]
            if not notes:
                break
            for n in notes:
                yield n
            start += len(notes)
            if len(notes) < count:
                break

    @_rate_limit()
    def download_note(self, doc_guid: str) -> Optional[dict]:
        """GET /ks/note/download/:kbGuid/:docGuid → {html, ...}"""
        resp = self._get(
            f"/ks/note/download/{self.kb_guid}/{doc_guid}",
            params={"downloadInfo": 1, "downloadData": 1})
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return self._result(resp)
        # 可能直接返回 HTML
        return {"html": resp.text, "guid": doc_guid}

    @_rate_limit()
    def download_attachment(self, doc_guid: str, att_guid: str) -> Optional[bytes]:
        """GET /ks/attachment/download/:kbGuid/:docGuid/:attGuid"""
        resp = self._get(
            f"/ks/attachment/download/{self.kb_guid}/{doc_guid}/{att_guid}")
        return resp.content if resp.status_code == 200 else None
