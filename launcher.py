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

# 改动 launcher 时就把它 +1，打包校验会比对 exe 自检里报出来的这个号，
# 防止「源码修好了、发出去的还是旧 exe」这种事故（这已经发生过一次）。
LAUNCHER_VERSION = "2026.10.31.9"


def _app_sha8() -> str:
    """包里 app.py 的 sha256 前 8 位（取不到就返回 ?）。"""
    import hashlib

    path = os.path.join(bundle_dir(), "app.py")
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()[:8]
    except OSError:
        return "?"


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


def _dbg(message: str) -> None:
    """启动过程关键节点写进 运行日志.txt。

    双击 exe 的窗口模式下没有控制台，print 出来的东西用户看不到；
    出问题时让他把这个文件发过来，就能知道卡在哪一步。
    """
    import datetime

    line = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [启动] {message}\n"
    try:
        with open(os.path.join(log_dir(), "运行日志.txt"), "a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass
    try:
        print(line.rstrip())
    except Exception:  # noqa: BLE001 - 没有控制台时 print 可能直接抛错
        pass


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
    """独立窗口用单独的用户配置目录：不污染用户自己的浏览器，关掉就是干净的。

    **必须先建好目录**：Chromium 只会在已存在的目录里创建 ProcessSingleton 锁文件，
    父目录不存在时它会报 `Lock file can not be created! Error code: 5` 然后直接退出，
    用户看到的就是"双击了窗口没出来"。

    顺序按"最可能写成功"排：先程序目录（解压到桌面/下载目录时一定可写），
    再用户目录，最后系统临时目录——实测有些机器上写 `C:\\Users\\<名字>\\.ai_partner`
    会被权限拦（`WinError 5 拒绝访问`），排在第一位就会每次都退到临时目录。
    """
    candidates = []
    forced = (os.environ.get("AI_PARTNER_HOME") or "").strip()
    if forced:
        candidates.append(os.path.join(forced, "browser"))
    candidates.append(os.path.join(app_dir(), "browser"))
    candidates.append(os.path.join(os.path.expanduser("~"), ".ai_partner", "browser"))

    for path in candidates:
        if _ensure_dir(path):
            return path

    # 都写不了（只读设备/受控终端）就退到临时目录，至少还能开出窗口
    import tempfile

    try:
        path = os.path.join(tempfile.mkdtemp(prefix="ai_partner_browser_"), "browser")
    except OSError:
        return os.path.join(tempfile.gettempdir(), "ai_partner_browser")
    _ensure_dir(path)
    return path


def _ensure_dir(path: str) -> bool:
    import os

    return not _ensure_dir_error(path)


def _ensure_dir_error(path: str) -> str:
    """建目录，成功返回空字符串，失败返回错误信息（排查"窗口出不来"时要看这个）。"""
    import os

    try:
        os.makedirs(path, exist_ok=True)
        return ""
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"


def _find_app_window(before: set, url: str, title_hint: str = "", timeout: float = 25.0) -> int:
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
            if hwnd in before:
                continue
            # 浏览器应用窗口的类名是 Chrome_WidgetWin*；我们自己的窗口宿主是 WindowsForms10.*
            if not (cls.startswith("Chrome_WidgetWin") or cls.startswith("WindowsForms")):
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


def _focus_window(hwnd: int) -> None:
    """把窗口提到最前面并给焦点。

    不然会出现这种"假死"：程序其实起来了、窗口也确实创建了，
    但它被压在别的窗口后面（Windows 不允许后台进程抢前台），
    用户看到的就是「双击了没反应」。这里用 AttachThreadInput 绕过前台锁。
    """
    import ctypes

    if not hwnd:
        return
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    SW_RESTORE = 9
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        foreground = user32.GetForegroundWindow()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        foreground_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        attached = False
        if foreground_thread and foreground_thread != target_thread:
            attached = bool(user32.AttachThreadInput(foreground_thread, target_thread, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        if attached:
            user32.AttachThreadInput(foreground_thread, target_thread, False)
        del kernel32
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


def _launch_app_window(url: str, profile: str):
    """启动一个浏览器「应用窗口」，返回 Popen。"""
    import subprocess

    args = [
        find_browser(),
        "--app=" + url,
        "--window-size=1180,860",
        "--user-data-dir=" + profile,
        "--no-first-run",
        "--no-default-browser-check",
        "--no-service-autorun",
        "--disable-features=Translate",
    ]
    _dbg(f"开应用窗口：{args[0]} --app={url} (profile={profile})")
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_page_loaded(hwnd: int, timeout: float = 20.0) -> bool:
    """等页面真正渲染出来——判据是窗口标题从 `localhost_/` 变成「AI智能伴侣」。

    实测：冷启动时 Edge 会先开出一个白窗口（标题 `localhost_/`），
    页面加载完标题才会变成页面自己的标题。白窗口摆在那里最像"没反应"，
    所以必须验证一次，没加载出来就当这次没成功。
    """
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        for h, _pid, title, _cls in _visible_windows():
            if h == hwnd:
                if WINDOW_TITLE_HINT in title:
                    return True
                break
        time.sleep(0.4)
    return False


def open_app_window(url: str, title_hint: str = "") -> int:
    """以「应用窗口」方式打开：没有地址栏、没有标签页、独立任务栏图标，看起来就是个软件。

    成功返回窗口句柄（>0）；失败返回 0，由调用方决定改用浏览器——
    这里不自己去开浏览器，避免同一个页面被打开两次。

    实测有概率开出白窗口（冷启动页面还没加载完），所以：
      1. 第一次用正式配置目录开；
      2. 20 秒内标题还没变成「AI智能伴侣」，就关掉它、换一个全新配置目录再开一次；
      3. 还不行就返回 0，让调用方退到默认浏览器 / 弹窗。
    宁可多重试一次，也不要给用户留一个白窗口。
    """
    if os.environ.get("AI_PARTNER_WINDOW", "1") == "0":
        return 0

    if not find_browser():
        _dbg("没找到 Edge/Chrome，无法开应用窗口")
        return 0

    base_profile = _window_profile_dir()
    for attempt, profile in enumerate((base_profile, base_profile + "_2"), start=1):
        try:
            os.makedirs(profile, exist_ok=True)
        except OSError:
            continue
        before = set(hwnd for hwnd, _pid, _title, _cls in _visible_windows())
        try:
            proc = _launch_app_window(url, profile)
        except OSError as exc:
            _dbg(f"应用窗口进程起不来：{exc}")
            return 0

        hwnd = _find_app_window(before, url, title_hint)
        if hwnd and _wait_page_loaded(hwnd):
            _decorate_window(hwnd, title_hint or WINDOW_TITLE_HINT)
            _focus_window(hwnd)
            return hwnd

        _dbg(f"第 {attempt} 次应用窗口没成功（hwnd={hwnd}），关掉重试")
        if hwnd:
            try:
                import ctypes

                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            except Exception:
                pass
        try:
            proc.terminate()
        except OSError:
            pass

    _dbg("两次应用窗口都没成功，改用浏览器")
    return 0


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
        for name in ("streamlit", "openai", "webview"):
            module = importlib.import_module(name)
            checked.append(f"{name}={getattr(module, '__version__', '?')}")
        # exe 里到底装的是哪一版启动器 / 哪一份 app.py：
        # launcher.py 会被编译进 PYZ（压缩过，没法用字符串搜索判断新旧），
        # 所以让它自己报出来，打包脚本再和源码比对，防止"发出去的是旧 exe"。
        checked.append("launcher=" + LAUNCHER_VERSION)
        checked.append("app=" + _app_sha8())
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


def _server_args(port: int, app_path: str) -> list:
    """拼出 Streamlit CLI 的参数（服务端模式用）。"""
    return [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.port", str(port),
        "--server.address", "localhost",
        # 窗口由启动器自己开，别让 Streamlit 去调默认浏览器
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        # 主题与界面（打包后没有 .streamlit/config.toml，这里直接写死）
        "--theme.base", "light",
        "--theme.primaryColor", "#FF6B9D",
        "--client.toolbarMode", "minimal",
    ]


def _run_server_only(port: int) -> None:
    """纯服务端模式：只跑 Streamlit，不开窗口（由父进程用 --server-only 调起）。"""
    from streamlit.web import cli as stcli

    app_path = os.path.join(bundle_dir(), "app.py")
    if not os.path.exists(app_path):
        raise SystemExit(
            f"找不到应用入口文件：{app_path}\n"
            "通常是因为解压不完整：请把整个文件夹（含 _internal 子目录）一起解压后再运行，不要只拷贝 exe。"
        )
    sys.argv = _server_args(port, app_path)
    sys.exit(stcli.main())


def _server_command(port: int) -> list:
    """怎么把"纯服务端"的那个自己叫起来。"""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--server-only", "--port", str(port)]
    return [sys.executable, os.path.abspath(__file__), "--server-only", "--port", str(port)]


def _native_window(url: str, icon: str) -> bool:
    """用 WebView2 开一个真正的桌面窗口（没有地址栏、没有标签页、跟本体同一个图标）。

    pywebview 在 Windows 上走的是系统自带的 WebView2 运行时，
    不依赖用户装没装 Edge/Chrome，也不会像 --app 那样受浏览器权限影响。
    返回 True 表示窗口正常打开过（关掉窗口时函数才返回）。
    """
    try:
        # 打包（frozen）环境下 pythonnet 自动挑运行时偶尔会挑错，导致
        # RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize，
        # 这里显式指定 .NET Framework（Windows 自带，不需要用户装 .NET Core）。
        from pythonnet import load as _load_runtime

        _load_runtime("netfx")
        _dbg("pythonnet 运行时 = netfx（已显式指定）")
    except Exception as exc:  # noqa: BLE001 - 已经加载过运行时会抛错，忽略即可
        _dbg(f"pythonnet 显式指定 netfx 失败（可忽略）：{type(exc).__name__}: {exc}")

    try:
        import webview
    except Exception as exc:  # noqa: BLE001
        _dbg(f"import webview 失败：{type(exc).__name__}: {exc}")
        return False

    try:
        _dbg(f"开始创建桌面窗口：{url}")
        webview.create_window(
            WINDOW_TITLE_HINT,
            url,
            width=1180,
            height=860,
            min_size=(900, 600),
            background_color="#FFFFFF",
            text_select=True,
        )
        webview.start(icon=icon if os.path.exists(icon) else None)
        _dbg("桌面窗口已关闭")
        return True
    except Exception as exc:  # noqa: BLE001 - 打不开就换方案，不能把用户卡死
        _dbg(f"桌面窗口启动失败：{type(exc).__name__}: {exc}，改用浏览器窗口")
        print(f"[提示] 桌面窗口启动失败（{exc}），改用浏览器窗口。")
        return False


def _wait_health(port: int, timeout: float = 120.0) -> bool:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _health(port):
            return True
        time.sleep(0.4)
    return False


def main() -> None:
    _ensure_streams()

    try:
        preferred = int(os.environ.get("AI_PARTNER_PORT", "8501"))
    except ValueError:
        preferred = 8501

    mode = (os.environ.get("AI_PARTNER_WINDOW") or "").strip().lower()
    _dbg(f"启动器版本 {LAUNCHER_VERSION}，exe={sys.executable}，模式={mode or '默认（桌面窗口）'}")

    # 已经开着（用户关掉窗口后又双击）就只把窗口叫回来，别再起一个服务
    for port in range(preferred, preferred + 10):
        if _health(port):
            print(f"[提示] 程序已经在运行（端口 {port}），直接打开窗口。")
            _show_window(f"http://localhost:{port}", mode)
            raise SystemExit(0)

    port = pick_port(preferred)
    if port != preferred:
        print(f"[提示] 端口 {preferred} 被占用，改用 {port}")

    app_path = os.path.join(bundle_dir(), "app.py")
    if not os.path.exists(app_path):
        raise SystemExit(
            f"找不到应用入口文件：{app_path}\n"
            "通常是因为解压不完整：请把整个文件夹（含 _internal 子目录）一起解压后再运行，不要只拷贝 exe。"
        )

    # CI 里只验证 HTTP 能不能起来，不需要窗口
    if os.environ.get("CI"):
        _run_server_only(port)

    # 服务跑在子进程里：WebView2 的窗口事件循环必须占着主线程，
    # 而 Streamlit 的 CLI 只能在主线程装信号处理器，两者不能同住一个进程。
    exe_dir = app_dir()
    env = dict(os.environ, AI_PARTNER_CHILD="1")
    log_path = os.path.join(log_dir(), "运行日志.txt")
    try:
        log_handle = open(log_path, "a", encoding="utf-8", errors="replace")
    except OSError:
        log_handle = subprocess_devnull()

    child = subprocess_popen(_server_command(port), exe_dir, env, log_handle)
    _dbg(f"已启动后台服务子进程 pid={child.pid}，端口 {port}，等待就绪…")
    try:
        if not _wait_health(port, timeout=120):
            _dbg("后台服务 120 秒内没有响应")
            raise SystemExit(
                "后台服务没能启动成功（等了 120 秒还没有响应）。\n"
                f"详细日志：{log_path}"
            )
        _dbg("后台服务已就绪，开始打开窗口")
        hwnd = _show_window(f"http://localhost:{port}", mode)
        if hwnd:
            # 关键：窗口开出来之后**不能马上退出**，否则 finally 会把服务杀掉，
            # 用户看到的就是一个白屏窗口（页面还没加载完，后端已经没了）。
            _dbg(f"窗口已打开（hwnd={hwnd}），服务保持运行，等窗口关闭")
            _wait_window_closed(hwnd, child)
            _dbg("窗口已关闭，关掉后台服务")
        else:
            _dbg("没拿到窗口句柄（走的是浏览器/弹窗），服务保持运行直到被结束")
            _keep_alive_until_child_exits(child)
    finally:
        try:
            child.terminate()
        except OSError:
            pass
        try:
            log_handle.close()
        except OSError:
            pass


def _wait_window_closed(hwnd: int, child, poll: float = 0.5) -> None:
    """等这个窗口被用户关掉（或者后台服务自己退出）。"""
    import time

    import ctypes

    user32 = ctypes.windll.user32
    while True:
        try:
            if not user32.IsWindow(hwnd):
                return
        except Exception:
            return
        if child.poll() is not None:
            return
        time.sleep(poll)


def _keep_alive_until_child_exits(child, poll: float = 0.5) -> None:
    """浏览器模式：窗口句柄拿不到，就一直陪着后台服务，直到它退出。

    用户双击 `停止AI智能伴侣.bat`（或任务管理器结束进程）就会把两个进程一起收掉。
    """
    import time

    while child.poll() is None:
        time.sleep(poll)


def subprocess_devnull():
    return open(os.devnull, "w", encoding="utf-8")


def subprocess_popen(command: list, cwd: str, env: dict, log_handle):
    import subprocess

    return subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=log_handle,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _show_window(url: str, mode: str = "") -> int:
    """按优先级把界面送到用户眼前，返回打开的应用窗口句柄（没有就是 0）。

    实测结论（2026-10-31，Edge 156）：
      * 原生窗口（pywebview + WebView2）在**源码模式**下完美，但打包成 exe 后
        pythonnet 加载 .NET 运行时会失败，用户机器上大概率起不来；
      * Edge/Chrome 的 `--app=<url>` 应用窗口**能正常用**：没有地址栏、没有标签页、
        任务栏是它自己的图标，页面加载完后标题会变成「AI智能伴侣」。
        前提是必须给它一个**已经存在**的 `--user-data-dir`（否则 Chromium 建锁文件失败直接退出），
        这样也不会被用户那个"管理员权限的 Edge"挡住。
    所以默认先试应用窗口，实在不行再退回系统默认浏览器，最后再弹窗给地址。

    返回值交给 main()：拿到句柄就一直陪着窗口，窗口关掉才收工——
    否则服务会先被杀掉，用户看到的是一个白屏窗口。
    """
    write_current_url(url)

    # 窗口/任务栏图标：优先用程序目录里的 app.ico（打包时放在 exe 旁边），
    # 源码模式退到 assets\\app.ico，都没有就交给系统默认图标。
    icon = ""
    for candidate in (
        os.path.join(app_dir(), "app.ico"),
        os.path.join(bundle_dir(), "app.ico"),
        os.path.join(bundle_dir(), "assets", "app.ico"),
    ):
        if os.path.exists(candidate):
            icon = candidate
            break

    if mode == "native":
        if _native_window(url, icon):
            return 0
        _dbg("pywebview 原生窗口不可用，继续尝试其它方式")
    elif mode == "browser":
        pass  # 用户显式要求用默认浏览器，跳过所有独立窗口
    else:
        # 默认：先用自己的 WebView2 窗口宿主（最像软件，也最稳）
        hwnd = _open_window_host(url, icon)
        if hwnd:
            _dbg("窗口宿主已打开")
            return hwnd
        # 再退一档：Edge/Chrome 的应用窗口
        hwnd = open_app_window(url, WINDOW_TITLE_HINT)
        if hwnd:
            _dbg("Edge 应用窗口已打开")
            return hwnd
        _dbg("应用窗口不可用，改用默认浏览器")

    # 兜底：直接交给系统默认浏览器（带地址栏和标签页，但 100% 是用户熟悉的东西）
    _dbg(f"用默认浏览器打开：{url}")
    before = set(hwnd for hwnd, _pid, _title, _cls in _visible_windows())
    _open_in_browser(url)
    token = _origin_token(url)
    if _wait_new_browser_window(before, timeout=12.0, token=token):
        _dbg("浏览器窗口已打开")
        return 0

    # 12 秒都没等到新窗口：最常见的原因是浏览器正以【管理员权限】运行，
    # 普通权限的程序没法让它开窗口（Windows 的权限隔离），这时给个明白的弹窗，
    # 而不是让用户对着"什么都没发生"发呆。
    _dbg("12 秒内没有出现新的浏览器窗口")
    _fatal(
        "服务已经启动好了，但没能把界面打开。\n\n"
        f"可以手动把这个地址复制到浏览器里打开：\n{url}\n\n"
        "为什么会这样？最常见的原因是你的浏览器（Edge/Chrome）正以【管理员权限】运行，\n"
        "普通权限的程序没法让它开新窗口。解决办法任选一个：\n"
        "  1. 右键「AI智能伴侣.exe」→「以管理员身份运行」；\n"
        "  2. 把上面这个地址直接粘贴到浏览器地址栏。"
    )
    return 0


def _host_exe() -> str:
    """窗口宿主 exe 的路径（打包后在程序目录，源码模式下在 assets\\window_host）。"""
    name = "AI伴侣窗口.exe"
    for base in (app_dir(), os.path.join(bundle_dir(), "window_host"), os.path.join(bundle_dir(), "assets", "window_host")):
        candidate = os.path.join(base, name)
        if os.path.exists(candidate):
            return candidate
    return ""


def _open_window_host(url: str, icon: str) -> int:
    """用自带的小窗口宿主（WinForms + WebView2）打开界面。

    为什么用这个而不是 pywebview：pythonnet 在 PyInstaller 打包后加载 .NET
    运行时会失败；而这个几十 KB 的小 exe 只用 .NET Framework 自带的
    WinForms + WebView2，稳得多，窗口标题/图标也都是我们自己的。

    返回窗口句柄；没成功返回 0（由调用方继续往后退）。
    """
    import subprocess

    host = _host_exe()
    if not host:
        _dbg("没有窗口宿主 exe，跳过")
        return 0

    before = set(hwnd for hwnd, _pid, _title, _cls in _visible_windows())
    _dbg(f"启动窗口宿主：{host} {url}")
    try:
        subprocess.Popen(
            [host, url, WINDOW_TITLE_HINT, icon],
            cwd=os.path.dirname(host),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        _dbg(f"窗口宿主起不来：{exc}")
        return 0

    hwnd = _find_app_window(before, url, WINDOW_TITLE_HINT)
    if hwnd and _wait_page_loaded(hwnd, timeout=25.0):
        _focus_window(hwnd)
        return hwnd
    _dbg(f"窗口宿主没成功（hwnd={hwnd}）")
    if hwnd:
        try:
            import ctypes

            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        except Exception:
            pass
    return 0


def _wait_new_browser_window(before: set, timeout: float = 12.0, token: str = "") -> bool:
    """等一个新的**属于我们**的浏览器窗口出现。

    只看"有没有新的 Chrome_WidgetWin"会误判：系统里任何 Edge/Chrome 弹个
    翻译气泡、通知窗口都会命中，结果就是"以为打开了、其实用户什么都没看到"。
    所以要求标题里带 origin 记号（`localhost_`）、或含「AI智能伴侣」。
    """
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        for hwnd, _pid, title, cls in _visible_windows():
            if hwnd in before or not cls.startswith("Chrome_WidgetWin"):
                continue
            if token and token in title:
                return True
            if WINDOW_TITLE_HINT in title:
                return True
        time.sleep(0.5)
    return False


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


def _diagnose() -> int:
    """诊断模式（AI_PARTNER_DIAG=1）：把路径/环境/浏览器判断结果写成文件后退出。

    排查「双击没反应」时不用猜——拿到这个文件就知道是找不到浏览器、
    配置目录建不出来，还是根本没有窗口权限。
    """
    import platform
    import tempfile

    lines = ["AI 智能伴侣 —— 诊断报告", ""]
    lines.append(f"系统：{platform.platform()}")
    lines.append(f"frozen：{bool(getattr(sys, 'frozen', False))}")
    lines.append(f"exe：{sys.executable}")
    lines.append("")
    lines.append("环境变量：")
    for name in ("USERPROFILE", "HOME", "TEMP", "TMP", "TMPDIR", "AI_PARTNER_HOME",
                 "AI_PARTNER_PORT", "AI_PARTNER_WINDOW", "AI_PARTNER_BROWSER"):
        lines.append(f"  {name} = {os.environ.get(name)!r}")
    lines.append("")
    lines.append(f"程序目录 app_dir()      = {app_dir()}")
    lines.append(f"资源目录 bundle_dir()   = {bundle_dir()}")
    lines.append(f"用户目录 expanduser(~)  = {os.path.expanduser('~')!r}")
    lines.append(f"系统临时目录            = {tempfile.gettempdir()!r}")
    lines.append(f"日志目录 log_dir()      = {log_dir()}")
    try:
        lines.append(f"窗口配置目录            = {_window_profile_dir()}")
    except Exception as exc:  # noqa: BLE001 - 诊断模式要尽量多带信息
        lines.append(f"窗口配置目录            = 失败：{exc}")
    home_browser = os.path.join(os.path.expanduser("~"), ".ai_partner", "browser")
    lines.append(f"建 {home_browser} 的结果 = {_ensure_dir_error(home_browser) or '成功'}")
    lines.append(f"建 {os.path.join(app_dir(), 'browser')} 的结果 = "
                 f"{_ensure_dir_error(os.path.join(app_dir(), 'browser')) or '成功'}")
    lines.append(f"浏览器 find_browser()   = {find_browser() or '（没找到）'}")
    for label, statement in (
        ("import webview", "import webview"),
        ("import clr", "import clr"),
        ("webview.platforms.winforms", "from webview.platforms import winforms"),
    ):
        try:
            exec(statement, {})  # noqa: S102 - 诊断模式，只做导入检查
            lines.append(f"{label} = OK")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"{label} = 失败：{type(exc).__name__}: {exc}")
    lines.append("")
    windows = [w for w in _visible_windows() if w[3].startswith("Chrome_WidgetWin")]
    lines.append(f"可见的浏览器窗口 {len(windows)} 个：")
    for _hwnd, pid, title, cls in windows:
        lines.append(f"  pid={pid} class={cls} title={title!r}")
    text = "\n".join(lines)

    out = (os.environ.get("AI_PARTNER_DIAG_OUT") or "").strip()
    if not out:
        out = os.path.join(log_dir(), "诊断报告.txt")
    try:
        with open(out, "w", encoding="utf-8-sig") as handle:
            handle.write(text)
    except OSError:
        return 3
    print(text)
    return 0


if __name__ == "__main__":
    if os.environ.get("AI_PARTNER_SELFCHECK") == "1":
        raise SystemExit(_self_check())
    if os.environ.get("AI_PARTNER_DIAG") == "1":
        raise SystemExit(_diagnose())
    if "--server-only" in sys.argv:
        # 父进程（同目录下的 exe）用这个参数把"只跑服务、不开窗口"的自己叫起来
        try:
            server_port = int(sys.argv[sys.argv.index("--port") + 1])
        except (ValueError, IndexError):
            server_port = 8501
        _ensure_streams()
        _run_server_only(server_port)
        raise SystemExit(0)
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
