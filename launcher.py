# -*- coding: utf-8 -*-
"""
PyInstaller 打包入口：在 exe 内部启动 Streamlit 服务。

直接用 streamlit 命令行无法打包成 exe，所以用这个脚本作为入口，
再调用 streamlit 自己的 CLI（streamlit.web.cli.main）。
"""

import os
import sys


def bundle_dir() -> str:
    """PyInstaller 解包目录；源码运行时就是本文件所在目录。"""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _pause_if_interactive(message: str) -> None:
    """双击运行时控制台会随进程退出立刻关闭，出错时停一下，让人看得见原因。"""
    print("\n" + "=" * 64)
    print(message)
    print("=" * 64)
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return
        input("按回车键关闭窗口…")
    except (EOFError, OSError, AttributeError):
        return


def main() -> None:
    from streamlit.web import cli as stcli

    app_path = os.path.join(bundle_dir(), "app.py")
    if not os.path.exists(app_path):
        raise SystemExit(f"找不到应用入口文件：{app_path}")

    port = os.environ.get("AI_PARTNER_PORT", "8501")
    # CI 里跑启动验证时没有浏览器，headless=true 免得它去找浏览器
    headless = "true" if os.environ.get("CI") else "false"

    # 等价于：streamlit run app.py --server.port 8501
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.port", str(port),
        "--server.address", "localhost",
        "--server.headless=" + headless,
        "--browser.gatherUsageStats=false",
        # 主题与界面（打包后没有 .streamlit/config.toml，这里直接写死）
        "--theme.base", "light",
        "--theme.primaryColor", "#FF6B9D",
        "--client.toolbarMode", "minimal",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback

        traceback.print_exc()
        _pause_if_interactive(
            "启动失败：上面是详细错误信息。\n"
            "可以把这段文字反馈给作者；也可以改用源码运行：pip install -r requirements.txt 后 streamlit run app.py"
        )
        raise
