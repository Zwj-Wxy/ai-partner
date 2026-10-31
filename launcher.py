# -*- coding: utf-8 -*-
"""
PyInstaller 打包入口：在 exe 内部启动 Streamlit 服务。

直接用 streamlit 命令行无法打包成 exe，所以用这个脚本作为入口，
再调用 streamlit 自己的 CLI（streamlit.web.cli.main）。
"""

import os
import sys

# 页面标题（和 app.py 的 APP_TITLE 保持一致）：独立窗口的标题栏就是它，也用来判断窗口是否真的打开了
WINDOW_TITLE_HINT = "AI智能伴侣"


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


def _health(port: int, timeout: float = 1.5) -> bool:
    """端口上是不是已经有我们自己的服务在跑（Streamlit 的健康检查）。"""
    import urllib.request

    url = f"http://127.0.0.1:{port}/_stcore/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200 and response.read(32).strip().lower().startswith(b"ok")
    except Exception:
        return False


# 常见浏览器路径（Edge 是 Windows 10/11 自带的，优先用它）
_BROWSER_CANDIDATES = (
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
)


def find_browser() -> str:
    """找一个支持 --app 模式的 Chromium 内核浏览器；用户可以自己指定路径。"""
    override = (os.environ.get("AI_PARTNER_BROWSER") or "").strip()
    if override:
        return override if os.path.exists(override) else ""
    for candidate in _BROWSER_CANDIDATES:
        path = os.path.expandvars(candidate)
        if os.path.exists(path):
            return path
    return ""


def _window_profile_dir() -> str:
    """独立窗口用单独的用户配置目录：不污染用户自己的浏览器，关掉就是干净的。"""
    base = (os.environ.get("AI_PARTNER_HOME") or "").strip() or os.path.join(
        os.path.expanduser("~"), ".ai_partner"
    )
    return os.path.join(base, "browser")


def _find_app_window(before: set, url: str, title_hint: str = "", timeout: float = 15.0) -> int:
    """等「新开出来的那个窗口」，返回它的句柄（找不到返回 0）。

    不能用标题匹配：Edge/Chrome 的应用窗口标题其实是 `<host>_<path>`
    （比如 `localhost_/`），端口和页面标题都不进去。所以改成：
    启动前记下已有窗口句柄，之后只要出现一个**新的** Chrome_WidgetWin 窗口，
    且标题以 origin 记号（`localhost_`）开头或含 title_hint，就算成功。
    """
    import time

    token = _origin_token(url)
    deadline = time.time() + timeout
    while time.time() < deadline:
        for hwnd, _pid, title, cls in _visible_windows():
            if hwnd in before or not cls.startswith("Chrome_WidgetWin"):
                continue
            if token and token in title:
                return hwnd
            if title_hint and title_hint in title:
                return hwnd
        time.sleep(0.3)
    return 0


def _decorate_window(hwnd: int, title: str) -> None:
    """把窗口标题和图标换成我们自己的——不然任务栏上写的是 `localhost_/`、图标是 Edge 的。

    跨进程改标题/图标对顶层窗口是允许的（SetWindowText / WM_SETICON），
    浏览器可能在下一次导航时改回去，所以这里只是"尽力而为"，失败也不影响使用。
    """
    import ctypes

    if not hwnd:
        return
    user32 = ctypes.windll.user32
    SMTO_ABORTIFHUNG = 0x0002
    WM_SETTEXT = 0x000C

    def _send(message, wparam, lparam):
        """带超时的 SendMessage：浏览器窗口卡住时不能把我们也拖死。"""
        try:
            user32.SendMessageTimeoutW(
                hwnd, message, wparam, lparam, SMTO_ABORTIFHUNG, 800, None
            )
        except Exception:
            pass

    _send(WM_SETTEXT, 0, ctypes.c_wchar_p(title))

    icon_path = os.path.join(bundle_dir(), "app.ico")
    if not os.path.exists(icon_path):
        return
    try:
        IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x0010, 0x0040
        WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1
        hicon = user32.LoadImageW(None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if hicon:
            _send(WM_SETICON, ICON_BIG, hicon)
            _send(WM_SETICON, ICON_SMALL, hicon)
    except Exception:
        pass


def _origin_token(url: str) -> str:
    """http://localhost:8501 -> `localhost_`（Edge 应用窗口标题的实际写法）。

    实测：Edge/Chrome 的 --app 窗口标题是 `<host>_<path>`，端口会被丢掉、
    页面标题也不会传进去，所以只能拿主机名当记号。
    """
    body = url.split("://", 1)[-1].split("/", 1)[0]  # localhost:8501
    host = body.split(":")[0]                         # localhost
    return host + "_"


def _visible_windows():
    """枚举所有可见的顶层窗口，产出 (hwnd, pid, 标题, 窗口类名)。"""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    results = []

    def _callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value
            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buffer, 256)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            results.append((hwnd, pid.value, title, class_buffer.value))
        return True

    user32.EnumWindows(enum_proc(_callback), 0)
    return results


