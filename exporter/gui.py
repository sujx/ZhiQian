"""为知笔记导出工具 — CustomTkinter GUI（现代卡片式设计）

运行: python -m exporter.gui  (或 gui.bat)
说明: 需基于带 tkinter 的 Python（项目内 .gui-venv 已就绪）
"""

from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

logger = logging.getLogger("exporter.gui")

# ---------- 设计令牌（现代深色主题） ----------

COLORS = {
    "bg": "#16161E",           # 窗口背景
    "card": "#1F1F2B",         # 卡片背景
    "card2": "#262635",        # 次级表面（输入框/卡片头）
    "border": "#34344A",       # 边框
    "accent": "#6C5CE7",       # 品牌紫
    "accent_hover": "#5A4BD1",
    "accent_soft": "#2A2740",  # 紫色系浅底
    "success": "#2ECC71",
    "danger": "#E74C3C",
    "text": "#E8E8F0",         # 主文字
    "text2": "#9A9AB0",        # 次要文字
    "text3": "#6E6E8A",        # 弱文字
}

FONT_FAMILY = "Microsoft YaHei UI"


def _font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size,
                       weight="bold" if weight == "bold" else "normal")


class LogQueueHandler(logging.Handler):
    """把 logging 记录转发到线程安全队列（主线程统一刷新 UI）"""

    def __init__(self, log_queue: "queue.Queue"):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.log_queue.put(("log", self.format(record)))
        except Exception:  # noqa: BLE001
            pass


class MetricCard(ctk.CTkFrame):
    """统计指标卡：大数字 + 标签 + 颜色"""

    def __init__(self, master, label: str, color: str, value: int = 0):
        super().__init__(master, fg_color=COLORS["card2"],
                         corner_radius=12, border_width=0)
        self._value = value
        ctk.CTkLabel(self, text=label, font=_font(12),
                     text_color=COLORS["text2"]).pack(padx=14, pady=(10, 0), anchor="w")
        self.value_label = ctk.CTkLabel(
            self, text=f"{value}", font=_font(24, "bold"), text_color=color)
        self.value_label.pack(padx=14, pady=(0, 10), anchor="w")

    def set(self, value: int) -> None:
        self._value = value
        self.value_label.configure(text=f"{value}")


