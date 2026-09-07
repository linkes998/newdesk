"""NewsDesk 桌面 GUI — v0.4.0 / CustomTkinter"""
from __future__ import annotations

import json
import os
import threading
import tkinter as tk
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import customtkinter as ctk

# v0.4.0 新 API
from .config import KEYWORDS, NEWS_FEEDS, SKIP, load_config
from .llm import build_llm_client
from .models import Event
from .output import generate_drafts, run_pipeline, _template_fallback
from .ranker import rank_and_merge
from .review import ReviewQueue, ReviewItem, ReviewStatus
from .rss import fetch_rss, clean
from .scoring import collect_events
from .templates import (
    STYLE_PRESETS, STYLE_MAP, PLATFORM_META,
    get_style, all_styles,
)
from .publisher import PublisherHub, PublishResult
from .export import export as export_content
from .video import generate_video_script, generate_video_script_template

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


CONFIG_FILE = Path.home() / ".newsdesk" / "config.json"


# ---------------------------------------------------------------------------
# 用户配置持久化（GUI 专用，独立于 config.yaml）
# ---------------------------------------------------------------------------

def load_user_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "llm_api_key": "",
        "llm_base_url": "",
        "llm_model": "",
        "default_style": "professional",
        "default_platforms": ["x", "telegram", "discord"],
        "default_language": "zh",
        "rss_feeds": list(NEWS_FEEDS),
        "skip_words": list(SKIP),
    }


def save_user_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_user_config_to_env(cfg: dict) -> None:
    os.environ["NEWSDESK_LLM_API_KEY"] = cfg.get("llm_api_key", "")
    os.environ["NEWSDESK_LLM_BASE_URL"] = cfg.get("llm_base_url", "")
    os.environ["NEWSDESK_LLM_MODEL"] = cfg.get("llm_model", "")


# ---------------------------------------------------------------------------
# 后台 Worker
# ---------------------------------------------------------------------------

class Worker(threading.Thread):
    def __init__(self, target_fn, on_result=None, on_error=None):
        super().__init__(daemon=True)
        self._target = target_fn
        self._on_result = on_result
        self._on_error = on_error

    def run(self):
        try:
            result = self._target()
            if self._on_result:
                self._on_result(result)
        except Exception as exc:
            if self._on_error:
                self._on_error(exc)


# ---------------------------------------------------------------------------
# 主应用
# ---------------------------------------------------------------------------

