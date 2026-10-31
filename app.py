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
    AI_PARTNER_CONTEXT   每次请求带多少条历史消息，默认 20（设 0 表示不截断）
    AI_PARTNER_HOME      数据目录（sessions/ 与 config.json 放哪），默认跟程序走
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


def _env_int(name: str, default: int) -> int:
    """读一个整数环境变量，写错了就安静地用默认值。"""
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


# 每次请求最多带多少条历史消息：聊得越久，全部塞给模型会越来越慢、越来越贵，
# 而且迟早超过模型的上下文上限直接报 400。默认只带最近 20 条。
CONTEXT_LIMIT = max(0, _env_int("AI_PARTNER_CONTEXT", 20))
# 界面上最多直接渲染多少条历史（更早的收进折叠区），避免长会话首屏卡顿
HISTORY_RENDER_LIMIT = 60


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


def _data_home() -> str:
    """数据目录：默认跟着程序走；设置 AI_PARTNER_HOME 可改到别处（绿色版/便携模式）。"""
    return (os.environ.get("AI_PARTNER_HOME") or "").strip() or app_root()


def _pick_sessions_dir() -> str:
    """会话保存目录：优先程序目录，不可写（如装在 Program Files）时退到用户目录。"""
    for base in (_data_home(), os.path.join(os.path.expanduser("~"), ".ai_partner")):
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


CONFIG_FILE = os.path.join(_data_home(), "config.json")
SESSIONS_DIR = _pick_sessions_dir()

# 窗口/标签页图标：有图就用图（独立窗口的任务栏图标就是它），没有就退回 emoji
_ICON_FILE = resource_path(os.path.join("resources", "app-icon.png"))
PAGE_ICON = _ICON_FILE if os.path.exists(_ICON_FILE) else "🤖"


