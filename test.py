#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat 自动化管理器 GUI
功能：
- 发朋友圈（pyq_post.py）
- 发视频号（pyq_sph_post.py）
- 删除朋友圈（del_pyq.py）
- 定时器：自动模式（先删后发）和手动模式
- 文案管理、模板管理、隐私标签管理
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import subprocess
import sys
import json
import random
import os
import shutil
import importlib.util
import io
import contextlib
from pathlib import Path
from PIL import Image, ImageTk

# ============================================================
# 路径配置
# ============================================================
def get_base_dir():
    """获取基础目录：打包后取 .app 所在目录，开发时取脚本所在目录"""
    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable)
        if ".app" in str(exe_path):
            # dist/微信自动发送朋友圈.app/Contents/MacOS/xxx -> dist/
            return exe_path.parent.parent.parent.parent
        return exe_path.parent
    return Path(__file__).parent

def get_bundle_dir():
    """获取打包资源目录（.py 文件所在位置）"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

BASE_DIR = get_base_dir()       # 模板、配置文件所在（.app 外部）
BUNDLE_DIR = get_bundle_dir()   # 子脚本所在（.app 内部）
TEMPLATES_DIR = BASE_DIR / "templates"
CONFIG_FILE = BASE_DIR / "config.json"
PRIVACY_DIR = TEMPLATES_DIR / "privacy"
TAGS_DIR = PRIVACY_DIR / "tags"
COVER_LIBRARY_DIR = TEMPLATES_DIR / "视频封面"
TARGET_COVER_FILE = TEMPLATES_DIR / "target_video_cover.png"
COVER_PREVIEW_SIZE = (180, 100)
AVATAR_LIBRARY_DIR = TEMPLATES_DIR / "头像"
PROFILE_AVATAR_FILE = TEMPLATES_DIR / "profile_avatar.png"
AVATAR_PREVIEW_SIZE = (88, 88)

# 模板文件列表
REQUIRED_TEMPLATES = [
    "profile_avatar.png",
    "pyq_btn.png",
    "sph_btn.png",
    "camera_icon.png",
    "check_pyq_btn.png",
    "publish_btn.png",
    "del_icon.png",
    "del_text.png",
    "sph_share_btn1.png",
    "sph_share_btn2.png",
    "target_video_cover.png",
]


class WeChatAutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("WeChat自动化发送朋友圈")
        self.root.geometry("760x820")
        self.root.minsize(720, 620)
        self.root.resizable(True, True)

        # 状态变量
        self.timer_running = False
        self.timer_thread = None
        self.is_running = False
        self.last_send_mode = None  # 记录上次发送模式，用于自动删除

        # 初始化变量
        self.mode_var = tk.StringVar(value="pyq")  # pyq 或 sph
        self.video_path_var = tk.StringVar()
        self.image_path_var = tk.StringVar()
        self.enable_privacy_var = tk.BooleanVar(value=True)
        self.enable_auto_del_var = tk.BooleanVar(value=False)
        self.enable_timer_var = tk.BooleanVar(value=False)
        self.timer_interval_var = tk.StringVar(value="60")
        self.timer_unit_var = tk.StringVar(value="分钟")
        self.avatar_file_var = tk.StringVar(value="当前头像: 未设置")
        self.avatar_preview_image = None
        self.cover_file_var = tk.StringVar(value="当前封面: 未设置")
        self.cover_preview_image = None

        # 创建界面
        self.setup_ui()

        # 加载配置
        self.load_config()

        # 检查模板
        self.check_templates()
        self.refresh_avatar_preview()
        self.refresh_cover_preview()

    # ============================================================
    # 界面构建
    # ============================================================

    def setup_ui(self):
        """创建所有界面组件"""
        style = ttk.Style(self.root)
        style.configure("Action.TButton", padding=(18, 8))

        scroll_container = ttk.Frame(self.root)
        scroll_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(scroll_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        main_frame = ttk.Frame(canvas, padding=10)
        window_id = canvas.create_window((0, 0), window=main_frame, anchor=tk.NW)

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox(tk.ALL))

        def fit_frame_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event):
            step = int(-event.delta / 120)
            if step == 0:
                step = -1 if event.delta > 0 else 1
            canvas.yview_scroll(step, "units")

        main_frame.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_frame_width)
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # ---- 模式选择 ----
        mode_frame = ttk.LabelFrame(main_frame, text="模式选择", padding=10)
        mode_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(mode_frame, text="发朋友圈", variable=self.mode_var,
                        value="pyq").pack(side=tk.LEFT, padx=20)
        ttk.Radiobutton(mode_frame, text="发视频号", variable=self.mode_var,
                        value="sph").pack(side=tk.LEFT, padx=20)

        # ---- 头像识别 ----
        avatar_frame = ttk.LabelFrame(main_frame, text="头像识别", padding=10)
        avatar_frame.pack(fill=tk.X, pady=5)

        avatar_preview_row = ttk.Frame(avatar_frame)
        avatar_preview_row.pack(fill=tk.X)

        self.avatar_preview_label = ttk.Label(
            avatar_preview_row,
            text="未加载头像",
            anchor=tk.CENTER,
            width=14,
        )
        self.avatar_preview_label.pack(side=tk.LEFT, padx=(0, 12))

        avatar_control_frame = ttk.Frame(avatar_preview_row)
        avatar_control_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(avatar_control_frame, textvariable=self.avatar_file_var).pack(anchor=tk.W)

        avatar_btn_row = ttk.Frame(avatar_control_frame)
        avatar_btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(avatar_btn_row, text="选择头像", command=self.choose_avatar_from_library).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(avatar_btn_row, text="导入头像", command=self.import_avatar_to_library).pack(side=tk.LEFT, padx=5)
        ttk.Button(avatar_btn_row, text="打开头像库", command=self.open_avatar_library_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(avatar_btn_row, text="刷新预览", command=self.refresh_avatar_preview).pack(side=tk.LEFT, padx=5)

        # ---- 视频封面识别 ----
        cover_frame = ttk.LabelFrame(main_frame, text="视频封面识别", padding=10)
        cover_frame.pack(fill=tk.X, pady=5)

        cover_preview_row = ttk.Frame(cover_frame)
        cover_preview_row.pack(fill=tk.X)

        self.cover_preview_label = ttk.Label(
            cover_preview_row,
            text="未加载封面",
            anchor=tk.CENTER,
            width=24,
        )
        self.cover_preview_label.pack(side=tk.LEFT, padx=(0, 12))

        cover_control_frame = ttk.Frame(cover_preview_row)
        cover_control_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(cover_control_frame, textvariable=self.cover_file_var).pack(anchor=tk.W)

        cover_btn_row = ttk.Frame(cover_control_frame)
        cover_btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(cover_btn_row, text="选择封面", command=self.choose_cover_from_library).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(cover_btn_row, text="导入封面", command=self.import_cover_to_library).pack(side=tk.LEFT, padx=5)
        ttk.Button(cover_btn_row, text="打开封面库", command=self.open_cover_library_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(cover_btn_row, text="刷新预览", command=self.refresh_cover_preview).pack(side=tk.LEFT, padx=5)

        # ---- 文案设置 ----
        caption_frame = ttk.LabelFrame(main_frame, text="文案设置（每行一条，随机选择）", padding=10)
        caption_frame.pack(fill=tk.X, pady=5)

        self.caption_text = scrolledtext.ScrolledText(caption_frame, height=3, width=60)
        self.caption_text.pack(fill=tk.X)

        # ---- 媒体设置 ----
        media_frame = ttk.LabelFrame(main_frame, text="媒体设置（发朋友圈时使用）", padding=10)
        media_frame.pack(fill=tk.X, pady=5)

        video_row = ttk.Frame(media_frame)
        video_row.pack(fill=tk.X, pady=2)
        ttk.Label(video_row, text="视频路径:").pack(side=tk.LEFT)
        ttk.Entry(video_row, textvariable=self.video_path_var, width=40).pack(side=tk.LEFT, padx=5)
        ttk.Button(video_row, text="选择", command=self.choose_video).pack(side=tk.LEFT)

        image_row = ttk.Frame(media_frame)
        image_row.pack(fill=tk.X, pady=2)
        ttk.Label(image_row, text="图片路径:").pack(side=tk.LEFT)
        ttk.Entry(image_row, textvariable=self.image_path_var, width=40).pack(side=tk.LEFT, padx=5)
        ttk.Button(image_row, text="选择", command=self.choose_image).pack(side=tk.LEFT)

        # ---- 隐私设置 ----
        privacy_frame = ttk.LabelFrame(main_frame, text="隐私设置", padding=10)
        privacy_frame.pack(fill=tk.X, pady=5)

        privacy_row = ttk.Frame(privacy_frame)
        privacy_row.pack(fill=tk.X)
        ttk.Checkbutton(privacy_row, text="启用\"不给谁看\"隐私设置",
                        variable=self.enable_privacy_var).pack(side=tk.LEFT)
        ttk.Button(privacy_row, text="打开标签文件夹", command=self.open_tags_folder).pack(side=tk.RIGHT, padx=5)
        ttk.Button(privacy_row, text="刷新标签数", command=self.update_tag_count).pack(side=tk.RIGHT)

        self.tag_count_label = ttk.Label(privacy_frame, text="当前标签: 0 个")
        self.tag_count_label.pack(anchor=tk.W, pady=2)

        # ---- 删除设置 ----
        del_frame = ttk.LabelFrame(main_frame, text="删除设置", padding=10)
        del_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(del_frame, text="定时发送时自动删除上次朋友圈（先删后发）",
                        variable=self.enable_auto_del_var).pack(anchor=tk.W)
        ttk.Button(del_frame, text="手动删除一条朋友圈", command=self.manual_delete).pack(anchor=tk.W, pady=5)

        # ---- 定时设置 ----
        timer_frame = ttk.LabelFrame(main_frame, text="定时设置", padding=10)
        timer_frame.pack(fill=tk.X, pady=5)

        timer_row1 = ttk.Frame(timer_frame)
        timer_row1.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(timer_row1, text="启用定时",
                        variable=self.enable_timer_var).pack(side=tk.LEFT)
        ttk.Label(timer_row1, text="间隔:").pack(side=tk.LEFT, padx=(20, 5))
        ttk.Entry(timer_row1, textvariable=self.timer_interval_var, width=8).pack(side=tk.LEFT)
        ttk.Combobox(timer_row1, textvariable=self.timer_unit_var,
                     values=["分钟", "小时"], width=5, state="readonly").pack(side=tk.LEFT, padx=5)

        timer_row2 = ttk.Frame(timer_frame)
        timer_row2.pack(fill=tk.X, pady=5)
        ttk.Button(timer_row2, text="开始定时", command=self.start_timer).pack(side=tk.LEFT, padx=5)
        ttk.Button(timer_row2, text="停止定时", command=self.stop_timer).pack(side=tk.LEFT, padx=5)

        self.timer_status_label = ttk.Label(timer_row2, text="状态: 未运行", foreground="gray")
        self.timer_status_label.pack(side=tk.LEFT, padx=20)

        # ---- 模板管理 ----
        template_frame = ttk.LabelFrame(main_frame, text="模板管理", padding=10)
        template_frame.pack(fill=tk.X, pady=5)

        template_btn_row = ttk.Frame(template_frame)
        template_btn_row.pack(fill=tk.X)
        ttk.Button(template_btn_row, text="打开模板文件夹", command=self.open_templates_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_btn_row, text="刷新模板状态", command=self.check_templates).pack(side=tk.LEFT, padx=5)

        self.template_status_text = tk.Text(template_frame, height=2, width=60, state=tk.DISABLED)
        self.template_status_text.pack(fill=tk.X, pady=5)

        # ---- 操作按钮 ----
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(8, 12), ipady=4)

        ttk.Button(
            btn_frame,
            text="立即执行",
            command=self.run_now,
            style="Action.TButton",
            width=14,
        ).pack(side=tk.LEFT, padx=6, ipady=4)
        ttk.Button(
            btn_frame,
            text="停止执行",
            command=self.stop_running,
            style="Action.TButton",
            width=14,
        ).pack(side=tk.LEFT, padx=6, ipady=4)

        # ---- 日志输出 ----
        log_frame = ttk.LabelFrame(main_frame, text="日志输出", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, width=60)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # ============================================================
    # 配置管理
    # ============================================================

    def load_config(self):
        """从配置文件加载设置"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)

                # 加载文案
                captions = config.get("captions", [])
                if captions:
                    self.caption_text.insert(tk.END, "\n".join(captions))

                # 加载其他设置
                self.video_path_var.set(config.get("video_path", ""))
                self.image_path_var.set(config.get("image_path", ""))
                self.mode_var.set(config.get("mode", "pyq"))
                self.enable_privacy_var.set(config.get("enable_privacy", True))
                self.enable_auto_del_var.set(config.get("enable_auto_del", False))
                self.enable_timer_var.set(config.get("enable_timer", False))
                self.timer_interval_var.set(str(config.get("timer_interval", 60)))
                self.timer_unit_var.set(config.get("timer_unit", "分钟"))

                self.log("配置已加载")
            except Exception as e:
                self.log(f"加载配置失败: {e}")

    def save_config(self):
        """保存设置到配置文件"""
        # 获取文案列表
        caption_text = self.caption_text.get("1.0", tk.END).strip()
        captions = [line.strip() for line in caption_text.split("\n") if line.strip()]

        config = {
            "captions": captions,
            "video_path": self.video_path_var.get(),
            "image_path": self.image_path_var.get(),
            "mode": self.mode_var.get(),
            "enable_privacy": self.enable_privacy_var.get(),
            "enable_auto_del": self.enable_auto_del_var.get(),
            "enable_timer": self.enable_timer_var.get(),
            "timer_interval": int(self.timer_interval_var.get() or 60),
            "timer_unit": self.timer_unit_var.get(),
        }

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            self.log("配置已保存")
        except Exception as e:
            self.log(f"保存配置失败: {e}")

    # ============================================================
    # 模板检查
    # ============================================================

    def check_templates(self):
        """检查模板文件状态"""
        status_lines = []
        for tmpl in REQUIRED_TEMPLATES:
            path = TEMPLATES_DIR / tmpl
            status = "✓" if path.exists() else "✗"
            status_lines.append(f"{status} {tmpl}")

        self.template_status_text.config(state=tk.NORMAL)
        self.template_status_text.delete("1.0", tk.END)
        self.template_status_text.insert(tk.END, "  ".join(status_lines))
        self.template_status_text.config(state=tk.DISABLED)

        # 同时更新标签数
        self.update_tag_count()

    def update_tag_count(self):
        """更新隐私标签数量显示"""
        if TAGS_DIR.exists():
            tags = list(TAGS_DIR.glob("*.png"))
            count = len(tags)
        else:
            count = 0
        self.tag_count_label.config(text=f"当前标签: {count} 个")

    # ============================================================
    # 文件选择
    # ============================================================

    def choose_video(self):
        """选择视频文件"""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.mov *.MP4 *.MOV")]
        )
        if path:
            self.video_path_var.set(path)

    def choose_image(self):
        """选择图片文件"""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.JPG *.JPEG *.PNG")]
        )
        if path:
            self.image_path_var.set(path)

    def choose_avatar_from_library(self):
        """从头像库选择当前要识别的头像。"""
        from tkinter import filedialog
        AVATAR_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="从头像库选择头像",
            initialdir=str(AVATAR_LIBRARY_DIR),
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.PNG *.JPG *.JPEG")]
        )
        if path:
            self.set_profile_avatar(Path(path))

    def import_avatar_to_library(self):
        """导入新头像到头像库，并设为当前识别头像。"""
        from tkinter import filedialog
        AVATAR_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="导入头像",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.PNG *.JPG *.JPEG")]
        )
        if not path:
            return

        src = Path(path)
        dst = self.unique_avatar_path(src.name)
        try:
            shutil.copy2(src, dst)
            self.set_profile_avatar(dst)
            self.log(f"已导入头像: {dst.name}")
        except Exception as e:
            messagebox.showerror("错误", f"导入头像失败: {e}")

    def unique_avatar_path(self, filename):
        """生成头像库中的不重复文件名。"""
        AVATAR_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        stem = Path(filename).stem or "avatar"
        suffix = Path(filename).suffix.lower() or ".png"
        candidate = AVATAR_LIBRARY_DIR / f"{stem}{suffix}"
        index = 1
        while candidate.exists():
            candidate = AVATAR_LIBRARY_DIR / f"{stem}_{index}{suffix}"
            index += 1
        return candidate

    def set_profile_avatar(self, source_path):
        """复制选中的头像为 profile_avatar.png。"""
        try:
            TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            with Image.open(source_path) as img:
                img.convert("RGB").save(PROFILE_AVATAR_FILE, format="PNG")
            self.log(f"当前识别头像已切换为: {source_path.name}")
            self.refresh_avatar_preview()
            self.check_templates()
        except Exception as e:
            messagebox.showerror("错误", f"设置当前头像失败: {e}")

    def refresh_avatar_preview(self):
        """刷新 profile_avatar.png 的界面预览。"""
        if not PROFILE_AVATAR_FILE.exists():
            self.avatar_preview_label.config(text="未设置头像", image="")
            self.avatar_file_var.set("当前头像: 未设置")
            self.avatar_preview_image = None
            return

        try:
            with Image.open(PROFILE_AVATAR_FILE) as img:
                img.thumbnail(AVATAR_PREVIEW_SIZE)
                preview = ImageTk.PhotoImage(img.copy())
        except Exception as e:
            self.avatar_preview_label.config(text="预览失败", image="")
            self.avatar_file_var.set(f"当前头像: 读取失败 - {e}")
            self.avatar_preview_image = None
            return

        self.avatar_preview_image = preview
        self.avatar_preview_label.config(image=self.avatar_preview_image, text="")
        self.avatar_file_var.set(f"当前头像: {PROFILE_AVATAR_FILE.name}")

    def choose_cover_from_library(self):
        """从封面库选择当前要识别的视频封面。"""
        from tkinter import filedialog
        COVER_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="从封面库选择视频封面",
            initialdir=str(COVER_LIBRARY_DIR),
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.PNG *.JPG *.JPEG")]
        )
        if path:
            self.set_target_cover(Path(path))

    def import_cover_to_library(self):
        """导入新封面到封面库，并设为当前识别封面。"""
        from tkinter import filedialog
        COVER_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="导入视频封面",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.PNG *.JPG *.JPEG")]
        )
        if not path:
            return

        src = Path(path)
        dst = self.unique_cover_path(src.name)
        try:
            shutil.copy2(src, dst)
            self.set_target_cover(dst)
            self.log(f"已导入封面: {dst.name}")
        except Exception as e:
            messagebox.showerror("错误", f"导入封面失败: {e}")

    def unique_cover_path(self, filename):
        """生成封面库中的不重复文件名。"""
        COVER_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        stem = Path(filename).stem or "cover"
        suffix = Path(filename).suffix.lower() or ".png"
        candidate = COVER_LIBRARY_DIR / f"{stem}{suffix}"
        index = 1
        while candidate.exists():
            candidate = COVER_LIBRARY_DIR / f"{stem}_{index}{suffix}"
            index += 1
        return candidate

    def set_target_cover(self, source_path):
        """复制选中的封面为 target_video_cover.png。"""
        try:
            TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            with Image.open(source_path) as img:
                img.convert("RGB").save(TARGET_COVER_FILE, format="PNG")
            self.log(f"当前识别封面已切换为: {source_path.name}")
            self.refresh_cover_preview()
            self.check_templates()
        except Exception as e:
            messagebox.showerror("错误", f"设置当前封面失败: {e}")

    def refresh_cover_preview(self):
        """刷新 target_video_cover.png 的界面预览。"""
        if not TARGET_COVER_FILE.exists():
            self.cover_preview_label.config(text="未设置封面", image="")
            self.cover_file_var.set("当前封面: 未设置")
            self.cover_preview_image = None
            return

        try:
            with Image.open(TARGET_COVER_FILE) as img:
                img.thumbnail(COVER_PREVIEW_SIZE)
                preview = ImageTk.PhotoImage(img.copy())
        except Exception as e:
            self.cover_preview_label.config(text="预览失败", image="")
            self.cover_file_var.set(f"当前封面: 读取失败 - {e}")
            self.cover_preview_image = None
            return

        self.cover_preview_image = preview
        self.cover_preview_label.config(image=self.cover_preview_image, text="")
        self.cover_file_var.set(f"当前封面: {TARGET_COVER_FILE.name}")

    # ============================================================
    # 打开文件夹
    # ============================================================

    def open_templates_folder(self):
        """打开模板文件夹"""
        subprocess.run(["open", str(TEMPLATES_DIR)])

    def open_tags_folder(self):
        """打开标签文件夹"""
        TAGS_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(TAGS_DIR)])

    def open_cover_library_folder(self):
        """打开视频封面库文件夹。"""
        COVER_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(COVER_LIBRARY_DIR)])

    def open_avatar_library_folder(self):
        """打开头像库文件夹。"""
        AVATAR_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(AVATAR_LIBRARY_DIR)])

    # ============================================================
    # 脚本执行
    # ============================================================

    def run_now(self):
        """立即执行任务"""
        if self.is_running:
            self.log("任务正在运行中，请等待完成")
            return

        self.save_config()
        self.is_running = True

        thread = threading.Thread(target=self._run_task_thread, daemon=True)
        thread.start()

    def _run_task_thread(self):
        """任务执行线程"""
        try:
            mode = self.mode_var.get()
            captions = self.get_captions()

            if not captions:
                self.log("错误：没有可用文案")
                return

            caption = random.choice(captions)

            if mode == "pyq":
                self.run_pyq_post(caption)
                self.last_send_mode = "pyq"
            elif mode == "sph":
                self.run_sph_post(caption)
                self.last_send_mode = "sph"
        finally:
            self.is_running = False

    def _import_and_run(self, script_name):
        """从 BUNDLE_DIR 导入脚本模块并执行其 main()，捕获日志输出。"""
        script_path = BUNDLE_DIR / script_name
        if not script_path.exists():
            self.log(f"错误：找不到脚本 {script_path}")
            return False

        spec = importlib.util.spec_from_file_location(script_name.stem, str(script_path))
        module = importlib.util.module_from_spec(spec)

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                spec.loader.exec_module(module)
                if hasattr(module, "main"):
                    module.main()
                else:
                    self.log(f"错误：{script_name} 没有 main() 函数")
                    return False
        except Exception as e:
            self.log(f"脚本 {script_name} 异常: {e}")
            return False
        finally:
            output = buf.getvalue()
            if output:
                lines = output.strip().split("\n")
                for line in lines[-20:]:
                    self.log(line)

        return True

    def run_pyq_post(self, caption):
        """调用 pyq_post.py 发送朋友圈"""
        self.log(">>> 开始发朋友圈...")

        video_path = self.video_path_var.get()
        image_path = self.image_path_var.get()

        os.environ["PYQ_CAPTION"] = caption
        os.environ["PYQ_VIDEO_PATH"] = video_path
        os.environ["PYQ_IMAGE_PATH"] = image_path
        os.environ["PYQ_ENABLE_PRIVACY"] = "1" if self.enable_privacy_var.get() else "0"

        if self._import_and_run(Path("pyq_post.py")):
            self.log("朋友圈发送完成")
        else:
            self.log("朋友圈发送失败")

    def run_sph_post(self, caption):
        """调用 pyq_sph_post.py 发送视频号"""
        self.log(">>> 开始发视频号...")

        os.environ["PYQ_CAPTION"] = caption
        os.environ["PYQ_ENABLE_PRIVACY"] = "1" if self.enable_privacy_var.get() else "0"

        if self._import_and_run(Path("pyq_sph_post.py")):
            self.log("视频号发送完成")
        else:
            self.log("视频号发送失败")

    def run_del_pyq(self):
        """调用 del_pyq.py 删除朋友圈"""
        self.log(">>> 开始删除朋友圈...")

        if self._import_and_run(Path("del_pyq.py")):
            self.log("朋友圈删除成功")
            return True
        else:
            self.log("朋友圈删除失败")
            return False

    def manual_delete(self):
        """手动删除一条朋友圈"""
        if self.is_running:
            self.log("任务正在运行中，请等待完成")
            return

        self.is_running = True
        thread = threading.Thread(target=self._manual_delete_thread, daemon=True)
        thread.start()

    def _manual_delete_thread(self):
        """手动删除线程"""
        try:
            self.run_del_pyq()
        finally:
            self.is_running = False

    def stop_running(self):
        """停止当前运行"""
        self.is_running = False
        self.log("已请求停止（当前任务可能需要几秒才能完全停止）")

    # ============================================================
    # 定时器
    # ============================================================

    def start_timer(self):
        """启动定时器"""
        if self.timer_running:
            self.log("定时器已在运行中")
            return

        try:
            interval = int(self.timer_interval_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的间隔数字")
            return

        unit = self.timer_unit_var.get()
        if unit == "小时":
            interval_seconds = interval * 3600
        else:
            interval_seconds = interval * 60

        self.timer_running = True
        self.timer_status_label.config(text=f"状态: 运行中（每{interval}{unit}）", foreground="green")
        self.log(f"定时器已启动：每 {interval} {unit}")

        self.timer_thread = threading.Thread(
            target=self._timer_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self.timer_thread.start()

    def _timer_loop(self, interval_seconds):
        """定时器循环"""
        while self.timer_running:
            self.log(f"定时任务执行中...")

            # 检查是否需要先删除
            if self.enable_auto_del_var.get() and self.last_send_mode:
                self.log("自动删除模式：先删除上次朋友圈")
                self.run_del_pyq()
                time.sleep(3)

            # 执行发送任务
            self._run_task_thread()

            # 等待下次执行
            self.log(f"等待 {interval_seconds} 秒后再次执行...")
            for _ in range(interval_seconds):
                if not self.timer_running:
                    break
                time.sleep(1)

    def stop_timer(self):
        """停止定时器"""
        if not self.timer_running:
            self.log("定时器未在运行")
            return

        self.timer_running = False
        self.timer_status_label.config(text="状态: 已停止", foreground="red")
        self.log("定时器已停止")

    # ============================================================
    # 工具方法
    # ============================================================

    def get_captions(self):
        """获取文案列表"""
        caption_text = self.caption_text.get("1.0", tk.END).strip()
        return [line.strip() for line in caption_text.split("\n") if line.strip()]

    def log(self, message):
        """输出日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)


def main():
    root = tk.Tk()
    app = WeChatAutomationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