class NewsDeskApp(ctk.CTk):
    PLATFORM_ORDER = ("x", "telegram", "discord")
    PLATFORM_LABELS = {"x": "X / Twitter", "telegram": "Telegram", "discord": "Discord"}
    STYLE_LABELS = {s.key: f"{s.label} ({s.key})" for s in STYLE_PRESETS}

    def __init__(self):
        super().__init__()
        self.title("NewsDesk · v0.4.0 多平台文案自动化")
        self.geometry("1400x880")
        self.minsize(1150, 720)

        self.cfg = load_user_config()
        self.events: list[Event] = []
        self.drafts: dict[int, dict[str, str]] = {}   # idx -> {platform: text}
        self._running = False

        # 读取 config.yaml 里的 data_dir
        cfg_yaml = load_config()
        self.data_dir = Path(cfg_yaml.get("paths", {}).get("data_dir", "data"))
        self.review_queue_path = self.data_dir / "review_queue.json"
        self.queue = ReviewQueue(path=str(self.review_queue_path))
        self.queue.load()

        self._build_ui()
        self.after(300, lambda: self._set_status("就绪 · v0.4.0 · 10 种风格 · 7 个平台 · 导出/发布/短视频脚本"))

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._build_toolbar()
        self._build_main()
        self._build_statusbar()

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, height=54, corner_radius=0)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)

        ctk.CTkLabel(bar, text="📰 NewsDesk v0.4", font=("", 18, "bold")).pack(side="left", padx=14)

        ctk.CTkButton(bar, text="🔍 抓取", width=90, command=self._on_fetch).pack(side="left", padx=3, pady=10)
        ctk.CTkButton(bar, text="✍️ 生成文案", width=120, command=self._on_generate, fg_color="#1f6feb").pack(side="left", padx=3, pady=10)
        ctk.CTkButton(bar, text="⚡ 一键抓+生", width=130, command=self._on_one_shot, fg_color="green").pack(side="left", padx=3, pady=10)
        ctk.CTkButton(bar, text="📋 审核中心", width=110, command=self._on_review_center).pack(side="left", padx=3, pady=10)
        ctk.CTkButton(bar, text="📦 导出", width=90, command=self._on_export).pack(side="left", padx=3, pady=10)
        ctk.CTkButton(bar, text="🚀 发布", width=90, command=self._on_publish, fg_color="#238636").pack(side="left", padx=3, pady=10)
        ctk.CTkButton(bar, text="🎬 短视频", width=100, command=self._on_video).pack(side="left", padx=3, pady=10)

        self.progress = ctk.CTkProgressBar(bar, width=200)
        self.progress.pack(side="right", padx=14)
        self.progress.set(0)

    def _build_main(self):
        # 左：配置
        self.left = ctk.CTkScrollableFrame(self, width=320, corner_radius=0, fg_color="transparent")
        self.left.grid(row=1, column=0, sticky="ns", padx=(6, 3), pady=(3, 0))

        # 右：事件 + 文案
        self.right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right.grid(row=1, column=1, sticky="nsew", padx=(3, 6), pady=(3, 0))
        self.right.grid_rowconfigure(1, weight=1)
        self.right.grid_columnconfigure(0, weight=1)

        self._build_config_panel()
        self._build_event_list()
        self._build_draft_tabs()

    # --- 左：配置 ---
    def _build_config_panel(self):
        ctk.CTkLabel(self.left, text="⚙️ 配置中心", font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))

        # LLM
        f = ctk.CTkFrame(self.left)
        f.pack(fill="x", pady=3)
        ctk.CTkLabel(f, text="🤖 LLM API（空则模板）", font=("", 12, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.var_key = tk.StringVar(value=self.cfg.get("llm_api_key", ""))
        self.var_url = tk.StringVar(value=self.cfg.get("llm_base_url", ""))
        self.var_model = tk.StringVar(value=self.cfg.get("llm_model", ""))
        self._entry(f, "Key", self.var_key, show="●")
        self._entry(f, "Base URL", self.var_url, placeholder="https://.../v1")
        self._entry(f, "Model", self.var_model, placeholder="agnes-2.5-flash")
        ctk.CTkButton(f, text="测试连接", width=90, command=self._on_test_llm).pack(padx=10, pady=(2, 8), anchor="w")

        # 风格
        f2 = ctk.CTkFrame(self.left)
        f2.pack(fill="x", pady=3)
        ctk.CTkLabel(f2, text="🎨 写作风格", font=("", 12, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.var_style = tk.StringVar(value=self.cfg.get("default_style", "professional"))
        style_menu = ctk.CTkOptionMenu(
            f2, variable=self.var_style,
            values=[s.key for s in STYLE_PRESETS],
            height=30, dynamic_resizing=False, width=200,
        )
        style_menu.pack(padx=10, pady=(0, 4))

        ctk.CTkLabel(f2, text="💬 语言", font=("", 12, "bold")).pack(anchor="w", padx=10)
        self.var_lang = tk.StringVar(value=self.cfg.get("default_language", "zh"))
        lang_menu = ctk.CTkOptionMenu(f2, variable=self.var_lang, values=["zh", "en", "auto"], height=30, dynamic_resizing=False, width=200)
        lang_menu.pack(padx=10, pady=(0, 8))

        # 平台选择
        f3 = ctk.CTkFrame(self.left)
        f3.pack(fill="x", pady=3)
        ctk.CTkLabel(f3, text="📱 目标平台", font=("", 12, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
        self.chk_x = ctk.CTkCheckBox(f3, text="X / Twitter")
        self.chk_tg = ctk.CTkCheckBox(f3, text="Telegram")
        self.chk_dc = ctk.CTkCheckBox(f3, text="Discord")
        defaults = self.cfg.get("default_platforms", ["x", "telegram", "discord"])
        self.chk_x.select() if "x" in defaults else self.chk_x.deselect()
        self.chk_tg.select() if "telegram" in defaults else self.chk_tg.deselect()
        self.chk_dc.select() if "discord" in defaults else self.chk_dc.deselect()
        self.chk_x.pack(padx=14, anchor="w")
        self.chk_tg.pack(padx=14, anchor="w")
        self.chk_dc.pack(padx=14, anchor="w")

        # RSS 源
        f4 = ctk.CTkFrame(self.left)
        f4.pack(fill="x", pady=3)
        ctk.CTkLabel(f4, text="📡 RSS 源（每行一条）", font=("", 12, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.rss_box = ctk.CTkTextbox(f4, height=100)
        self.rss_box.pack(fill="x", padx=10, pady=(0, 8))
        self.rss_box.insert("1.0", "\n".join(self.cfg.get("rss_feeds", NEWS_FEEDS)))

        # 保存
        ctk.CTkButton(self.left, text="💾 保存配置", command=self._on_save_cfg).pack(fill="x", pady=(8, 0))

    def _entry(self, parent, label, variable, show=None, placeholder=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=1)
        ctk.CTkLabel(row, text=label, width=70, anchor="w").pack(side="left")
        kw = {"textvariable": variable, "height": 30, "placeholder_text": placeholder}
        if show:
            kw["show"] = show
        ctk.CTkEntry(row, **kw).pack(side="left", fill="x", expand=True)

    # --- 右：事件列表 ---
    def _build_event_list(self):
        f = ctk.CTkFrame(self.right)
        f.grid(row=0, column=0, sticky="ew", pady=(0, 3))
        ctk.CTkLabel(f, text="📋 事件列表（点击选中编辑 / 双击打开原文）", font=("", 13, "bold")).pack(anchor="w", padx=10, pady=6)

        cols = ("#", "标题", "分数", "标签", "链接")
        self.tree = ttk.Treeview(f, columns=cols, show="headings", height=6)
        for col, w in zip(cols, (32, 440, 50, 110, 260)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center" if col in ("#", "分数") else "w")
        self.tree.pack(fill="x", padx=10, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select_event)
        self.tree.bind("<Double-1>", lambda e: self._open_url())

    def _build_draft_tabs(self):
        self.tabs = ctk.CTkTabview(self.right)
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.draft_texts: dict[str, ctk.CTkTextbox] = {}
        self.review_labels: dict[str, ctk.CTkLabel] = {}
        self.word_labels: dict[str, ctk.CTkLabel] = {}

        for p in self.PLATFORM_ORDER:
            tab = self.tabs.add(self.PLATFORM_LABELS[p])
            tb = ctk.CTkTextbox(tab, wrap="word", font=("Consolas", 12))
            tb.grid(row=0, column=0, columnspan=5, sticky="nsew", padx=10, pady=(10, 4))
            tb.bind("<<Modified>>", lambda e, plat=p: self._on_edit_draft(plat))
            self.draft_texts[p] = tb

            bottom = ctk.CTkFrame(tab, fg_color="transparent")
            bottom.grid(row=1, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 10))

            ctk.CTkLabel(bottom, text="审核：", text_color="gray").pack(side="left")
            lbl = ctk.CTkLabel(bottom, text="—", text_color="gray")
            lbl.pack(side="left", padx=(0, 12))
            self.review_labels[p] = lbl

            ctk.CTkLabel(bottom, text="字数：", text_color="gray").pack(side="left")
            wlbl = ctk.CTkLabel(bottom, text="0")
            wlbl.pack(side="left", padx=(0, 12))
            self.word_labels[p] = wlbl

            ctk.CTkButton(bottom, text="🌐 原文", width=80, command=self._open_url).pack(side="right", padx=2)
            ctk.CTkButton(bottom, text="↩ 重置", width=70, command=lambda plat=p: self._reset_draft(plat)).pack(side="right", padx=2)
            ctk.CTkButton(bottom, text="✅ 通过", width=70, command=lambda plat=p: self._set_review(plat, "approved")).pack(side="right", padx=2)

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color="#2b2b2b")
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        self.status = ctk.CTkLabel(bar, text="就绪", text_color="#aaaaaa", font=("", 11))
        self.status.pack(side="left", padx=12)

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def _set_status(self, msg: str): self.status.configure(text=msg)
    def _platforms(self) -> list[str]:
        ps = []
        if self.chk_x.get(): ps.append("x")
        if self.chk_tg.get(): ps.append("telegram")
        if self.chk_dc.get(): ps.append("discord")
        return ps or ["x", "telegram", "discord"]

    def _open_url(self):
        sel = self.tree.selection()
        if sel:
            idx = int(sel[0])
            if idx < len(self.events):
                webbrowser.open(self.events[idx].url)

    def _set_review_label(self, platform: str, status: str):
        colors = {"pending": "#f0ad4e", "approved": "#5cb85c", "rejected": "#ff7b72", "modified": "#58a6ff"}
        self.review_labels[platform].configure(text=f"● {status}", text_color=colors.get(status, "gray"))

    # ------------------------------------------------------------------
    # 配置保存 / LLM 测试
    # ------------------------------------------------------------------
    def _on_save_cfg(self):
        self.cfg["llm_api_key"] = self.var_key.get()
        self.cfg["llm_base_url"] = self.var_url.get()
        self.cfg["llm_model"] = self.var_model.get()
        self.cfg["default_style"] = self.var_style.get()
        self.cfg["default_language"] = self.var_lang.get()
        self.cfg["default_platforms"] = self._platforms()
        self.cfg["rss_feeds"] = [l.strip() for l in self.rss_box.get("1.0", "end").splitlines() if l.strip()]
        save_user_config(self.cfg)
        _apply_user_config_to_env(self.cfg)
        self._set_status("✅ 配置已保存")

    def _on_test_llm(self):
        _apply_user_config_to_env(self.cfg)
        client = build_llm_client()
        if client is None:
            messagebox.showwarning("提示", "未配置 API Key")
            return
        self._set_status("🔄 测试 LLM 连接...")

        def do_test(): return client.generate("回复一个词：ok", model=self.var_model.get() or None)
        def ok(r): self._set_status(f"✅ LLM 连接成功：{r[:30]}"); messagebox.showinfo("成功", r[:50])
        def err(e): self._set_status(f"❌ LLM 失败：{e}"); messagebox.showerror("失败", str(e))
        Worker(do_test, ok, err).start()

    # ------------------------------------------------------------------
    # 抓取 / 生成 / 一键
    # ------------------------------------------------------------------
    def _on_fetch(self):
        self._set_status("🔄 抓取新闻...")
        self.progress.start()
        self._running = True

        def do():
            # 临时覆盖 config.yaml 里的 feeds
            import newsdesk.config as _c
            saved = _c.NEWS_FEEDS
            _c.NEWS_FEEDS = [l.strip() for l in self.rss_box.get("1.0", "end").splitlines() if l.strip()]
            try:
                events = collect_events()
                events = rank_and_merge(events)
                events = events[:8]
                return events
            finally:
                _c.NEWS_FEEDS = saved

        def ok(result: list[Event]):
            self.events = result
            self._populate_events()
            self.progress.stop(); self.progress.set(0); self._running = False
            self._set_status(f"✅ 抓到 {len(result)} 条事件（LLM ranker 已重排）")

        def err(e):
            self.progress.stop(); self.progress.set(0); self._running = False
            self._set_status(f"❌ 抓取失败：{e}")
            messagebox.showerror("抓取失败", str(e))

        Worker(do, ok, err).start()

    def _on_generate(self):
        if not self.events:
            messagebox.showinfo("提示", "请先抓取新闻")
            return
        _apply_user_config_to_env(self.cfg)
        client = build_llm_client()
        style = self.var_style.get()
        platforms = self._platforms()
        lang = self.var_lang.get()
        self._set_status(f"🔄 生成文案（风格={style}，平台={platforms}，语言={lang}）...")
        self.progress.start(); self._running = True

        def do():
            packs = {}
            for idx, ev in enumerate(self.events):
                packs[idx] = generate_drafts(
                    ev, llm_client=client,
                    style_key=style, language=lang, platforms=platforms,
                )
            return packs

        def ok(result):
            self.drafts = result
            self._refresh_drafts()
            self.progress.stop(); self.progress.set(0); self._running = False
            mode = "LLM" if client else "模板"
            self._set_status(f"✅ 文案生成完毕（{mode} 模式）· {len(result)} 条 · 人工审核后再发布")
            messagebox.showinfo("完成", f"为 {len(result)} 条事件生成了文案。\n请在右侧 Tab 中人工审核。")

        def err(e):
            self.progress.stop(); self.progress.set(0); self._running = False
            self._set_status(f"❌ 生成失败：{e}"); messagebox.showerror("生成失败", str(e))

        Worker(do, ok, err).start()

    def _on_one_shot(self):
        if messagebox.askyesno("一键执行", "先抓取新闻再为每条生成文案。继续？"):
            self._on_fetch()
            # 简单方式：监听 events 变化（这里直接在 _on_fetch 完成回调之后触发）
            def _wait_for_fetch():
                self.wait_variable(tk.BooleanVar(value=not self._running))
                if self.events:
                    self._on_generate()
            self.after(500, lambda: self._on_generate() if self.events else None)

    # ------------------------------------------------------------------
    # 事件列表 + 文案 Tab 交互
    # ------------------------------------------------------------------
    def _populate_events(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, ev in enumerate(self.events):
            self.tree.insert("", "end", iid=str(i),
                             values=(i + 1, ev.title[:60], f"{ev.score:.1f}",
                                     ", ".join(ev.tags[:3]), ev.url[:40]))

    def _refresh_drafts(self):
        for i in range(len(self.events)):
            has = all(p in self.drafts.get(i, {}) for p in self._platforms())
            if self.tree.exists(str(i)):
                vals = list(self.tree.item(str(i), "values"))
                vals[1] = ("✓ " if has else "") + self.events[i].title[:58]
                self.tree.item(str(i), values=tuple(vals))

    def _on_select_event(self, _e=None):
        sel = self.tree.selection()
        if not sel: return
        idx = int(sel[0])
        self._show_drafts(idx)

    def _show_drafts(self, idx: int):
        if idx not in self.drafts:
            for p in self.PLATFORM_ORDER:
                tb = self.draft_texts[p]
                tb.delete("1.0", "end")
                tb.insert("1.0", "⚠️ 请先点击「生成文案」")
                tb.edit_modified(False)
                self.review_labels[p].configure(text="—", text_color="gray")
                self.word_labels[p].configure(text="0")
            return
        for p in self.PLATFORM_ORDER:
            text = self.drafts[idx].get(p, "")
            tb = self.draft_texts[p]
            tb.delete("1.0", "end")
            tb.insert("1.0", text)
            tb.edit_modified(False)
            self._set_review_label(p, "pending")
            self.word_labels[p].configure(text=str(len(text)))

    def _on_edit_draft(self, platform: str):
        tb = self.draft_texts[platform]
        if tb.edit_modified():
            tb.edit_modified(False)
            sel = self.tree.selection()
            if sel:
                idx = int(sel[0])
                if idx in self.drafts:
                    new = tb.get("1.0", "end").rstrip()
                    self.drafts[idx][platform] = new
                    self.word_labels[platform].configure(text=str(len(new)))
                    self._set_review_label(platform, "modified")

    def _reset_draft(self, platform: str):
        sel = self.tree.selection()
        if not sel: return
        idx = int(sel[0])
        if idx >= len(self.events): return
        ev = self.events[idx]
        # 用模板重新生成
        text = _template_fallback(ev, platform)
        if idx in self.drafts:
            self.drafts[idx][platform] = text
        tb = self.draft_texts[platform]
        tb.delete("1.0", "end")
        tb.insert("1.0", text)
        tb.edit_modified(False)
        self.word_labels[platform].configure(text=str(len(text)))
        self._set_review_label(platform, "pending")

    # ------------------------------------------------------------------
    # 审核中心 / 导出 / 发布 / 短视频
    # ------------------------------------------------------------------
    def _on_review_center(self):
        stats = self.queue.stats()
        msg = "\n".join(f"  {k}: {v}" for k, v in stats.items())
        messagebox.showinfo("审核队列", f"审核状态：\n{msg}\n\n完整审核请使用命令：\nNewsDesk.exe review")

    def _on_export(self):
        if not self.drafts:
            messagebox.showinfo("提示", "没有可导出的内容，请先生成文案")
            return

        # 同步当前编辑
        sel = self.tree.selection()
        if sel:
            idx = int(sel[0])
            for p in self._platforms():
                if idx in self.drafts:
                    self.drafts[idx][p] = self.draft_texts[p].get("1.0", "end").rstrip()

        # 构造 ReviewItem 列表
        items = []
        for i, ev in enumerate(self.events):
            if i in self.drafts:
                import hashlib
                item_id = hashlib.sha256(f"{ev.title}|{ev.url}".encode()).hexdigest()[:16]
                items.append(ReviewItem(
                    item_id=item_id, event_title=ev.title, event_url=ev.url,
                    event_summary=ev.summary, event_score=ev.score, event_tags=ev.tags,
                    drafts=self.drafts[i], status=ReviewStatus.APPROVED.value,
                ))

        fmt = messagebox.askstring("导出格式",
                                   "选择格式:\n  markdown - 通用 Markdown\n  html - Beehiiv/Substack\n  quaily - Quaily 社区\n  json - 结构化 JSON\n  rss - RSS 2.0 XML\n\n输入格式名：",
                                   initialvalue="markdown")
        if not fmt: return

        out_dir = Path.cwd() / "output"
        out_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        ext_map = {"html": "html", "beehiiv": "html", "substack": "html", "markdown": "md",
                   "quaily": "md", "json": "json", "rss": "xml"}
        path = out_dir / f"newsdesk_{ts}.{ext_map.get(fmt, 'md')}"
        try:
            content = export_content(fmt, items, output_path=str(path))
            messagebox.showinfo("导出成功", f"已保存到：\n{path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _on_publish(self):
        # 先把当前审核条目存入队列
        self._sync_to_queue()

        # 检查是否配置了发布凭证
        hub = PublisherHub.from_config()
        available = hub.available_platforms()
        if not available:
            messagebox.showwarning("未配置发布凭证",
                                   "未检测到 Twitter / Telegram / Discord 的发布凭证。\n\n"
                                   "请在 config.yaml 的 publisher 段或环境变量中配置：\n"
                                   "  TWITTER_BEARER_TOKEN\n  TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID\n  DISCORD_WEBHOOK_URL")
            return

        if not messagebox.askyesno("确认发布",
                                   f"将发布到 {available}，当前已批准的 {len(self.queue.by_status(ReviewStatus.APPROVED))} 条。继续？"):
            return

        self._set_status("🚀 正在发布...")
        self.progress.start()
        self._running = True

        def do_publish():
            approved = self.queue.by_status(ReviewStatus.APPROVED)
            results = {}
            for item in approved:
                results[item.item_id] = {}
                for plat in item.drafts:
                    if plat in available:
                        r = hub.publish_to(plat, item.drafts[plat])
                        results[item.item_id][plat] = r.success
                        if r.success:
                            item.mark_published(plat, r.__dict__)
            self.queue.save()
            return results, len(approved)

        def ok(result):
            results, count = result
            self.progress.stop(); self.progress.set(0); self._running = False
            self._set_status(f"✅ 发布完成 · {count} 条")
            messagebox.showinfo("发布完成", f"向 {count} 条事件发送到 {available}")

        def err(e):
            self.progress.stop(); self.progress.set(0); self._running = False
            self._set_status(f"❌ 发布失败：{e}"); messagebox.showerror("发布失败", str(e))

        Worker(do_publish, ok, err).start()

    def _on_video(self):
        if not self.events:
            messagebox.showinfo("提示", "请先抓取新闻")
            return
        _apply_user_config_to_env(self.cfg)
        client = build_llm_client()
        count = min(3, len(self.events))
        self._set_status(f"🎬 生成 {count} 条短视频脚本...")
        self.progress.start(); self._running = True

        def do():
            scripts = []
            for i, ev in enumerate(self.events[:count]):
                script = generate_video_script(ev, llm_client=client)
                scripts.append(script)
            return scripts

        def ok(scripts):
            self.progress.stop(); self.progress.set(0); self._running = False
            out_dir = Path.cwd() / "output"
            out_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            path = out_dir / f"video_scripts_{ts}.md"
            md_parts = [f"# 🎬 短视频脚本集\n自动生成 · {len(scripts)} 条\n"]
            for s in scripts:
                md_parts.append(s.to_markdown())
                md_parts.append("---\n")
            path.write_text("\n".join(md_parts), encoding="utf-8")
            self._set_status(f"✅ 短视频脚本已生成 → {path}")
            messagebox.showinfo("完成", f"已保存到：\n{path}")

        def err(e):
            self.progress.stop(); self.progress.set(0); self._running = False
            self._set_status(f"❌ 生成失败：{e}"); messagebox.showerror("失败", str(e))

        Worker(do, ok, err).start()

    def _sync_to_queue(self):
        """把 GUI 当前事件/文案同步到审核队列。"""
        for i, ev in enumerate(self.events):
            if i not in self.drafts: continue
            import hashlib
            item_id = hashlib.sha256(f"{ev.title}|{ev.url}".encode()).hexdigest()[:16]
            existing = self.queue.find(item_id)
            if existing:
                for p, t in self.drafts[i].items():
                    existing.drafts[p] = t
            else:
                self.queue.add(ReviewItem(
                    item_id=item_id, event_title=ev.title, event_url=ev.url,
                    event_summary=ev.summary, event_score=ev.score, event_tags=ev.tags,
                    drafts=self.drafts[i],
                ))
        self.queue.save()


def main() -> None:
    app = NewsDeskApp()
    app.mainloop()


if __name__ == "__main__":
    main()
