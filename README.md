# 知迁 — 为知笔记导出工具

将为知笔记（本地缓存 / 在线 API）批量导出为 Markdown 文件，保持文件夹结构、提取图片附件、生成 YAML 元数据，兼容 Obsidian / Logseq / Typora 等工具。

## 功能特性

- ✅ 本地缓存导出（SQLite + `.ziw` ZIP 解析，多编码兼容）
- ✅ 在线 API 导出（登录 → 知识库 → 文件夹选择，自动重试）
- ✅ 保持文件夹层级结构，文件名 = 笔记标题
- ✅ 图片提取到 `assets/`（file 模式）或内嵌 base64
- ✅ YAML frontmatter（标题 / 时间 / 标签 / 路径）
- ✅ 自动查找为知笔记数据目录（`--find` / GUI 按钮）
- ✅ 并发导出（线程数可配，webapi 默认 2，限流线程安全）
- ✅ 导出控制：开始 / 暂停（继续）/ 停止
- ✅ 增量导出：跳过上次导出后未修改的笔记
- ✅ 群组笔记自动发现
- ✅ GUI 界面（深色主题，CustomTkinter，作者 sujx@live.cn）
- ✅ HTML→Markdown 高质量转换（代码块语言 / 表格 / 列表修复 / 噪音清理）

## 安装

```bash
# 1. 创建虚拟环境（CLI）
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 2. GUI 环境（需带 tkinter 的 Python，如官方 python.org 安装版）
"C:\Program Files\Python312\python.exe" -m venv .gui-venv
.gui-venv\Scripts\pip install -r requirements.txt
```

或使用 pyproject.toml 标准安装（可选，自动注册 `zhiqian` 命令）：

```bash
pip install -e .
zhiqian --find
```

或直接使用项目内置脚本：`run.bat`（CLI）/ `gui.bat`（GUI），二者已配置好环境。

## 跨平台安装（macOS / Ubuntu）

核心程序完全跨平台（无 Windows 特定代码），macOS / Ubuntu 安装方式：

```bash
# 1. 准备 Python 环境（CLI 无需 tkinter；GUI 需要）
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. GUI 额外依赖 tkinter
#    macOS (Homebrew python):  brew install python-tk
#    macOS (python.org 官方版): 自带 tkinter，无需安装
#    Ubuntu / Debian:          sudo apt install python3-tk

# 3. 使用 start.sh（CLI 与 GUI 统一入口）
chmod +x start.sh
./start.sh --find                                  # 自动查找数据目录
./start.sh --source local --input ~/Documents/My\ Knowledge --output ~/notes
./start.sh --gui                                   # 启动 GUI
```

> 或 `pip install -e .` 注册 `zhiqian` 命令，与 `start.sh` 等价。
> 自动查找目录已适配各平台（macOS 含 `~/Library/Application Support`，Linux 含 `~/.wiznote`）。

## 快速开始

```bash
# 1. 自动查找数据目录
run.bat --find

# 2. 列出全部笔记
run.bat --source local --input "C:\Users\xxx\Documents\My Knowledge" --list

# 3. 完整导出
run.bat --source local --input "C:\Users\xxx\Documents\My Knowledge" --output "D:\notes"
```

## GUI 使用

```bash
gui.bat
# 或预填目录
gui.bat --input "C:\Users\xxx\Documents\My Knowledge"
```

**独立 exe（免 Python 环境）**：`release/ZhiQian.exe`（单文件，双击即用）。

- **本地模式**：自动查找 / 浏览选择目录 → 开始导出
- **在线 API 模式**：填账号密码 → 登录 → 选择知识库 → 勾选文件夹 → 导出
- **导出控制**：开始 / 暂停（继续）/ 停止，进度实时显示，支持增量导出

## 在线 API 模式（CLI）

```bash
# 列出知识库（获取 GUID）
run.bat --source webapi --username 账号 --password 密码 --list-kb

# 导出指定知识库的全部笔记
run.bat --source webapi --username 账号 --password 密码 --kb <GUID> --output D:\notes

# 导出指定文件夹
run.bat --source webapi --username 账号 --password 密码 --kb <GUID> --folders "/技术/" "/生活/" --output D:\notes
```

