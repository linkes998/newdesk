from __future__ import annotations

import sys

from .output import main as cli_main


def main() -> None:
    """默认启动 GUI，传 --cli 则走命令行模式。"""
    if "--cli" in sys.argv:
        cli_main()
        return
    try:
        from .gui import NewsDeskApp
        app = NewsDeskApp()
        app.mainloop()
    except ImportError as exc:
        print(f"GUI 依赖缺失（请安装 customtkinter），回退到 CLI：{exc}")
        cli_main()


if __name__ == "__main__":
    main()
