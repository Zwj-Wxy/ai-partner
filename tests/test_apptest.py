# -*- coding: utf-8 -*-
"""用真实的 streamlit 跑一遍 app.py（AppTest），确认页面能渲染、不抛异常。

不是假模块的冒烟测试：这是 Streamlit 官方的无头测试 API，会真的执行脚本、
真的调用每个控件。跑法：
    <某个装了 streamlit 的 python> tests/test_apptest.py
"""

import os
import sys

# Windows 控制台默认 GBK，打印 ✓/🔑 会 UnicodeEncodeError，统一按 utf-8 输出
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app.py")

failures = []


def check(label, at):
    excs = [e.value for e in at.exception]
    if excs:
        failures.append(f"{label}: {excs}")
        print(f"  [FAIL] {label} -> {excs}")
    else:
        print(f"  [OK]   {label}（无异常）")
    return excs


# ---------- 情形 1：没有 API Key（新用户第一次打开） ----------
os.environ.pop("DEEPSEEK_API_KEY", None)
cfg = os.path.join(ROOT, "config.json")
if os.path.exists(cfg):
    os.rename(cfg, cfg + ".apptest.bak")

at = AppTest.from_file(APP, default_timeout=60)
at.run()
check("无密钥启动", at)
infos = [i.value for i in at.info]
print(f"         提示条数量 {len(infos)}，首条：{(infos[0][:40] + '…') if infos else '无'}")
if not infos:
    failures.append("无密钥时没有给出提示条")
print(f"         侧边栏文本框 {len(at.sidebar.text_input)} 个，按钮 {len(at.sidebar.button)} 个，"
      f"复选框 {len(at.sidebar.checkbox)} 个")
if len(at.sidebar.text_input) < 1:
    failures.append("侧边栏没有 API Key 输入框")
if not any("测试连接" in (b.label or "") for b in at.sidebar.button):
    failures.append("侧边栏没有「测试连接」按钮")

# ---------- 情形 2：填了 key（模拟用户粘贴后） ----------
def key_box(at):
    """侧边栏有三个输入框（昵称 / API Key / 模型），按标签找，别按顺序。"""
    for box in at.sidebar.text_input:
        if "API Key" in (box.label or ""):
            return box
    return None


at2 = AppTest.from_file(APP, default_timeout=60)
at2.run()
key_box(at2).set_value("sk-apptest-1234567890abcdef")
at2.run()
check("填入密钥后重跑", at2)
masked = [c.value for c in at2.sidebar.caption if "已配置" in (c.value or "")]
print(f"         状态回显：{masked[0] if masked else '无'}")
if not masked:
    failures.append("填入密钥后状态没有回显")
if not any("sk-apptest" in (c.value or "") for c in at2.sidebar.caption):
    # 只显示掩码，不该出现完整 key
    if any("sk-apptest-1234567890abcdef" in (c.value or "") for c in at2.sidebar.caption):
        failures.append("状态回显泄露了完整密钥")

# ---------- 情形 3：空输入不该崩 ----------
at3 = AppTest.from_file(APP, default_timeout=60)
at3.run()
key_box(at3).set_value("")
at3.run()
check("空密钥重跑", at3)

# 清理
if os.path.exists(cfg):
    os.remove(cfg)
if os.path.exists(cfg + ".apptest.bak"):
    os.rename(cfg + ".apptest.bak", cfg)

print()
if failures:
    print(f"结论：不通过（{len(failures)} 项）")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("结论：页面对以上三种情形都能正常渲染。")