## 参数说明

| 参数 | 说明 | 默认 |
|------|------|------|
| `--source` | `local`（本地）/ `webapi`（在线） | `local` |
| `--config` | JSON 配置文件路径（如 config.example.json） | - |
| `--input` | 为知笔记本地数据目录 | - |
| `--output` | 导出目录 | `./notes` |
| `--list` | 仅列出笔记 | - |
| `--find` | 自动查找数据目录 | - |
| `--guid` | 导出单篇（调试） | - |
| `--images` | `file`（提取）/ `base64`（内嵌），未指定时尊重配置文件 | 配置文件值 |
| `--workers` | 并发线程数（webapi 未指定时默认 2） | 4 |
| `--incremental` | 增量导出：跳过上次导出后未修改的笔记 | - |
| `--username` | 在线模式账号 | - |
| `--password` | 在线模式密码 | - |
| `--as-url` | 在线模式 AS 服务器地址 | `https://as.wiz.cn` |
| `--kb` | 在线模式知识库 GUID | 个人库 |
| `--folders` | 在线模式限定文件夹（多值） | 全部 |
| `--no-frontmatter` | 不生成 YAML 元数据 | - |
| `--flat` | 扁平输出（不保持层级） | - |
| `-v` | 调试日志 | - |

## 输出结构

```
notes/
├── 个人笔记/                   # 数据源名（个人库 / 群组名）即顶级目录
│   ├── 技术/
│   │   ├── React 指南.md
│   │   └── assets/          # 图片与附件
│   └── 生活/
├── 我的团队/                   # 群组笔记
│   └── 团队笔记.md
└── _metadata/
    ├── index.json           # 笔记索引（增量比对依据）
    └── report.json          # 失败明细
```

## 已知限制

- 本地模式：仅导出已下载到本地的笔记（云端未下载的会跳过并记录）
- 在线模式：附件下载接口暂未实现；官方 API 偶发 503 / 参数错误（已内置指数退避重试，最多 4 次）
- 复杂 HTML（微信文章等）转换后可能有少量格式噪音，已做自动清理
- 增量导出仅对未修改过的笔记跳过；同一标题不同 GUID 的笔记会自动追加 GUID 后缀

## 项目结构

```
zhiqian/
├── exporter/                    # 主包源码
│   ├── cli.py / config.py / models.py / app.py   # 入口 / 配置 / 模型 / 编排
│   ├── sources/                 # 数据源（适配器模式）
│   │   ├── local.py             #   本地缓存
│   │   ├── discover.py          #   自动查找目录
│   │   └── webapi/              #   在线 API（auth/client/source）
│   ├── pipeline/                # 处理管线
│   │   ├── preprocessor.py      #   HTML 清洗
│   │   ├── converter.py         #   HTML→MD + 后处理
│   │   ├── images.py            #   图片提取
│   │   └── pipeline.py          #   管线编排
│   ├── storage/manager.py       # 输出管理
│   └── gui.py                   # 深色主题 GUI
├── tests/                       # pytest 测试套件（66 用例）
├── scripts/gui_launcher.py      # PyInstaller 打包入口
├── release/ZhiQian.exe          # 发布产物（免 Python 双击运行）
├── docs/                        # 文档
├── .github/workflows/ci.yml     # GitHub Actions CI
├── gui.bat / run.bat            # Windows 一键启动脚本
├── start.sh                     # macOS / Linux 启动脚本
├── pyproject.toml               # 项目元数据 / 依赖 / zhiqian 入口
├── pytest.ini                   # pytest 配置
├── config.example.json          # 配置示例
└── LICENSE                      # MIT
```

## 开发

```bash
# 测试
python -m pytest

# 打包 exe（需先安装 pyinstaller）
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name ZhiQian \
  --paths . --collect-all customtkinter \
  --workpath build --distpath dist \
  scripts/gui_launcher.py
# 产物: dist/ZhiQian.exe → 放入 release/
```

## 联系

作者：sujx@live.cn（程序界面底部亦显示此邮箱）

## 免责声明

本工具仅供个人笔记迁移使用，请遵守为知笔记服务条款。基于第三方 API 实现，接口变动可能导致兼容问题。
