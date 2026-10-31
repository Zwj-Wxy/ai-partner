# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置（onedir 模式，产物在 dist/AI智能伴侣/）

本地打包：
    pyinstaller --noconfirm --clean app.spec
"""

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
]

# Streamlit / Altair 需要连同数据文件、元数据一起打包，
# 否则运行时会报 “找不到 streamlit 版本” 或缺失前端静态资源。
for package in ("streamlit", "altair", "pydeck"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:  # 该包未安装时跳过
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

for metadata_package in ("streamlit", "altair", "pydeck", "openai", "pandas", "numpy", "packaging"):
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI智能伴侣",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # 保留控制台，出错时能看到日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,             # 想换图标：放一个 app.ico 到根目录，改成 "app.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AI智能伴侣",
)
