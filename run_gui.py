"""
PyInstaller GUI 入口脚本 —— 打包成无控制台窗口的桌面 EXE。
"""
import sys
import os

# 确保 src 在 path 里
_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(_here, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# 强制导入 customtkinter（让 PyInstaller 收集它的资源）
import customtkinter
import tkinter
from tkinter import ttk, messagebox, filedialog
import PIL.Image

# 启动 GUI
from newsdesk.gui import main

if __name__ == "__main__":
    main()
