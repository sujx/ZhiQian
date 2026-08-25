"""命令行入口"""

from __future__ import annotations

import argparse
import logging
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m exporter",
        description="为知笔记导出 Markdown 工具",
        epilog="示例:\n"
               "  python -m exporter --source local --input <为知数据目录> --list\n"
               "  python -m exporter --source local --input <为知数据目录> --output ./notes\n"
               "  python -m exporter --source local --input <目录> --guid <GUID>\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source", choices=["local", "webapi"], default="local",
                        help="数据源类型 (默认 local)")
    parser.add_argument("--input", help="为知笔记本地数据目录")
    parser.add_argument("--output", default="./notes", help="输出目录 (默认 ./notes)")
    parser.add_argument("--username", help="webapi: 为知笔记账号")
    parser.add_argument("--password", help="webapi: 密码")
    parser.add_argument("--as-url", default=None, help="webapi: AS 服务器地址")
    parser.add_argument("--list-kb", action="store_true",
                        help="webapi: 列出所有知识库并退出")
    parser.add_argument("--kb", help="webapi: 指定知识库 GUID (默认个人库)")
    parser.add_argument("--folders", nargs="+",
                        help="webapi: 指定要导出的文件夹（多值）")
    parser.add_argument("--list", action="store_true", help="仅列出所有笔记")
    parser.add_argument("--find", action="store_true",
                        help="自动查找为知笔记数据目录并退出")
    parser.add_argument("--guid", help="导出单篇笔记内容（调试）")
    parser.add_argument("--images", choices=["file", "base64"], default=None,
                        help="图片处理策略 (默认 file，不指定时尊重配置文件)")
    parser.add_argument("--no-frontmatter", action="store_true",
                        help="不添加 YAML frontmatter")
    parser.add_argument("--flat", action="store_true",
                        help="不保持文件夹层级，扁平输出")
    parser.add_argument("--incremental", action="store_true",
                        help="增量导出：跳过上次导出后未修改的笔记")
    parser.add_argument("--workers", type=int, default=None,
                        help="并发导出线程数 (默认 4，1 = 串行)")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    return parser


def main(argv=None) -> int:
    # 强制 stdout/stderr 使用 UTF-8，避免 Windows 控制台中文乱码
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from exporter.config import load_config, merge_cli
    from exporter.app import WizNoteExporter

    config = load_config(args.config)
    config = merge_cli(config, args)

    # 自动查找数据目录（无需 --input）
    if args.find:
        from exporter.sources.discover import find_wiznote_dirs

        found = find_wiznote_dirs()
        if not found:
            print("未找到为知笔记数据目录，请使用 --input 手动指定。")
            return 1
        print("发现以下为知笔记数据目录:")
        for d in found:
            print(f"  {d}")
        return 0

    # webapi: 列出知识库（登录后）
    if args.list_kb:
        from exporter.sources.webapi.source import WebAPISource

        source = WebAPISource(args.username or "", args.password or "",
                              args.as_url or "https://as.wiz.cn")
        if not source.login():
            print("登录失败，请检查用户名和密码。", file=sys.stderr)
            return 1
        print("\n知识库列表:")
        for i, kb in enumerate(source.auth.get_kb_list(), 1):
            print(f"  {i}. {kb['name']}  ({kb['kbGuid']})")
        return 0

    errors = config.validate()
    if errors:
        for e in errors:
            print(f"配置错误: {e}", file=sys.stderr)
        return 1

    exporter = WizNoteExporter(config)

    if args.list:
        exporter.list_notes()
        return 0

    if args.guid:
        md = exporter.export_document(args.guid)
        if md is None:
            print(f"未找到笔记: {args.guid}", file=sys.stderr)
            return 1
        print(md)
        return 0

    stats = exporter.export_all()
    print(stats.summary())
    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
