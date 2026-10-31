# -*- coding: utf-8 -*-
"""把 packaging/*.bat 统一成「GBK 编码 + CRLF 行尾」。

为什么必须这样做：
  1. cmd.exe 只认 CRLF。LF-only 的 .bat 会被当成一条超长命令，
     于是出现 "'浠跺彜閲屻€?' 不是内部或外部命令" 这种乱码报错。
  2. 中文 Windows 的 cmd 默认代码页是 936(GBK)。UTF-8 的中文会被按 GBK 解码成乱码，
     所以 .bat 里的中文要用 GBK 存盘，并在开头 chcp 936 锁死代码页。

用法： python scripts/fix_bat_encoding.py
"""

import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def convert(path: str) -> bool:
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        print(f"  跳过（认不出编码）：{path}")
        return False

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("chcp 65001", "chcp 936")
    lines = text.split("\n")

    # 保证开头有一句 chcp 936，避免用户改过控制台代码页
    head = [ln for ln in lines[:3] if ln.strip().lower().startswith("@echo") or
            ln.strip().lower().startswith("chcp")]
    if not any("chcp 936" in ln for ln in head):
        insert_at = 1 if lines and lines[0].strip().lower().startswith("@echo") else 0
        lines.insert(insert_at, "chcp 936 >nul")

    data = "\r\n".join(lines)
    if not data.endswith("\r\n"):
        data += "\r\n"
    open(path, "wb").write(data.encode("gbk"))
    print(f"  已转换：{path}")
    return True


def main() -> int:
    files = sorted(glob.glob(os.path.join(ROOT, "packaging", "*.bat")))
    files += sorted(glob.glob(os.path.join(ROOT, "scripts", "*.bat")))
    if not files:
        print("没有找到 .bat 文件")
        return 1
    for f in files:
        convert(f)
    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
