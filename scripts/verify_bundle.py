# -*- coding: utf-8 -*-
"""
检查 PyInstaller 产物是否"长齐了"——少一样，exe 就打不开或白屏。

用法：
    python scripts/verify_bundle.py                      # 默认检查 dist/AI智能伴侣
    python scripts/verify_bundle.py --dir dist/AI智能伴侣

为什么需要这个脚本：
    PyInstaller 只顺着 import 链自动打包 .py 代码，
    而下面这些"非代码文件"必须显式声明才会进包：
      - streamlit 的 dist-info（importlib.metadata 读版本号用；缺了直接崩）
      - streamlit/static 前端资源（缺了服务起来了也是白屏）
      - app.py、resources/（应用自己的东西）
"""

import argparse
import glob
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (说明, 相对产物目录的路径/通配, 是否必须, 缺了会怎样)
CHECKS = [
    ("主程序 exe", "AI智能伴侣.exe", True, "整个包没有入口"),
    ("应用入口 app.py", "_internal/app.py", True, "启动即报找不到 app.py"),
    ("静态资源 resources/", "_internal/resources", True, "logo 等资源缺失"),
    ("Streamlit 前端静态文件", "_internal/streamlit/static/index.html", True,
     "服务能起来但浏览器白屏（JS/CSS 404）"),
    ("Streamlit 元数据", "_internal/streamlit-*.dist-info", True,
     "启动即崩：PackageNotFoundError: No package metadata was found for streamlit"),
    ("Altair 元数据", "_internal/altair-*.dist-info", False, "图表功能可能报版本错误"),
    ("OpenAI SDK 元数据", "_internal/openai-*.dist-info", False, "一般不影响（SDK 版本号是写死的）"),
]


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(base: str, pattern: str) -> list:
    return sorted(glob.glob(os.path.join(base, pattern)))


def _describe_metadata(path: str) -> str:
    """从 dist-info 里读出版本号，方便对照。"""
    for name in ("METADATA", "PKG-INFO"):
        candidate = os.path.join(path, name)
        if not os.path.exists(candidate):
            continue
        with open(candidate, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
    return "?"


def main() -> int:
    # Windows 控制台默认 GBK/cp1252，直接打印 ✓ 会 UnicodeEncodeError，强制 utf-8 输出
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="检查 PyInstaller 产物完整性")
    parser.add_argument("--dir", default=os.path.join(ROOT, "dist", "AI智能伴侣"),
                        help="产物目录，默认 dist/AI智能伴侣")
    args = parser.parse_args()

    base = os.path.abspath(args.dir)
    print(f"检查目录：{base}")
    if not os.path.isdir(base):
        print("✗ 目录不存在。先跑 pyinstaller --noconfirm --clean app.spec")
        return 1

    required_failed = []
    for label, pattern, required, consequence in CHECKS:
        found = _resolve(base, pattern)
        if found:
            extra = ""
            if pattern.endswith("-*.dist-info"):
                extra = f"（版本 {_describe_metadata(found[0])}）"
            print(f"  ✓ {label}{extra}")
        elif required:
            required_failed.append(label)
            print(f"  ✗ {label} —— 缺了会：{consequence}")
        else:
            print(f"  ⚠ {label} 缺失（可选）")

    # 打包进包里的 app.py 必须是当前源码，否则等于发布了一个旧程序
    bundled_app = os.path.join(base, "_internal", "app.py")
    source_app = os.path.join(ROOT, "app.py")
    if os.path.exists(bundled_app) and os.path.exists(source_app):
        if _sha256(bundled_app) == _sha256(source_app):
            print("  ✓ 包内 app.py 与源码一致")
        else:
            required_failed.append("app.py 与源码不一致")
            print("  ✗ 包内 app.py 与源码不一致 —— 这是旧代码打的包，重新打包")
    else:
        required_failed.append("无法比对 app.py")

    # 批处理文件：LF 行尾或 UTF-8 存盘都会让 cmd 把多行拼成乱码命令，
    # 用户双击就看到一串 "'浠跺彜閲屻€?' 不是内部或外部命令"
    for bat_dir in (os.path.join(ROOT, "packaging"), base):
        for path in sorted(glob.glob(os.path.join(bat_dir, "*.bat"))):
            name = os.path.relpath(path, ROOT)
            raw = open(path, "rb").read()
            problems = []
            if raw.count(b"\r\n") != raw.count(b"\n"):
                problems.append("行尾不是 CRLF")
            if raw.startswith(b"\xef\xbb\xbf"):
                problems.append("带了 UTF-8 BOM")
            try:
                raw.decode("gbk")
            except UnicodeDecodeError:
                problems.append("不是 GBK 编码")
            if problems:
                required_failed.append(f"{name}（{'、'.join(problems)}）")
                print(f"  ✗ {name} —— {'、'.join(problems)}；cmd 里会整段乱码")
            else:
                print(f"  ✓ {name}（GBK + CRLF）")

    print()
    if required_failed:
        print(f"结论：不通过，缺 {len(required_failed)} 项 —— {'、'.join(required_failed)}")
        print("这种包发出去，用户双击就是一个一闪而过的黑窗口。")
        return 1

    print("结论：通过。所有必需文件都在，可以发布。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