def open_app_window(url: str, title_hint: str = "") -> bool:
    """以「应用窗口」方式打开：没有地址栏、没有标签页、独立任务栏图标，看起来就是个软件。

    打不开（没装 Edge/Chrome、或浏览器拒绝）就退回浏览器标签页，
    总之不能出现"双击了但什么都没发生"。
    """
    import subprocess
    import webbrowser

    if os.environ.get("AI_PARTNER_WINDOW", "1") == "0":
        _open_in_browser(url)
        return False

    browser = find_browser()
    if not browser:
        print("[提示] 没找到 Edge/Chrome，改用默认浏览器打开。")
        _open_in_browser(url)
        return False

    args = [
        browser,
        "--app=" + url,
        "--window-size=1180,860",
        "--user-data-dir=" + _window_profile_dir(),
        "--no-first-run",
        "--no-default-browser-check",
        "--no-service-autorun",
        "--disable-features=Translate",
    ]
    before = set(hwnd for hwnd, _pid, _title, _cls in _visible_windows())
    try:
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        print(f"[提示] 独立窗口打开失败（{exc}），改用默认浏览器。")
        _open_in_browser(url)
        return False

    hwnd = _find_app_window(before, url, title_hint)
    if hwnd:
        _decorate_window(hwnd, title_hint or WINDOW_TITLE_HINT)
        return True

    # 没等到窗口：多半是浏览器以管理员权限在跑，拒绝了这个请求
    print(
        "[提示] 独立窗口没能打开（浏览器可能正以管理员权限运行），这次改用浏览器标签页。\n"
        "       想要独立窗口：把浏览器窗口全部关掉，再双击「启动AI智能伴侣」。"
    )
    try:
        proc.terminate()
    except OSError:
        pass
    _open_in_browser(url)
    return False


