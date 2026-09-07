"""
PyInstaller 入口脚本 —— 独立文件，避免包内相对导入问题。
打包时使用：pyinstaller run.py（不是 src/newsdesk/__main__.py）
"""
import sys
import os

# 确保 src 在 path 里
_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(_here, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Windows 终端强制 UTF-8（让 emoji 和中文正常显示）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from newsdesk.output import main

if __name__ == "__main__":
    main()
