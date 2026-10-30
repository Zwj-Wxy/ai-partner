# -*- coding: utf-8 -*-
"""
AI 智能伴侣 —— 基于 Streamlit + DeepSeek 的拟人化聊天伴侣

运行方式：
    源码运行：  streamlit run app.py
    打包运行：  python launcher.py（或双击 AI智能伴侣.exe）

环境变量（可选，优先级最高）：
    DEEPSEEK_API_KEY     DeepSeek 接口密钥
    DEEPSEEK_BASE_URL    接口地址，默认 https://api.deepseek.com
    DEEPSEEK_MODEL       模型名，默认 deepseek-flash
"""

import os
import sys
import json
from datetime import datetime

import streamlit as st
from openai import OpenAI

APP_TITLE = "AI智能伴侣"
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
MODEL_NAME = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash").strip()


# --------------------------------------------------------------------------
# 路径处理：源码运行 与 PyInstaller 打包运行 都指向正确的位置
# --------------------------------------------------------------------------
def app_root() -> str:
    """程序所在目录：源码运行时是项目根目录，打包运行时是 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def bundle_dir() -> str:
    """打包后资源的解包目录（PyInstaller 的 sys._MEIPASS）。"""
    return getattr(sys, "_MEIPASS", app_root())


def resource_path(relative_path: str) -> str:
    """定位随程序分发的静态资源，例如 resources/logo.png。"""
    for base in (bundle_dir(), app_root(), os.getcwd()):
        candidate = os.path.join(base, relative_path)
        if os.path.exists(candidate):
            return candidate
    return relative_path


def _pick_sessions_dir() -> str:
    """会话保存目录：优先程序目录，不可写（如装在 Program Files）时退到用户目录。"""
    for base in (app_root(), os.path.join(os.path.expanduser("~"), ".ai_partner")):
        folder = os.path.join(base, "sessions")
        try:
            os.makedirs(folder, exist_ok=True)
            probe = os.path.join(folder, ".writable")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("")
            os.remove(probe)
            return folder
        except OSError:
            continue
    return "sessions"


CONFIG_FILE = os.path.join(app_root(), "config.json")
SESSIONS_DIR = _pick_sessions_dir()


# --------------------------------------------------------------------------
# 页面配置（必须是第一个 Streamlit 调用）
# --------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------
# API 密钥：环境变量 > Streamlit secrets > 本机 config.json > 侧边栏手动输入
# --------------------------------------------------------------------------
def _from_secrets(name: str) -> str:
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return ""


def _from_config() -> str:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return str(json.load(f).get("api_key", "")).strip()
    except (OSError, ValueError):
        return ""


def _save_config(api_key: str) -> None:
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"api_key": api_key}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


if "api_key" not in st.session_state:
    st.session_state.api_key = (
        os.environ.get("DEEPSEEK_API_KEY", "").strip()
        or _from_secrets("DEEPSEEK_API_KEY")
        or _from_config()
    )


# --------------------------------------------------------------------------
# 会话读写
# --------------------------------------------------------------------------
def generate_session_name() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def session_file(session_name: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{session_name}.json")


def save_session() -> None:
    """把当前会话写入 sessions/<会话名>.json（空会话不落盘）。"""
    if not st.session_state.get("messages"):
        return
    session_data = {
        "nick_name": st.session_state.nick_name,
        "nature": st.session_state.nature,
        "current_session": st.session_state.current_session,
        "messages": st.session_state.messages,
    }
    try:
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        with open(session_file(st.session_state.current_session), "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=4)
    except OSError as exc:
        st.error(f"会话保存失败：{exc}")


def load_sessions() -> list:
    """列出 sessions 目录下所有会话名，最新的排前面。"""
    session_list = []
    try:
        for filename in os.listdir(SESSIONS_DIR):
            if filename.endswith(".json"):
                session_list.append(filename[:-5])
    except OSError:
        pass
    session_list.sort(reverse=True)
    return session_list


def load_session(session_name: str) -> None:
    try:
        with open(session_file(session_name), "r", encoding="utf-8") as f:
            session_data = json.load(f)
        st.session_state.nick_name = session_data["nick_name"]
        st.session_state.nature = session_data["nature"]
        st.session_state.current_session = session_name
        st.session_state.messages = session_data["messages"]
    except Exception:
        st.error("会话数据加载失败！")


def delete_session(session_name: str) -> None:
    try:
        path = session_file(session_name)
        if os.path.exists(path):
            os.remove(path)
        if session_name == st.session_state.current_session:
            st.session_state.messages = []
            st.session_state.current_session = generate_session_name()
    except Exception:
        st.error("会话数据删除失败！")


# --------------------------------------------------------------------------
# 系统提示词
# --------------------------------------------------------------------------
system_prompt = """
       你叫 %s ，现在是用户的真实伴侣，请完全代入伴侣角色。
       规则：
       1. 每次只回1条消息
       2. 禁止任何场景或状态描述性文字
       3. 匹配用户的语言
       4. 回复简短，像微信聊天一样
       5. 有需要的话可以用❤️🌸等emoji表情
       6. 用符合伴侣性格的方式对话
       7. 回复的内容，要充分体现伴侣的性格特征
       伴侣性格：
       - %s
       你必须严格遵守上述规则来回复用户。
    """


# --------------------------------------------------------------------------
# 初始化会话状态
# --------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "nick_name" not in st.session_state:
    st.session_state.nick_name = "小甜甜"

if "nature" not in st.session_state:
    st.session_state.nature = "活泼开朗的东北姑娘"

if "current_session" not in st.session_state:
    st.session_state.current_session = generate_session_name()


# --------------------------------------------------------------------------
# 标题与 Logo
# --------------------------------------------------------------------------
st.title(APP_TITLE)

logo = resource_path("resources/logo.png")
if os.path.exists(logo):
    try:
        st.logo(logo)
    except Exception:
        pass


# --------------------------------------------------------------------------
# 侧边栏
# --------------------------------------------------------------------------
with st.sidebar:
    st.subheader("AI控制面板")

    if st.button("新建会话", width="stretch", icon="🚀"):
        save_session()
        st.session_state.messages = []
        st.session_state.current_session = generate_session_name()
        st.rerun()

    st.text("会话历史")
    for session in load_sessions():
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                session,
                width="stretch",
                icon="⌨️",
                key=f"load_{session}",
                type="primary" if session == st.session_state.current_session else "secondary",
            ):
                load_session(session)
                st.rerun()
        with col2:
            if st.button("", width="stretch", icon="✖️", key=f"delete_{session}"):
                delete_session(session)
                st.rerun()

    st.divider()

    st.subheader("伴侣信息")
    nick_name = st.text_input("昵称", placeholder="请输入昵称", value=st.session_state.nick_name)
    if nick_name:
        st.session_state.nick_name = nick_name

    nature = st.text_area("性格", placeholder="请输入性格", value=st.session_state.nature)
    if nature:
        st.session_state.nature = nature

    st.divider()

    with st.expander("🔑 API 密钥设置", expanded=not st.session_state.api_key):
        typed_key = st.text_input(
            "DeepSeek API Key",
            value=st.session_state.api_key,
            type="password",
            placeholder="sk-...",
            help="在 https://platform.deepseek.com 申请；只保存在你自己的电脑上。",
        )
        remember = st.checkbox("记住密钥（保存到本机 config.json）", value=bool(_from_config()))
        if typed_key.strip() != st.session_state.api_key:
            st.session_state.api_key = typed_key.strip()
            if remember and st.session_state.api_key:
                _save_config(st.session_state.api_key)
        st.caption(f"接口地址：{BASE_URL}　模型：{MODEL_NAME}")


# --------------------------------------------------------------------------
# 展示历史消息
# --------------------------------------------------------------------------
st.caption(f"会话名称：{st.session_state.current_session}")
for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])


# --------------------------------------------------------------------------
# 消息输入与流式回复
# --------------------------------------------------------------------------
prompt = st.chat_input("请输入您的问题")
if prompt:
    if not st.session_state.api_key:
        st.chat_message("user").write(prompt)
        st.error("还没有配置 DeepSeek API Key：请在左侧「🔑 API 密钥设置」里填写后再发送。")
        st.stop()

    st.chat_message("user").write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    try:
        client = OpenAI(api_key=st.session_state.api_key, base_url=BASE_URL)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt % (st.session_state.nick_name, st.session_state.nature),
                },
                *st.session_state.messages,
            ],
            stream=True,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )

        response_message = st.empty()
        full_response = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
                response_message.write(full_response)
    except Exception as exc:
        st.error(f"调用大模型失败：{exc}")
        save_session()
        st.stop()

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    save_session()
