"""为知笔记 Web API 认证：登录换取 Token，获取知识库列表"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 30


class WizNoteAuth:
    """认证管理器：登录 / Token / 知识库（个人+团队）列表"""

    def __init__(self, username: str, password: str, as_url: str):
        self.username = username
        self.password = password
        self.as_url = as_url.rstrip("/")
        self.token: Optional[str] = None
        self.kb_guid: Optional[str] = None
        self.kb_server: Optional[str] = None
        self.user_guid: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.kb_list: List[dict] = []
        # 登录锁：并发 401 时只触发一次登录，避免 token 竞态改写
        self._login_lock = threading.Lock()

    def login(self) -> bool:
        """POST /as/user/login 换取 Token（官方 API）

        线程安全：并发 401 时通过 _login_lock 保证只触发一次真实登录，
        其他 worker double-check 到有效 token 后直接复用。
        """
        # double-check：若已有有效 token 直接返回（避免并发重复登录）
        if self.is_token_valid():
            return True
        with self._login_lock:
            # 再次检查（拿到锁后可能已被其他线程登录）
            if self.is_token_valid():
                return True
            return self._do_login()

    def _do_login(self) -> bool:
        """实际执行登录请求（持锁调用）"""
        try:
            resp = requests.post(
                f"{self.as_url}/as/user/login",
                json={"userId": self.username, "password": self.password},
                timeout=_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.error(f"登录请求失败: HTTP {resp.status_code}")
                return False
            result = resp.json()
            if result.get("returnCode") != 200:
                logger.error(f"登录失败: {result.get('returnMessage')}")
                return False

            auth = result["result"]
            self.token = auth.get("token")
            self.kb_guid = auth.get("kbGuid")
            self.kb_server = auth.get("kbServer")
            self.user_guid = auth.get("userGuid", self.username)
            self.token_expiry = datetime.now() + timedelta(hours=24)
            logger.info(f"登录成功，服务器: {self.kb_server}")
            self._load_kb_list()
            return True
        except requests.RequestException as e:
            logger.error(f"登录请求异常: {e}")
            return False

    def _load_kb_list(self) -> None:
        """知识库列表：个人库 + 团队库"""
        self.kb_list = [{
            "kbGuid": self.kb_guid, "kbServer": self.kb_server,
            "name": "个人笔记", "type": "personal",
        }]
        # 团队知识库（尽力而为，失败不影响个人库）
        try:
            biz = requests.get(
                f"{self.as_url}/as/api/biz/joined", headers=self.get_headers(),
                timeout=_TIMEOUT)
            if biz.status_code == 200 and biz.json().get("returnCode") == 200:
                for b in biz.json().get("result", []):
                    kb = requests.get(
                        f"{self.as_url}/as/biz/user_kb_list?bizGuid={b['bizGuid']}",
                        headers=self.get_headers(), timeout=_TIMEOUT)
                    if kb.status_code == 200 and kb.json().get("returnCode") == 200:
                        info = kb.json().get("result", {})
                        if info:
                            self.kb_list.append({
                                "kbGuid": info["kbGuid"],
                                "kbServer": info["kbServer"],
                                "name": f"{b['bizName']} - 团队笔记",
                                "type": "team",
                            })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"获取团队知识库失败（忽略）: {e}")
        logger.info(f"共 {len(self.kb_list)} 个知识库")

    # ---------- 会话状态 ----------

    def is_token_valid(self) -> bool:
        return (self.token is not None and self.token_expiry is not None
                and datetime.now() < self.token_expiry - timedelta(minutes=5))

    def get_headers(self) -> Dict[str, str]:
        return {
            "X-Wiz-Token": self.token or "",
            "Content-Type": "application/json",
            "User-Agent": "WizNote-Exporter/0.1",
        }

    def get_kb_list(self) -> List[dict]:
        return self.kb_list

    def switch_kb(self, kb_guid: str) -> bool:
        for kb in self.kb_list:
            if kb["kbGuid"] == kb_guid:
                self.kb_guid = kb["kbGuid"]
                self.kb_server = kb["kbServer"]
                logger.info(f"切换到知识库: {kb['name']}")
                return True
        return False
