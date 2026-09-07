# PyInstaller spec for NewsDesk v0.4.0 — GUI 版本（无控制台窗口）
# 使用：pyinstaller NewsDesk.spec

import sys
from pathlib import Path

# 硬编码（spec 执行时无 __file__）
src_path = str(Path.cwd() / "src")

a = Analysis(
    ["run_gui.py"],
    pathex=[src_path],
    binaries=[],
    datas=[],
    hiddenimports=[
        "customtkinter",
        "customtkinter.assets",
        "customtkinter.windows",
        "customtkinter.appearance_mode",
        "customtkinter.scaling",
        "feedparser",
        "feedparser.namespaces.admin",
        "feedparser.namespaces.content",
        "feedparser.namespaces.dc",
        "feedparser.namespaces.sy",
        "feedparser.namespaces.w3c",
        "yaml",
        "requests",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "PIL",
        "PIL.Image",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="NewsDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # ← 关键：不显示黑色命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