# --------------------------------------------------------------------------
# 页面配置（必须是第一个 Streamlit 调用）
# --------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# 纯外观微调：正文收窄居中（宽屏上别拉成一整行）、气泡圆角。改坏了也只是难看，不影响功能。
st.markdown(
    """
    <style>
      .block-container { max-width: 880px; padding-top: 2.2rem; }
      [data-testid="stChatMessage"] { border-radius: 14px; }
      [data-testid="stChatMessage"] p { line-height: 1.75; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# API 密钥：环境变量 > Streamlit secrets > 本机 config.json > 侧边栏手动输入
# --------------------------------------------------------------------------
def _from_secrets(name: str) -> str:
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return ""


def _read_config() -> dict:
    """读本机 config.json（保存密钥和模型名，出任何错都当成空配置）。"""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_config(**updates) -> None:
    """把设置合并写回 config.json；空值会被删掉，避免留下半截配置。"""
    data = _read_config()
    data.update(updates)
    data = {k: v for k, v in data.items() if v not in ("", None)}
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if os.name == "posix":
            os.chmod(CONFIG_FILE, 0o600)  # 只有自己能读
    except OSError:
        pass


def _clear_config() -> None:
    """删除本机保存的密钥（"不再记住"时调用）。"""
    try:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
    except OSError:
        pass


def _from_config() -> str:
    return str(_read_config().get("api_key", "")).strip()


def _mask(key: str) -> str:
    """只显示密钥的头尾，方便确认"填的是哪一把"，又不至于泄露。"""
    if not key:
        return "未配置"
    return f"{key[:6]}…{key[-4:]}" if len(key) > 12 else "已配置"


def test_connection(api_key: str, model: str) -> tuple:
    """做一次最轻量的调用，确认「密钥 + 网络 + 模型名」三件事都对。"""
    if not api_key:
        return False, "请先填入 API Key。"
    try:
        client = OpenAI(api_key=api_key, base_url=BASE_URL)
        models = [m.id for m in client.models.list().data]
    except Exception as exc:
        return False, f"连接失败：{exc}"

    msg = "连接正常 ✅"
    if models:
        msg += f"，可用模型：{'、'.join(models[:6])}"
        if model not in models:
            msg += f"\n\n⚠️ 当前模型 `{model}` 不在上面列表里，调用大概率失败，建议换成 `{models[0]}`。"
    return True, msg


def _sync_config(remember: bool) -> None:
    """按复选框状态把当前密钥/模型写入或清出 config.json（只在有变化时写盘）。"""
    current = _read_config()
    if remember and st.session_state.api_key:
        if (current.get("api_key") != st.session_state.api_key
                or current.get("model") != st.session_state.model_name):
            _write_config(api_key=st.session_state.api_key, model=st.session_state.model_name)
    else:
        # 没勾选，或者把密钥清空了 —— 都不该在本机留下东西
        _clear_config()


_cfg = _read_config()
if "api_key" not in st.session_state:
    st.session_state.api_key = (
        os.environ.get("DEEPSEEK_API_KEY", "").strip()
        or _from_secrets("DEEPSEEK_API_KEY")
        or str(_cfg.get("api_key", "")).strip()
    )
if "model_name" not in st.session_state:
    st.session_state.model_name = str(_cfg.get("model", "")).strip() or MODEL_NAME


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

if not st.session_state.api_key:
    st.info(
        "还没配置 DeepSeek API Key：到左侧 **🔑 API 设置** 里粘贴密钥"
        "（[点这里申请](https://platform.deepseek.com/api_keys)），"
        "填完点「🔍 测试连接」确认可用，就能开始聊天了。"
    )


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

    st.subheader("🔑 API 设置")

    env_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    secret_key = _from_secrets("DEEPSEEK_API_KEY")
    locked = bool(env_key or secret_key)   # 环境变量 / secrets 提供时，界面只读
    remember = False

    if locked:
        st.success(f"密钥已由{'系统环境变量' if env_key else ' Streamlit secrets'}提供，自动生效，无需填写。")
    else:
        typed_key = st.text_input(
            "DeepSeek API Key",
            value=st.session_state.api_key,
            type="password",
            placeholder="sk-...（粘贴后回车）",
            help="在 https://platform.deepseek.com/api_keys 申请；只保存在你自己的电脑上。",
        ).strip()
        if typed_key != st.session_state.api_key:
            st.session_state.api_key = typed_key

        remember = st.checkbox(
            "记住到本机（下次启动免输入）",
            value=bool(_from_config()),
            help="勾选后明文写入程序目录的 config.json；取消勾选就等于删除该文件。",
        )

    if st.session_state.api_key:
        st.caption(f"状态：✅ 已配置　{_mask(st.session_state.api_key)}")
    else:
        st.caption("状态：⚠️ 未配置，聊天前必须先填")

    # 模型放在「测试连接」之前，这样改完名字顺手一测就是新模型的真实结果
    model_input = st.text_input(
        "模型",
        value=st.session_state.model_name,
        help="DeepSeek 官方可用：deepseek-chat、deepseek-reasoner。名字写错会直接报 400。",
    ).strip()
    if model_input and model_input != st.session_state.model_name:
        st.session_state.model_name = model_input

    if st.button("🔍 测试连接", width="stretch"):
        ok, msg = test_connection(st.session_state.api_key, st.session_state.model_name)
        (st.success if ok else st.error)(msg)

    st.caption(f"接口地址：{BASE_URL}")
    st.caption(
        f"上下文：每次带最近 {CONTEXT_LIMIT} 条消息"
        if CONTEXT_LIMIT
        else "上下文：不截断（长会话会更慢、更贵）"
    )

    # 放在最后同步：这样"改了模型但没改密钥"也能一起存进去
    if not locked:
        _sync_config(remember)


# --------------------------------------------------------------------------
# 展示历史消息
# --------------------------------------------------------------------------
st.caption(f"会话名称：{st.session_state.current_session}")

_history = st.session_state.messages
if len(_history) > HISTORY_RENDER_LIMIT:
    _older = _history[:-HISTORY_RENDER_LIMIT]
    with st.expander(f"更早的 {len(_older)} 条消息（点击展开）"):
        for message in _older:
            st.chat_message(message["role"]).write(message["content"])
    _history = _history[-HISTORY_RENDER_LIMIT:]

for message in _history:
    st.chat_message(message["role"]).write(message["content"])


# --------------------------------------------------------------------------
# 消息输入与流式回复
# --------------------------------------------------------------------------
def _recent_messages() -> list:
    """只把最近 CONTEXT_LIMIT 条历史发给模型（含刚刚发出的这条）。"""
    messages = st.session_state.messages
    if CONTEXT_LIMIT <= 0:
        return messages
    return messages[-CONTEXT_LIMIT:]


def _stream_text(response, keep=None):
    """把 OpenAI 的流式响应拆成纯文本块；顺带丢掉只有思考过程、没有正文的空块。

    传了 keep（list）就把吐出去的每段也存一份：万一流到一半断线，
    已经收到的半截回复还能留在会话里，而不是凭空消失。
    """
    try:
        for chunk in response:
            if not chunk.choices:
                continue
            piece = getattr(chunk.choices[0].delta, "content", None)
            if piece:
                if keep is not None:
                    keep.append(piece)
                yield piece
    except Exception as exc:  # 流到一半失败：报出来，已吐出来的字留在界面上
        st.error(f"回复中断：{exc}")


prompt = st.chat_input("请输入您的问题")
if prompt:
    if not st.session_state.api_key:
        st.chat_message("user").write(prompt)
        st.error("还没有配置 DeepSeek API Key：请在左侧「🔑 API 设置」里填写后再发送。")
        st.stop()

    st.chat_message("user").write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    full_response = ""
    try:
        client = OpenAI(
            api_key=st.session_state.api_key,
            base_url=BASE_URL,
            timeout=60,      # 别让网络卡住时界面一直转圈
            max_retries=2,   # 偶发的 429 / 连接重置，SDK 自己重试
        )
        response = client.chat.completions.create(
            model=st.session_state.model_name,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt % (st.session_state.nick_name, st.session_state.nature),
                },
                *_recent_messages(),
            ],
            stream=True,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
    except Exception as exc:
        # 请求阶段就失败（密钥、余额、模型名、网络）——不要把报错塞进她的气泡里
        st.error(f"调用大模型失败：{exc}\n\n可以点左侧的「🔍 测试连接」先确认密钥和网络是否正常。")
        save_session()
        st.stop()

    with st.chat_message("assistant"):
        collected: list = []
        # write_stream 会一段一段地吐字，不用每来一个字就整段重绘
        full_response = st.write_stream(_stream_text(response, collected)) or ""
        if not str(full_response).strip():
            full_response = "".join(collected)

    if not str(full_response).strip():
        full_response = "（这条没收到内容，可能是网络中断或额度不足，再说一次试试？）"

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    save_session()