def _open_in_browser(url: str) -> bool:
    """最后的兜底：一定要让页面出现在用户眼前。

    依次试 ShellExecute（os.startfile）、explorer、webbrowser——
    其中 explorer 是以桌面 Shell 的身份去开，权限最"正常"，最容易被忽略的那个反而最可靠。
    """
    import subprocess
    import webbrowser

    write_current_url(url)

    try:
        os.startfile(url)  # noqa: S606 - Windows 专用，等价于双击
        return True
    except OSError:
        pass

    try:
        subprocess.Popen(["explorer.exe", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        pass

    try:
        return webbrowser.open(url)
    except Exception:
        return False


def write_current_url(url: str) -> None:
    """把当前地址写进 当前地址.txt：窗口没弹出来时，用户还能自己复制去打开。"""
    path = os.path.join(log_dir(), "当前地址.txt")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "AI智能伴侣已经启动，地址是：\n\n"
                + url
                + "\n\n"
                "如果浏览器没有自动打开，把上面这行地址复制到浏览器地址栏即可。\n"
            )
    except OSError:
        pass


def open_window_when_ready(port: int, title_hint: str = "") -> None:
    """服务真正能应答之后再开窗口——否则用户会先看到一个"无法访问"的页面。"""
    import threading
    import time

    url = f"http://localhost:{port}"

    def worker() -> None:
        deadline = time.time() + 120
        while time.time() < deadline:
            if _health(port):
                write_current_url(url)  # 万一窗口没弹出来，用户能自己复制地址
                open_app_window(url, title_hint)
                return
            time.sleep(0.4)

    threading.Thread(target=worker, daemon=True, name="open-window").start()


def _ensure_streams() -> None:
    """窗口模式（console=False）下 sys.stdout/stderr 是 None，Streamlit 一写日志就崩。

    打包成"没有黑窗口"的软件后必须补上这个：把输出接到 运行日志.txt，
    既避免崩溃，出问题时也还有线索可查。
    """
    if not getattr(sys, "frozen", False):
        return
    if sys.stdout is not None and sys.stderr is not None:
        return
    path = os.path.join(log_dir(), "运行日志.txt")
    try:
        stream = open(path, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        try:
            stream = open(os.devnull, "w", encoding="utf-8")
        except OSError:
            return
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def _fatal(message: str) -> None:
    """起不来的时候要让人看见原因：有控制台就打印，没有就弹窗（像正常软件那样）。"""
    print("\n" + "=" * 64)
    print(message)
    print("=" * 64)
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            input("按回车键关闭窗口…")
            return
    except (EOFError, OSError, AttributeError):
        pass
    if not getattr(sys, "frozen", False):
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "AI 智能伴侣 — 启动失败", 0x10)
    except Exception:
        pass


def _self_check() -> int:
    """自检模式：只验证包里的依赖能不能 import，然后退出（返回 0 表示通过）。

    打包后 app.py 是当数据文件被 Streamlit exec 的，PyInstaller 静态分析看不到
    它的 import；一旦漏收某个包，用户看到的只是网页里一段红字 Traceback。
    所以让打包流程真的把 exe 跑一遍自检（AI_PARTNER_SELFCHECK=1）：
        ModuleNotFoundError 会在这一步当场暴露，发不出去。

    窗口模式下没有 stdout，所以结果既打印也写文件（AI_PARTNER_SELFCHECK_OUT）。
    """
    import importlib
    import traceback

    lines = []
    try:
        checked = []
        for name in ("streamlit", "openai"):
            module = importlib.import_module(name)
            checked.append(f"{name}={getattr(module, '__version__', '?')}")
        lines.append("SELFCHECK OK " + " ".join(checked))
        code = 0
    except Exception:
        lines.append("SELFCHECK FAILED")
        lines.append(traceback.format_exc())
        code = 2

    text = "\n".join(lines)
    print(text)
    out_path = (os.environ.get("AI_PARTNER_SELFCHECK_OUT") or "").strip()
    if out_path:
        try:
            with open(out_path, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError:
            pass
    return code


def main() -> None:
    _ensure_streams()

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

    # 已经开着（用户关掉窗口后又双击）就只把窗口叫回来，别再起一个服务
    if os.environ.get("AI_PARTNER_SELFCHECK") != "1":
        for port in range(preferred, preferred + 10):
            if _health(port):
                print(f"[提示] 程序已经在运行（端口 {port}），直接打开窗口。")
                open_app_window(f"http://localhost:{port}", WINDOW_TITLE_HINT)
                raise SystemExit(0)

    port = pick_port(preferred)

    if port != preferred:
        print(f"[提示] 端口 {preferred} 被占用，改用 {port}")

    # 窗口由我们自己开（--app 应用窗口），所以让 Streamlit 别去调默认浏览器
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.port", str(port),
        "--server.address", "localhost",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        # 主题与界面（打包后没有 .streamlit/config.toml，这里直接写死）
        "--theme.base", "light",
        "--theme.primaryColor", "#FF6B9D",
        "--client.toolbarMode", "minimal",
    ]

    # CI 里只验证 HTTP 能不能起来，不需要窗口
    if os.environ.get("CI"):
        sys.exit(stcli.main())

    open_window_when_ready(port, WINDOW_TITLE_HINT)
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
        raise SystemExit(_self_check())
    try:
        main()
    except SystemExit as exc:
        # 正常退出（code 0）不记日志；带错误码退出（端口冲突、缺文件等）要留下线索
        if exc.code in (0, None):
            raise
        log_path = write_error_log(_crash_report(note=str(exc.code)))
        extra = f"\n\n详细日志已保存到：{log_path}" if log_path else ""
        _fatal(str(exc.code) + extra)
        raise
    except BaseException:
        import traceback

        traceback.print_exc()
        log_path = write_error_log(_crash_report())
        extra = f"\n\n详细日志已保存到：{log_path}" if log_path else ""
        _fatal(
            "AI 智能伴侣启动失败。" + extra
            + "\n\n可以把「启动日志.txt」反馈给作者；也可以改用源码运行："
            "pip install -r requirements.txt 后 streamlit run app.py"
        )
        raise
