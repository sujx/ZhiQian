"""为知笔记导出: Markdown 文件导出工具

用法示例:
    python -m exporter --source local --input <为知数据目录> --list
    python -m exporter --source local --input <为知数据目录> --output ./notes
"""

from exporter.cli import main

if __name__ == "__main__":
    main()
