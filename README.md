# 知迁 — 为知笔记导出工具

将为知笔记批量导出为 Markdown 文件，支持本地缓存数据源。保持文件夹结构、提取图片附件、生成 YAML 元数据，导出结果可直接导入 Obsidian / Logseq / Typora 等工具。

## 功能特性

- **本地缓存** — SQLite + `.ziw` ZIP 解析，自动发现数据目录
- **高质量转换** — HTML→Markdown 代码块语言标注、表格修复、列表修复、噪音清理
- **文件夹结构** — 保持原有层级，文件名 = 笔记标题
- **图片处理** — 提取到 `assets/` 目录（file 模式）或内嵌 base64
- **YAML 元数据** — 标题、创建/修改时间、标签、路径
- **自动查找** — 跨平台自动发现为知笔记数据目录
- **并发导出** — 线程数可配，限流线程安全
- **增量导出** — 跳过上次导出后未修改的笔记
- **断点续导** — 中断后可从上次位置继续
- **导出控制** — 开始 / 暂停 / 停止，进度实时显示
- **群组笔记** — 自动发现并导出
- **GUI 界面** — 深色主题，现代卡片式设计

## 安装

### 方式一：pip 安装（推荐）

```bash
pip install -e .
zhiqian --find          # 自动查找数据目录
zhiqian --help          # 查看帮助
```

### 方式二：虚拟环境

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 方式三：一键脚本

Windows 直接使用 `run.bat`（CLI）或 `gui.bat`（GUI），脚本已内置环境配置。

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# GUI 需要 tkinter
#   macOS (Homebrew):   brew install python-tk
#   Ubuntu/Debian:      sudo apt install python3-tk

chmod +x start.sh
./start.sh --find       # CLI
./start.sh --gui        # GUI
```

## 快速开始

```bash
# 自动查找为知笔记数据目录
zhiqian --find

# 列出全部笔记
zhiqian --input "C:\Users\xxx\Documents\My Knowledge" --list

# 导出到指定目录
zhiqian --input "C:\Users\xxx\Documents\My Knowledge" --output "D:\notes"
```

## GUI 使用

```bash
gui.bat
# 或预填目录
gui.bat --input "C:\Users\xxx\Documents\My Knowledge"
```

也可使用独立 exe：`release/ZhiQian.exe`（单文件，双击即用，无需 Python 环境）。

**本地模式**：自动查找或浏览选择目录 → 开始导出

## 配置文件

支持 JSON 配置文件，避免每次输入参数：

```bash
zhiqian --config config.json
```

配置示例（`config.example.json`）：

```json
{
    "source_dir": "C:\\Users\\yourname\\Documents\\My Knowledge",
    "output_dir": "D:\\notes_backup",
    "preserve_structure": true,
    "image_strategy": "file",
    "add_frontmatter": true,
    "max_workers": 4
}
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config` | JSON 配置文件路径 | — |
| `--input` | 为知笔记本地数据目录 | — |
| `--output` | 导出输出目录 | `./notes` |
| `--find` | 自动查找数据目录 | — |
| `--list` | 仅列出笔记，不导出 | — |
| `--guid` | 导出单篇笔记（调试用） | — |
| `--images` | `file`（提取为文件）/ `base64`（内嵌） | 配置文件值 |
| `--workers` | 并发线程数 | 4 |
| `--incremental` | 增量导出，跳过未修改笔记 | — |
| `--resume` | 断点续导，跳过已导出笔记 | — |
| `--no-frontmatter` | 不生成 YAML 元数据 | — |
| `--flat` | 扁平输出，不保持层级 | — |
| `-v` | 输出调试日志 | — |

## 输出结构

```
notes/
├── 个人笔记/                       # 数据源名即顶级目录
│   ├── 技术/
│   │   ├── React 指南.md
│   │   └── assets/                 # 图片与附件
│   └── 生活/
│       └── 日记.md
├── 我的团队/                       # 群组笔记
│   └── 团队笔记.md
└── _metadata/
    ├── index.json                  # 笔记索引（增量比对依据）
    └── report.json                 # 失败明细
```

## 项目结构

```
zhiqian/
├── exporter/                       # 主包
│   ├── cli.py                      #   CLI 入口
│   ├── config.py                   #   配置管理
│   ├── models.py                   #   数据模型
│   ├── app.py                      #   导出编排
│   ├── gui.py                      #   GUI 界面
│   ├── sources/                    #   数据源适配器
│   │   ├── local.py                #     本地缓存（SQLite + .ziw）
│   │   └── discover.py             #     自动查找数据目录
│   ├── pipeline/                   #   处理管线
│   │   ├── preprocessor.py         #     HTML 清洗
│   │   ├── converter.py            #     HTML→Markdown 转换
│   │   ├── images.py               #     图片提取策略
│   │   └── pipeline.py             #     管线编排
│   └── storage/manager.py          #   输出与索引管理
├── tests/                          # 测试套件（67 用例）
├── scripts/gui_launcher.py         # PyInstaller 打包入口
├── release/ZhiQian.exe             # 独立 exe（免 Python 运行）
├── run.bat / gui.bat               # Windows 一键启动
├── start.sh                        # macOS / Linux 启动脚本
├── config.example.json             # 配置示例
├── pyproject.toml                  # 项目元数据与依赖
└── LICENSE                         # Apache-2.0
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
python -m pytest

# 打包独立 exe
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name ZhiQian \
  --paths . --collect-all customtkinter \
  --workpath build --distpath dist \
  scripts/gui_launcher.py
```

## 已知限制

- **本地模式**：仅导出已下载到本地的笔记，云端未下载的会跳过并记录
- **复杂 HTML**：微信文章等转换后可能有少量格式噪音，已做自动清理
- **增量导出**：同一标题不同 GUID 的笔记会自动追加 GUID 后缀以避免冲突

## 许可证

[Apache-2.0](LICENSE)

## 联系

sujx@live.cn
