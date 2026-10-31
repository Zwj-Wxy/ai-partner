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


def app_dir() -> str:
    """exe 所在目录（打包后）或本文件目录（源码运行）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _writable(path: str) -> bool:
    """目录能不能写（Program Files 之类是只读的）。"""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".writable")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def log_dir() -> str:
    """日志往哪写：优先程序目录，不行就退到用户目录。"""
    for candidate in (app_dir(), os.path.join(os.path.expanduser("~"), ".ai_partner")):
        if _writable(candidate):
            return candidate
    return os.path.join(os.path.expanduser("~"), ".ai_partner")


def write_error_log(text: str) -> str:
    """把启动失败的详情落盘——别人的电脑上控制台一闪就没了，只能靠这个文件。"""
    path = os.path.join(log_dir(), "启动日志.txt")
    try:
        # utf-8-sig：老版本记事本也能正确显示中文
        with open(path, "w", encoding="utf-8-sig") as handle:
            handle.write(text)
        return path
    except OSError:
        return ""


def _port_is_free(port: int) -> bool:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def pick_port(preferred: int, span: int = 10) -> int:
    """8501 被占用时自动往后找。

    别人的电脑上 8501 完全可能已经被别的程序占着，写死端口会让人以为"打不开"。
    显式设了 AI_PARTNER_PORT 就尊重它，不再乱换。
    """
    if os.environ.get("AI_PARTNER_PORT"):
        if not _port_is_free(preferred):
            raise SystemExit(f"端口 {preferred} 已被其他程序占用（AI_PARTNER_PORT 指定），请换一个端口。")
        return preferred
    for port in range(preferred, preferred + span):
        if _port_is_free(port):
            return port
    raise SystemExit(f"端口 {preferred}~{preferred + span - 1} 全被占用了，没法启动。请关掉占用端口的程序后重试。")


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


def _self_check() -> None:
    """自检模式：只验证包里的依赖能不能 import，然后退出。

    打包后 app.py 是当数据文件被 Streamlit exec 的，PyInstaller 静态分析看不到
    它的 import；一旦漏收某个包，用户看到的只是网页里一段红字 Traceback。
    所以让打包流程真的把 exe 跑一遍自检（AI_PARTNER_SELFCHECK=1）：
        ModuleNotFoundError 会在这一步当场暴露，发不出去。
    """
    import importlib

    checked = []
    for name in ("streamlit", "openai"):
        module = importlib.import_module(name)
        checked.append(f"{name}={getattr(module, '__version__', '?')}")
    print("SELFCHECK OK " + " ".join(checked))


def main() -> None:
    from streamlit.web import cli as stcli

    app_path = os.path.join(bundle_dir(), "app.py")
    if not os.path.exists(app_path):
        raise SystemExit(
            f"找不到应用入口文件：{app_path}\n"
            "通常是因为解压不完整：请把整个文件夹（含 _internal 子目录）一起解压后再运行，不要只拷贝 exe。"
        )

    try:
        preferred = int(os.environ.get("AI_PARTNER_PORT", "8501"))
    except ValueError:
        preferred = 8501
    port = pick_port(preferred)
    # CI 里跑启动验证时没有浏览器，headless=true 免得它去找浏览器
    headless = "true" if os.environ.get("CI") else "false"

    if port != preferred:
        print(f"[提示] 端口 {preferred} 被占用，改用 {port}")

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


def _crash_report(note: str = "") -> str:
    """把能想到的环境信息都搜进来，方便别人把日志发回来。"""
    import datetime
    import platform
    import traceback

    lines = [
        "AI 智能伴侣 —— 启动失败日志",
        "",
        "时间：",
        "  " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "系统：",
        f"  {platform.platform()}",
        f"  Python {platform.python_version()}（打包后是 exe 内置的版本）",
        "路径：",
        "  程序目录：" + app_dir(),
        "  用户目录：" + os.path.expanduser("~"),
        "  工作目录：" + os.getcwd(),
        "  打包运行：" + ("是" if getattr(sys, "frozen", False) else "否（源码运行）"),
        "",
        "错误详情：",
        note or traceback.format_exc(),
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    if os.environ.get("AI_PARTNER_SELFCHECK") == "1":
        _self_check()
        raise SystemExit(0)
    try:
        main()
    except SystemExit as exc:
        # 正常退出（code 0）不记日志；带错误码退出（端口冲突、缺文件等）要留下线索
        if exc.code in (0, None):
            raise
        log_path = write_error_log(_crash_report(note=str(exc.code)))
        extra = f"\n详细日志已保存到：{log_path}" if log_path else ""
        _pause_if_interactive("启动失败：" + str(exc.code) + extra)
        raise
    except BaseException:
        import traceback

        traceback.print_exc()
        log_path = write_error_log(_crash_report())
        extra = f"\n详细日志已保存到：{log_path}" if log_path else ""
        _pause_if_interactive(
            "启动失败：上面是详细错误信息。" + extra
            + "\n可以把「启动日志.txt」反馈给作者；也可以改用源码运行："
            "pip install -r requirements.txt 后 streamlit run app.py"
        )
        raise
