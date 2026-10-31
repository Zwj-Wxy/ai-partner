# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置（onedir 模式，产物在 dist/AI智能伴侣/）

本地打包：
    pyinstaller --noconfirm --clean app.spec
"""

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

# ---------------------------------------------------------------- 资源文件
datas = [
    ("app.py", "."),                 # Streamlit 运行时需要读到真实 .py 文件
    ("resources", "resources"),      # logo 等静态资源
]

binaries = []
hiddenimports = [
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.web.cli",
    # 桌面窗口（WebView2）那一套是运行时才挑后端的，静态分析看不见
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "clr",
    "clr_loader",
    "pythonnet",
]

# 注意：app.py 是当成**数据文件**塞进包里的（Streamlit 运行时用 exec 执行它），
# PyInstaller 的静态分析只看得见 launcher.py，看不到 app.py 里的
# `from openai import OpenAI` —— 不显式收集就会在用户机器上炸
# ModuleNotFoundError: No module named 'openai'。
# Streamlit / Altair / PyDeck 同理，需要连同数据文件、元数据一起打包，
# 否则运行时会报“找不到 streamlit 版本”或缺失前端静态资源。
# pywebview 还必须带上它自带的 WebView2 的 .NET 程序集，否则窗口创建不出来。
for package in ("streamlit", "altair", "pydeck", "openai", "webview"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:  # 该包未安装时跳过
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

for metadata_package in ("streamlit", "altair", "pydeck", "openai", "pandas", "numpy", "packaging",
                         "pywebview", "pythonnet", "clr_loader"):
    try:
        datas += copy_metadata(metadata_package)
    except Exception:
        # streamlit 是硬依赖：它 import 时要用 importlib.metadata 读自己的版本号，
        # 缺了 dist-info 就会 PackageNotFoundError: No package metadata was found for streamlit
        if metadata_package == "streamlit":
            raise
        pass

# 明显用不到的大块头，剔除后体积能小不少
excludes = [
    "tkinter",
    "matplotlib",
    "torch",
    "IPython",
    "notebook",
    "jupyter",
    "pytest",
]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

# 单文件版：AI_PARTNER_ONEFILE=1 pyinstaller ... app.spec
# 好处是真的只有一个 exe（发给别人最省事）；代价是每次启动都要把 200+MB 解压到临时目录，
# 第一次打开要 15~30 秒，也更容易被杀毒软件误报。默认还是 onedir。
ONEFILE = os.environ.get("AI_PARTNER_ONEFILE") == "1"
APP_NAME = "AI智能伴侣-单文件" if ONEFILE else "AI智能伴侣"

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon="assets/app.ico" if os.path.exists("assets/app.ico") else None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,         # 不弹黑窗口，像个正常软件；启动失败由 launcher 弹窗 + 写启动日志.txt
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon="assets/app.ico" if os.path.exists("assets/app.ico") else None,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )
