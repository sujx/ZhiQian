"""ImageProcessor：图片引用处理（file 模式：提取为 assets/ 独立文件）"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from typing import Dict, List, Optional
from urllib.parse import unquote

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_DATA_URI_RE = re.compile(r"data:image/(\w+);base64,(.+)", re.DOTALL)
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}


class ImageProcessor:
    """处理 HTML 中的 img 引用

    strategy="file"（最小版默认）:
        - 本地图片(src 为 index_files/... 等相对路径) → 改 src 为 ./assets/<name>，
          并把图片字节加入待保存列表
        - base64 内嵌图片 → 解码为文件同样提取
    strategy="base64":
        - 本地图片 → 转为 data URL 内嵌（预留，M7 实现）
    """

    def __init__(self, strategy: str = "file"):
        self.strategy = strategy

    def process_images(self, soup: BeautifulSoup,
                       images: Dict[str, bytes]) -> List[dict]:
        """处理 body 内所有 img，返回待落盘资源列表 [{filename, data}]"""
        resources: List[dict] = []

        for img in soup.find_all("img"):
            src = (img.get("src") or "").strip()
            if not src:
                continue

            # 已内嵌 → file 模式提取为文件
            if src.startswith("data:image"):
                if self.strategy == "file":
                    res = self._extract_data_uri(src)
                    if res:
                        img["src"] = f"./assets/{res['filename']}"
                        resources.append(res)
                continue

            # http(s) 外链保留不动
            if src.startswith(("http://", "https://")):
                continue

            # 本地引用：规范化路径后匹配 ZIP 内图片
            normalized = unquote(src).replace("\\", "/")
            normalized = normalized.split("?")[0].split("#")[0]
            candidates = [normalized, os.path.basename(normalized)]

            data = None
            matched = None
            for key in candidates:
                if key in images:
                    data = images[key]
                    matched = key
                    break
            if data is None:
                continue

            if self.strategy == "file":
                filename = self._unique_name(os.path.basename(matched or src), resources)
                img["src"] = f"./assets/{filename}"
                resources.append({"filename": filename, "data": data})
            else:
                img["src"] = self._to_data_url(data, matched or src)

        return resources

    def _extract_data_uri(self, data_uri: str) -> Optional[dict]:
        m = _DATA_URI_RE.match(data_uri)
        if not m:
            return None
        try:
            img_type, b64 = m.group(1), m.group(2)
            data = base64.b64decode(b64)
            digest = hashlib.md5(data).hexdigest()[:8]
            filename = f"image_{digest}.{img_type}"
            return {"filename": filename, "data": data}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"base64 图片解析失败: {e}")
            return None

    @staticmethod
    def _to_data_url(data: bytes, path: str) -> str:
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = f"image/{ext}" if ext else "image/png"
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    @staticmethod
    def _unique_name(filename: str, resources: List[dict]) -> str:
        used = {r["filename"] for r in resources}
        if filename not in used:
            return filename
        stem, ext = os.path.splitext(filename)
        i = 1
        while f"{stem}_{i}{ext}" in used:
            i += 1
        return f"{stem}_{i}{ext}"