class ExporterGUI(ctk.CTk):
    """主窗口（现代卡片式布局）"""

    WIDTH, HEIGHT = 860, 600

    def __init__(self, preset_input: str = "") -> None:
        super().__init__()
        self.title("知迁 — 为知笔记导出工具")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(760, 540)

        # 线程通信
        self.progress_queue: "queue.Queue" = queue.Queue()
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker: Optional[threading.Thread] = None

        self._build_ui()
        if preset_input:
            self.input_var.set(preset_input)

        # 日志 → 队列 → 面板
        self.log_handler = LogQueueHandler(self.progress_queue)
        self.log_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(self.log_handler)

        self.after(100, self._poll_queue)

    # ---------- UI 构建 ----------

    def _build_ui(self) -> None:
        self.configure(fg_color=COLORS["bg"])
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_config_panel()
        self._build_right_panel()
        self._build_footer()

    def _build_footer(self) -> None:
        """底部信息栏：作者联系方式"""
        footer = ctk.CTkFrame(self, fg_color=COLORS["card2"], corner_radius=10)
        footer.grid(row=2, column=0, columnspan=2, padx=20, pady=(0, 8), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            footer, text="sujx@live.cn", font=_font(11),
            text_color=COLORS["text3"]).grid(row=0, column=0, pady=4)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2,
                    padx=20, pady=(18, 10), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        # 品牌标识
        logo = ctk.CTkFrame(header, fg_color=COLORS["accent_soft"],
                            corner_radius=10, width=42, height=42)
        logo.grid(row=0, column=0, padx=(0, 12))
        logo.grid_propagate(False)
        ctk.CTkLabel(logo, text="◆", font=_font(20, "bold"),
                     text_color=COLORS["accent"]).place(relx=0.5, rely=0.5, anchor="center")

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(title_box, text="知迁", font=_font(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w")
        ctk.CTkLabel(title_box, text="为知笔记导出工具",
                     font=_font(12), text_color=COLORS["text2"]).pack(anchor="w")

    def _build_config_panel(self) -> None:
        panel = ctk.CTkFrame(self, fg_color=COLORS["card"],
                             corner_radius=16, width=300)
        panel.grid(row=1, column=0, padx=(20, 10), pady=(0, 20), sticky="nsw")
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="导出配置", font=_font(14, "bold"),
                     text_color=COLORS["text"]).grid(
            row=0, column=0, padx=20, pady=(18, 4), sticky="w")
        ctk.CTkLabel(panel, text="SOURCE & OPTIONS", font=_font(10),
                     text_color=COLORS["text3"]).grid(
            row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        # 数据源类型
        ctk.CTkLabel(panel, text="数据源类型", font=_font(12),
                     text_color=COLORS["text2"]).grid(
            row=2, column=0, padx=20, pady=(8, 4), sticky="w")
        self.source_menu = ctk.CTkOptionMenu(
            panel, values=["本地缓存 (local)", "在线 API (webapi)"],
            command=self._on_source_change, width=260, height=34,
            fg_color=COLORS["card2"], button_color=COLORS["card2"],
            button_hover_color=COLORS["border"], text_color=COLORS["text"],
            dropdown_fg_color=COLORS["card2"], corner_radius=10)
        self.source_menu.grid(row=3, column=0, padx=20, sticky="ew")

        # webapi 账号（本地模式隐藏）
        self.webapi_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.webapi_frame.grid(row=4, column=0, padx=20, pady=(6, 0), sticky="ew")
        self.webapi_frame.grid_columnconfigure(0, weight=1)
        self.user_entry = ctk.CTkEntry(
            self.webapi_frame, placeholder_text="用户名/邮箱", height=32,
            fg_color=COLORS["card2"], border_color=COLORS["border"],
            text_color=COLORS["text"], corner_radius=10)
        self.user_entry.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.pass_entry = ctk.CTkEntry(
            self.webapi_frame, placeholder_text="密码", show="*", height=32,
            fg_color=COLORS["card2"], border_color=COLORS["border"],
            text_color=COLORS["text"], corner_radius=10)
        self.pass_entry.grid(row=1, column=0, sticky="ew")
        self.login_btn = ctk.CTkButton(
            self.webapi_frame, text="登录", width=56, height=32, corner_radius=10,
            font=_font(12), text_color="#FFFFFF",
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self._login_webapi)
        self.login_btn.grid(row=1, column=1, padx=(8, 0))

        # 云端知识库选择（登录后显示）
        self.kb_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.kb_frame.grid(row=11, column=0, padx=20, pady=(10, 4), sticky="ew")
        self.kb_frame.grid_columnconfigure(0, weight=1)
        self.kb_menu = ctk.CTkOptionMenu(
            self.kb_frame, values=["-- 登录后选择知识库 --"], height=34,
            command=self._on_kb_change, width=260,
            fg_color=COLORS["card2"], button_color=COLORS["card2"],
            button_hover_color=COLORS["border"], text_color=COLORS["text"],
            dropdown_fg_color=COLORS["card2"], corner_radius=10)
        self.kb_menu.grid(row=0, column=0, sticky="ew")

        # 云端文件夹多选（登录后显示）
        self.folder_frame = ctk.CTkFrame(panel, fg_color=COLORS["card2"], corner_radius=10)
        self.folder_frame.grid(row=12, column=0, padx=20, pady=(4, 8), sticky="ew")
        self.folder_frame.grid_columnconfigure(0, weight=1)
        self.folder_box = ctk.CTkScrollableFrame(
            self.folder_frame, height=110, fg_color="transparent")
        self.folder_box.grid(row=0, column=0, padx=(10, 6), pady=(8, 4), sticky="ew")
        self.folder_box.grid_columnconfigure(0, weight=1)
        self.folder_btn_row = ctk.CTkFrame(self.folder_frame, fg_color="transparent")
        self.folder_btn_row.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
        self.sel_all_btn = ctk.CTkButton(
            self.folder_btn_row, text="全选", width=48, height=26, corner_radius=8,
            font=_font(11), fg_color=COLORS["card"], text_color=COLORS["text"],
            hover_color=COLORS["border"], command=self._select_all_folders)
        self.sel_all_btn.pack(side="left", padx=(0, 6))
        self.sel_none_btn = ctk.CTkButton(
            self.folder_btn_row, text="清空", width=48, height=26, corner_radius=8,
            font=_font(11), fg_color=COLORS["card"], text_color=COLORS["text"],
            hover_color=COLORS["border"], command=self._clear_folders)
        self.sel_none_btn.pack(side="left")

        self.folder_vars: dict = {}
        self._webapi_source = None  # 登录后的 WebAPISource 实例
        self._kb_guid_map: dict = {}  # 知识库名 -> GUID

        # 数据目录
        input_label = ctk.CTkLabel(panel, text="为知笔记数据目录", font=_font(12),
                                   text_color=COLORS["text2"])
        input_label.grid(row=5, column=0, padx=20, pady=(12, 4), sticky="w")
        row = self._dir_row(panel, 6)
        self.input_var = ctk.StringVar()
        row["entry"].configure(textvariable=self.input_var,
                               placeholder_text="如 D:\\My Knowledge")
        row["btn"].configure(command=self._pick_input)
        # 自动查找按钮
        self.auto_find_btn = ctk.CTkButton(
            row["frame"], text="自动查找", width=56, height=34, corner_radius=10,
            font=_font(12), text_color=COLORS["text"],
            fg_color=COLORS["accent_soft"], hover_color=COLORS["border"],
            command=self._auto_find_input)
        self.auto_find_btn.grid(row=0, column=2, padx=(6, 0))

        # 输出目录
        output_label = ctk.CTkLabel(panel, text="导出输出目录", font=_font(12),
                                    text_color=COLORS["text2"])
        output_label.grid(row=7, column=0, padx=20, pady=(10, 4), sticky="w")
        row2 = self._dir_row(panel, 8)
        self.output_var = ctk.StringVar(value="./notes_gui")
        row2["entry"].configure(textvariable=self.output_var)
        row2["btn"].configure(command=self._pick_output)

        # 本地模式才显示的控件（webapi 模式隐藏）
        self._local_only = [input_label, output_label, row["frame"], row2["frame"]]

        # 选项
        opt = ctk.CTkFrame(panel, fg_color=COLORS["card2"], corner_radius=10)
        opt.grid(row=9, column=0, padx=20, pady=(14, 8), sticky="ew")
        opt.grid_columnconfigure(1, weight=1)
        self.struct_var = ctk.BooleanVar(value=True)
        self.front_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt, text="保持文件夹结构", variable=self.struct_var,
                        font=_font(12), text_color=COLORS["text"],
                        fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                        checkmark_color="#FFFFFF").grid(
            row=0, column=0, columnspan=2, padx=14, pady=(12, 6), sticky="w")
        ctk.CTkCheckBox(opt, text="添加 YAML 元数据", variable=self.front_var,
                        font=_font(12), text_color=COLORS["text"],
                        fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                        checkmark_color="#FFFFFF").grid(
            row=1, column=0, columnspan=2, padx=14, pady=(0, 6), sticky="w")
        self.incremental_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opt, text="增量导出（跳过未修改）", variable=self.incremental_var,
                        font=_font(12), text_color=COLORS["text"],
                        fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                        checkmark_color="#FFFFFF").grid(
            row=2, column=0, columnspan=2, padx=14, pady=(0, 6), sticky="w")
        ctk.CTkLabel(opt, text="图片策略", font=_font(12),
                     text_color=COLORS["text2"]).grid(
            row=3, column=0, padx=(14, 8), pady=(6, 12), sticky="w")
        self.image_menu = ctk.CTkOptionMenu(
            opt, values=["提取为文件 (file)", "内嵌 base64"], width=130, height=30,
            fg_color=COLORS["card"], button_color=COLORS["card"],
            button_hover_color=COLORS["border"], text_color=COLORS["text"],
            dropdown_fg_color=COLORS["card"], corner_radius=8)
        self.image_menu.grid(row=3, column=1, padx=(0, 14), pady=(6, 12), sticky="e")

        # 并发线程数
        thread_row = ctk.CTkFrame(panel, fg_color=COLORS["card2"], corner_radius=10)
        thread_row.grid(row=13, column=0, padx=20, pady=(8, 4), sticky="ew")
        thread_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(thread_row, text="并发线程数", font=_font(12),
                     text_color=COLORS["text2"]).grid(
            row=0, column=0, padx=(14, 8), pady=8, sticky="w")
        self.workers_var = ctk.StringVar(value="4")
        self._workers_edited = False  # 用户手动改过线程数则不再自动调整
        self.workers_entry = ctk.CTkEntry(
            thread_row, textvariable=self.workers_var, width=56, height=30,
            fg_color=COLORS["card"], border_color=COLORS["border"],
            text_color=COLORS["text"], corner_radius=8, justify="center")
        self.workers_entry.grid(row=0, column=1, padx=(0, 8), pady=8, sticky="e")
        self.workers_entry.bind(
            "<Key>", lambda _e: setattr(self, "_workers_edited", True))
        self.workers_entry.bind(
            "<<Paste>>", lambda _e: setattr(self, "_workers_edited", True))
        ctk.CTkLabel(thread_row, text="(1 = 串行)", font=_font(11),
                     text_color=COLORS["text3"]).grid(
            row=0, column=2, padx=(0, 14), pady=8, sticky="w")

        # 初始状态：本地模式（所有依赖控件定义完成后调用）
        self._on_source_change("本地缓存 (local)")

    def _dir_row(self, master, row: int) -> dict:
        """生成 [输入框 + 浏览按钮] 一行"""
        frame = ctk.CTkFrame(master, fg_color="transparent")
        frame.grid(row=row, column=0, padx=20, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        entry = ctk.CTkEntry(
            frame, height=34, fg_color=COLORS["card2"],
            border_color=COLORS["border"], text_color=COLORS["text"],
            corner_radius=10)
        entry.grid(row=0, column=0, sticky="ew")
        btn = ctk.CTkButton(
            frame, text="浏览", width=56, height=34, corner_radius=10,
            font=_font(12), text_color=COLORS["text"],
            fg_color=COLORS["card2"], hover_color=COLORS["border"])
        btn.grid(row=0, column=1, padx=(8, 0))
        return {"frame": frame, "entry": entry, "btn": btn}

    def _build_right_panel(self) -> None:
        right = ctk.CTkFrame(self, fg_color=COLORS["card"],
                             corner_radius=16)
        right.grid(row=1, column=1, padx=(10, 20), pady=(0, 20), sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        # 日志行扩展，进度区按内容自适应（防止进度区拉伸挤压日志）
        right.grid_rowconfigure(3, weight=1)

        # 统计卡片
        ctk.CTkLabel(right, text="导出统计", font=_font(14, "bold"),
                     text_color=COLORS["text"]).grid(
            row=0, column=0, padx=20, pady=(18, 8), sticky="w")
        stats_row = ctk.CTkFrame(right, fg_color="transparent")
        stats_row.grid(row=1, column=0, padx=20, sticky="ew")
        for i in range(3):
            stats_row.grid_columnconfigure(i, weight=1)
        self.metric_total = MetricCard(stats_row, "总笔记数", COLORS["text"])
        self.metric_total.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.metric_ok = MetricCard(stats_row, "成功导出", COLORS["success"])
        self.metric_ok.grid(row=0, column=1, padx=8, sticky="ew")
        self.metric_fail = MetricCard(stats_row, "失败数量", COLORS["danger"])
        self.metric_fail.grid(row=0, column=2, padx=(8, 0), sticky="ew")

        # 进度区（按内容高度，不随窗口拉伸）
        prog = ctk.CTkFrame(right, fg_color=COLORS["card2"], corner_radius=12)
        prog.grid(row=2, column=0, padx=20, pady=(14, 6), sticky="ew")
        prog.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(
            prog, height=12, corner_radius=6,
            fg_color=COLORS["border"], progress_color=COLORS["accent"])
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, padx=(16, 8), pady=(14, 2), sticky="ew")
        self.percent_label = ctk.CTkLabel(
            prog, text="0.0%", font=_font(14, "bold"), text_color=COLORS["text"], width=70)
        self.percent_label.grid(row=0, column=1, padx=(0, 16), pady=(14, 2))

        self.status_label = ctk.CTkLabel(
            prog, text="就绪 — 请选择数据目录", font=_font(12),
            text_color=COLORS["text2"], anchor="w")
        self.status_label.grid(row=1, column=0, columnspan=2,
                               padx=16, pady=(0, 10), sticky="ew")

        # 控制按钮行（进度条正下方：开始 / 暂停 / 停止）
        ctrl = ctk.CTkFrame(prog, fg_color="transparent")
        ctrl.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="ew")
        for i in range(3):
            ctrl.grid_columnconfigure(i, weight=1)

        self.start_btn = ctk.CTkButton(
            ctrl, text="✦ 开始", height=40, corner_radius=10,
            font=_font(14, "bold"), text_color="#FFFFFF",
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self._start_export)
        self.start_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.pause_btn = ctk.CTkButton(
            ctrl, text="⏸ 暂停", height=40, corner_radius=10,
            font=_font(14), text_color=COLORS["text"],
            fg_color=COLORS["card"], hover_color=COLORS["border"],
            command=self._toggle_pause, state="disabled")
        self.pause_btn.grid(row=0, column=1, padx=5, sticky="ew")

        self.stop_btn = ctk.CTkButton(
            ctrl, text="⏹ 停止", height=40, corner_radius=10,
            font=_font(14), text_color="#FFFFFF",
            fg_color=COLORS["danger"], hover_color="#C0392B",
            command=self._cancel_export, state="disabled")
        self.stop_btn.grid(row=0, column=2, padx=(5, 0), sticky="ew")

        # 日志面板
        self.log_text = ctk.CTkTextbox(
            right, height=220, state="disabled",
            fg_color=COLORS["card2"], border_width=0, corner_radius=12,
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=COLORS["text"])
        self.log_text.grid(row=3, column=0, padx=20, pady=(6, 20), sticky="nsew")

    # ---------- 交互 ----------

    @staticmethod
    def _set_visible(widget, visible: bool) -> None:
        """grid 控件显隐切换"""
        if visible:
            widget.grid()
        else:
            widget.grid_remove()

    def _on_source_change(self, choice: str) -> None:
        """本地缓存：显示目录选择，隐藏账号；在线 API：相反"""
        is_webapi = choice.startswith("在线")
        logged_in = self._webapi_source is not None
        self._set_visible(self.webapi_frame, is_webapi)
        self._set_visible(self.kb_frame, is_webapi and logged_in)
        self._set_visible(self.folder_frame, is_webapi and logged_in)
        for w in self._local_only:
            self._set_visible(w, not is_webapi)
        # webapi 默认并发 2（用户未手动修改时自动调整）
        if not self._workers_edited:
            self.workers_var.set("2" if is_webapi else "4")

    # ---------- webapi：登录 / 知识库 / 文件夹 ----------

    def _login_webapi(self) -> None:
        """登录为知笔记（后台线程），成功后加载知识库列表"""
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not username or not password:
            self._log("[错误] 请输入用户名和密码")
            self.status_label.configure(text="请填写账号密码", text_color=COLORS["danger"])
            return

        self.status_label.configure(text="正在登录...")
        self.login_btn.configure(state="disabled")
        self.update_idletasks()

        import os
        as_url = os.environ.get("WIZ_AS_URL", "https://as.wiz.cn")

        def _do_login():
            from exporter.sources.webapi.source import WebAPISource
            source = WebAPISource(username, password, as_url)
            try:
                ok = source.login()
            except Exception as e:  # noqa: BLE001
                ok = False
                self.progress_queue.put(("log", f"[错误] 登录异常: {e}"))
            self.progress_queue.put(("login_result", (source, ok)))

        threading.Thread(target=_do_login, daemon=True).start()

    def _handle_login_result(self, source, ok: bool) -> None:
        """在主线程处理登录结果"""
        username = self.user_entry.get().strip()
        self.login_btn.configure(state="normal")
        if not ok or source is None:
            self.status_label.configure(text="登录失败，请检查账号密码",
                                        text_color=COLORS["danger"])
            self._log("[错误] 登录失败（网络或账号问题）")
            return

        self._webapi_source = source
        self._kb_guid_map = {kb["name"]: kb["kbGuid"]
                             for kb in source.auth.get_kb_list()}
        self.kb_menu.configure(values=list(self._kb_guid_map.keys()))
        if self._kb_guid_map:
            first = next(iter(self._kb_guid_map))
            self.kb_menu.set(first)
        self._set_visible(self.kb_frame, True)
        self._on_kb_change(self.kb_menu.get())
        self.status_label.configure(text=f"登录成功: {username}",
                                    text_color=COLORS["success"])
        self._log(f"[提示] 登录成功，{len(self._kb_guid_map)} 个知识库已加载")

    def _on_kb_change(self, kb_name: str) -> None:
        """切换知识库 → 加载文件夹列表"""
        if self._webapi_source is None or not kb_name:
            return
        self._webapi_source.switch_source(kb_name)
        folders = self._webapi_source.get_folder_list()
        self._render_folders(folders)
        self._set_visible(self.folder_frame, True)
        self._log(f"[提示] 知识库「{kb_name}」: {len(folders)} 个文件夹")

    def _render_folders(self, folders: list) -> None:
        """渲染文件夹复选框列表"""
        for w in self.folder_box.winfo_children():
            w.destroy()
        self.folder_vars = {}
        for folder in folders:
            var = ctk.BooleanVar(value=False)
            self.folder_vars[folder] = var
            ctk.CTkCheckBox(
                self.folder_box, text=folder, variable=var,
                font=_font(11), text_color=COLORS["text"],
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                checkmark_color="#FFFFFF").pack(anchor="w", pady=2)

    def _select_all_folders(self) -> None:
        for var in self.folder_vars.values():
            var.set(True)

    def _clear_folders(self) -> None:
        for var in self.folder_vars.values():
            var.set(False)

    def _selected_kb_guid(self) -> str:
        return self._kb_guid_map.get(self.kb_menu.get(), "")

    def _selected_folders(self) -> list:
        return [f for f, var in self.folder_vars.items() if var.get()]

    def _pick_input(self) -> None:
        d = filedialog.askdirectory(title="选择为知笔记数据目录")
        if d:
            self.input_var.set(d)

    def _auto_find_input(self) -> None:
        """自动扫描常见位置查找为知笔记数据目录"""
        from exporter.sources.discover import find_wiznote_dirs

        self.status_label.configure(text="正在自动查找为知笔记目录...")
        self.update_idletasks()
        found = find_wiznote_dirs()
        if not found:
            self.status_label.configure(
                text="未找到为知笔记数据目录，请手动选择",
                text_color=COLORS["danger"])
            self._log("[提示] 自动查找未命中，请在常见位置手动选择目录")
            return
        self.input_var.set(found[0])
        if len(found) > 1:
            self.status_label.configure(
                text=f"发现 {len(found)} 个数据目录，已填入第一个")
            self._log(f"[提示] 自动发现 {len(found)} 个目录: {found}")
        else:
            self.status_label.configure(text=f"已自动找到: {found[0]}")
            self._log(f"[提示] 自动发现数据目录: {found[0]}")

    def _pick_output(self) -> None:
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_var.set(d)

    def _log(self, msg: str, color: str = "default") -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ---------- 导出流程 ----------

    def _workers_value(self) -> int:
        """读取并发线程数输入，非法时回退默认 4"""
        try:
            value = int(self.workers_var.get().strip() or "4")
            return value if 1 <= value <= 32 else 4
        except ValueError:
            return 4

    def _start_export(self) -> None:
        output_dir = self.output_var.get().strip()
        is_webapi = self.source_menu.get().startswith("在线")

        from exporter.config import ExportConfig
        from exporter.app import WizNoteExporter

        if is_webapi:
            # 在线 API：需先登录并选择知识库/文件夹
            if self._webapi_source is None:
                self._log("[错误] 请先登录为知笔记账号")
                self.status_label.configure(text="请先登录", text_color=COLORS["danger"])
                return
            kb_guid = self._selected_kb_guid()
            if not kb_guid:
                self._log("[错误] 请选择知识库")
                return
            folders = self._selected_folders()
            if not folders:
                self._log("[错误] 请勾选要导出的文件夹（或点全选）")
                return
            cfg = ExportConfig(
                source_type="webapi",
                username=self.user_entry.get().strip(),
                password=self.pass_entry.get(),
                kb_guid=kb_guid,
                include_folders=folders,
                output_dir=output_dir,
                preserve_structure=self.struct_var.get(),
                add_frontmatter=self.front_var.get(),
                image_strategy=("file" if self.image_menu.get().startswith("提取")
                                else "base64"),
                incremental=self.incremental_var.get(),
                max_workers=self._workers_value(),
            )
        else:
            source_dir = self.input_var.get().strip()
            if not source_dir:
                self._log("[错误] 请选择为知笔记数据目录")
                self.status_label.configure(text="请选择数据目录", text_color=COLORS["danger"])
                return
            cfg = ExportConfig(
                source_type="local",
                source_dir=source_dir,
                output_dir=output_dir,
                preserve_structure=self.struct_var.get(),
                add_frontmatter=self.front_var.get(),
                image_strategy=("file" if self.image_menu.get().startswith("提取")
                                else "base64"),
                incremental=self.incremental_var.get(),
                max_workers=self._workers_value(),
            )

        exporter = WizNoteExporter(cfg)

        # 状态：开始导出
        self.cancel_event.clear()
        self.pause_event.clear()
        self._set_running(True)
        self.progress_bar.set(0)
        self.status_label.configure(text="正在导出...", text_color=COLORS["text2"])

        def worker() -> None:
            try:
                stats = exporter.export_all(
                    progress_callback=self._progress,
                    cancel_event=self.cancel_event,
                    pause_event=self.pause_event,
                )
                self.progress_queue.put(("done", stats))
            except Exception as e:  # noqa: BLE001
                self.progress_queue.put(("error", str(e)))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _progress(self, done: int, total: int, title: str,
                  ok: int, fail: int) -> None:
        self.progress_queue.put(("progress", done, total, title, ok, fail))

    # ---------- 三按钮控制 ----------

    def _set_running(self, running: bool) -> None:
        """运行状态切换：开始/暂停/停止按钮可用性"""
        self.start_btn.configure(state="disabled" if running else "normal")
        self.pause_btn.configure(state="normal" if running else "disabled")
        self.stop_btn.configure(state="normal" if running else "disabled")
        if not running:
            self.pause_btn.configure(text="⏸ 暂停")

    def _toggle_pause(self) -> None:
        """暂停 ↔ 继续"""
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.configure(text="⏸ 暂停")
            self.status_label.configure(text="继续导出...", text_color=COLORS["text2"])
            self._log("[提示] 继续导出")
        else:
            self.pause_event.set()
            self.pause_btn.configure(text="▶ 继续")
            self.status_label.configure(text="已暂停（点击继续恢复）",
                                        text_color="#FAC775")
            self._log("[提示] 已暂停，处理完在途笔记后挂起")

    def _cancel_export(self) -> None:
        """停止导出"""
        self.cancel_event.set()
        self.pause_event.clear()  # 解除暂停等待，让 worker 尽快退出
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="正在停止...", text_color=COLORS["danger"])
        self._log("[提示] 正在停止，处理完当前笔记后退出")

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.progress_queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, done, total, title, ok, fail = item
                    pct = done / total if total else 0
                    self.progress_bar.set(pct)
                    self.percent_label.configure(text=f"{pct * 100:.1f}%")
                    self.status_label.configure(
                        text=f"{done} / {total} 篇 · 成功 {ok} · 失败 {fail}")
                    self.metric_total.set(total)
                    self.metric_ok.set(ok)
                    self.metric_fail.set(fail)
                    self._log(f"✓ {title}")
                elif kind == "log":
                    self._log(item[1])
                elif kind == "done":
                    _, stats = item
                    self.progress_bar.set(1.0)
                    self.percent_label.configure(text="100%")
                    self.status_label.configure(
                        text=f"完成 · 成功 {stats.success} · 失败 {stats.failed}",
                        text_color=COLORS["success"])
                    self._log("=" * 44)
                    self._log(f"导出完成: 总 {stats.total} 篇, "
                              f"成功 {stats.success}, 失败 {stats.failed}")
                    if stats.failures:
                        self._log(f"失败 {len(stats.failures)} 条，可在 "
                                  f"{stats.failures[0].get('title', '')} 等查看")
                    self._reset_buttons()
                elif kind == "error":
                    _, err = item
                    self.status_label.configure(text="导出出错", text_color=COLORS["danger"])
                    self._log(f"[错误] {err}")
                    self._reset_buttons()
                elif kind == "login_result":
                    _, (source, ok) = item
                    self._handle_login_result(source, ok)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _reset_buttons(self) -> None:
        """导出结束（完成/出错/停止）后恢复空闲状态"""
        self._set_running(False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="为知笔记导出工具 GUI")
    parser.add_argument("--input", default="", help="预填为知笔记数据目录")
    args = parser.parse_args(argv)

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = ExporterGUI(preset_input=args.input)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
