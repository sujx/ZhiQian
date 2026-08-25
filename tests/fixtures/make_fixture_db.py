"""构造为知笔记迷你测试库（SQLite + ZIP + 附件）

用法: python tests/fixtures/make_fixture_db.py <输出目录>
"""

from __future__ import annotations

import base64
import os
import sqlite3
import sys
import zipfile
from pathlib import Path

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def build_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE WIZ_DOCUMENT (
            DOCUMENT_GUID TEXT PRIMARY KEY,
            DOCUMENT_TITLE TEXT,
            DOCUMENT_LOCATION TEXT,
            DT_CREATED TEXT,
            DT_MODIFIED TEXT,
            DT_ACCESSED TEXT,
            DOCUMENT_ATTACHEMENT_COUNT INTEGER,
            DOCUMENT_DATA_MD5 TEXT
        );
        CREATE TABLE WIZ_TAG (
            TAG_GUID TEXT PRIMARY KEY,
            TAG_NAME TEXT
        );
        CREATE TABLE WIZ_DOCUMENT_TAG (
            DOCUMENT_GUID TEXT,
            TAG_GUID TEXT
        );
        CREATE TABLE WIZ_DOCUMENT_ATTACHMENT (
            ATTACHMENT_GUID TEXT PRIMARY KEY,
            DOCUMENT_GUID TEXT,
            ATTACHMENT_NAME TEXT,
            ATTACHMENT_DATA_MD5 TEXT
        );
        CREATE TABLE WIZ_META (
            META_NAME TEXT,
            META_KEY TEXT,
            META_VALUE TEXT
        );
    """)
    conn.execute(
        "INSERT INTO WIZ_DOCUMENT VALUES (?,?,?,?,?,?,?,?)",
        ("doc-0001", "笔记一：列表与标题", "/技术/前端", "2026-01-01T10:00:00",
         "2026-01-02T11:00:00", "2026-01-02T11:00:00", 0, "md5-1"),
    )
    conn.execute(
        "INSERT INTO WIZ_DOCUMENT VALUES (?,?,?,?,?,?,?,?)",
        ("doc-0002", "笔记二：代码块与表格", "/技术/Python", "2026-01-03T09:00:00",
         "2026-01-04T09:00:00", "2026-01-04T09:00:00", 0, "md5-2"),
    )
    conn.execute(
        "INSERT INTO WIZ_DOCUMENT VALUES (?,?,?,?,?,?,?,?)",
        ("doc-0003", "笔记三：含图片与附件", "/读书", "2026-01-05T08:00:00",
         "2026-01-05T08:00:00", "2026-01-05T08:00:00", 2, "md5-3"),
    )
    conn.executemany(
        "INSERT INTO WIZ_TAG VALUES (?,?)",
        [("tag-1", "前端"), ("tag-2", "Python"), ("tag-3", "读书")],
    )
    conn.executemany(
        "INSERT INTO WIZ_DOCUMENT_TAG VALUES (?,?)",
        [("doc-0001", "tag-1"), ("doc-0002", "tag-2"), ("doc-0003", "tag-3")],
    )
    conn.executemany(
        "INSERT INTO WIZ_DOCUMENT_ATTACHMENT VALUES (?,?,?,?)",
        [
            ("att-0001", "doc-0003", "参考文档.pdf", "md5-a"),
            ("att-0002", "doc-0003", "screenshot.png", "md5-b"),
        ],
    )
    conn.execute(
        "INSERT INTO WIZ_META VALUES (?,?,?)",
        ("DATABASE", "NAME", "测试群组"),
    )
    conn.commit()


def build_note_zip(zip_path: Path, html: str, images: dict[str, bytes]) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", html)
        for name, data in images.items():
            zf.writestr(name, data)


def main(out_dir: str = "") -> None:
    """生成 fixture 库。out_dir 为空时从命令行参数读取（兼容 pytest 调用）"""
    if out_dir:
        out = Path(out_dir)
    else:
        out = Path(sys.argv[1] if len(sys.argv) > 1 else "fixture_wiznote")
    email = "test@wiznote.local"
    data_dir = out / email / "data"
    notes_dir = data_dir / "notes"
    att_dir = data_dir / "attachments"
    notes_dir.mkdir(parents=True, exist_ok=True)
    att_dir.mkdir(parents=True, exist_ok=True)

    # 个人库
    conn = sqlite3.connect(str(data_dir / "index.db"))
    build_db(conn)
    conn.close()

    build_note_zip(
        notes_dir / "{doc-0001}",
        """<html><body>
<h1>笔记一：列表与标题</h1>
<p>这是一个<strong>加粗</strong>和<em>斜体</em>的测试。</p>
<ul>
<li>项目 A</li>
<li>项目 B</li>
</ul>
<ol>
<li>步骤 1</li>
<li>步骤 2</li>
</ol>
<p><a href="https://example.com">示例链接</a></p>
</body></html>""",
        {},
    )
    build_note_zip(
        notes_dir / "{doc-0002}",
        """<html><body>
<h2>代码块与表格</h2>
<pre><code class="language-python">
def hello():
    print("Hello")
    return 42
</code></pre>
<table>
<tr><th>列A</th><th>列B</th></tr>
<tr><td>1</td><td>2</td></tr>
<tr><td>3</td><td>4</td></tr>
</table>
</body></html>""",
        {},
    )
    build_note_zip(
        notes_dir / "{doc-0003}",
        """<html><body>
<h2>含图片与附件</h2>
<p>本地图片引用：</p>
<img src="index_files/pic.png" alt="本地图">
<p>内嵌 base64 图片：</p>
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" alt="内嵌图">
</body></html>""",
        {"index_files/pic.png": PNG_1PX},
    )

    # 附件文件
    (att_dir / "att-0001参考文档.pdf").write_bytes(b"%PDF-1.4 fake pdf content")
    (att_dir / "att-0002screenshot.png").write_bytes(PNG_1PX)

    # 群组库
    group_dir = out / email / "group" / "grp-0001"
    (group_dir / "notes").mkdir(parents=True, exist_ok=True)
    gconn = sqlite3.connect(str(group_dir / "index.db"))
    build_db(gconn)
    gconn.execute("DELETE FROM WIZ_DOCUMENT WHERE DOCUMENT_GUID != 'doc-0001'")
    gconn.commit()
    gconn.close()
    (group_dir / "notes" / "{doc-0001}").write_bytes(
        (notes_dir / "{doc-0001}").read_bytes()
    )

    print(f"fixture 已生成: {out}")
    print(f"  个人库: {data_dir}")
    print(f"  群组库: {group_dir}")


if __name__ == "__main__":
    main()
