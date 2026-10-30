# -*- coding: utf-8 -*-
"""
冒烟测试：用假的 streamlit 模块把 app.py 完整"跑"一遍模块级代码。

目的不是测 UI，而是保证：
  * app.py 没有语法错误 / 拼写错误；
  * 路径、会话目录、密钥初始化这些"一定会执行"的逻辑不会抛异常。

用法： python tests/test_smoke.py
"""

import os
import shutil
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 让 sessions / config 落在仓库内的临时目录（有些环境禁止写系统 TEMP），跑完删除
_TMP = os.path.join(ROOT, ".smoke_tmp")
shutil.rmtree(_TMP, ignore_errors=True)
os.environ["AI_PARTNER_HOME"] = _TMP
os.environ["DEEPSEEK_API_KEY"] = "sk-test-key"


class _State(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _Block:
    """假的可当上下文管理器 / 可 write 的占位对象。"""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write(self, *args, **kwargs):
        return self

    def text(self, *args, **kwargs):
        return self


class _Columns(list):
    def __iter__(self):
        return super().__iter__()


def _make_fake_streamlit():
    st = types.ModuleType("streamlit")
    st.session_state = _State(current_session="")
    st.secrets = {}
    st.sidebar = _Block()
    st.columns = lambda spec, **kw: _Columns(_Block() for _ in spec)
    st.expander = lambda *a, **kw: _Block()
    st.chat_message = lambda *a, **kw: _Block()

    for name in (
        "set_page_config", "title", "logo", "subheader", "text", "divider",
        "caption", "write", "markdown", "error", "warning", "success", "info",
        "rerun", "empty", "container",
    ):
        setattr(st, name, lambda *a, **kw: _Block())

    st.button = lambda *a, **kw: False
    st.checkbox = lambda *a, **kw: False
    st.text_input = lambda *a, **kw: kw.get("value", "")
    st.text_area = lambda *a, **kw: kw.get("value", "")
    st.chat_input = lambda *a, **kw: None   # 不触发对话分支
    st.write_stream = lambda gen, **kw: "".join(gen)
    st.stop = lambda *a, **kw: None
    return st


def main() -> None:
    st_mod = _make_fake_streamlit()
    sys.modules["streamlit"] = st_mod

    # 假的 openai（避免真的去构造客户端 / 真的发请求）
    openai_mod = types.ModuleType("openai")

    fake_models = ["deepseek-chat", "deepseek-reasoner"]
    fail = {"on": False}

    class _Model:
        def __init__(self, mid):
            self.id = mid

    class _ModelsAPI:
        def list(self):
            if fail["on"]:
                raise RuntimeError("Error code: 401 - Unauthorized")
            return types.SimpleNamespace(data=[_Model(m) for m in fake_models])

    class _OpenAI:
        def __init__(self, *a, **kw):
            self.api_key = kw.get("api_key")
            self.models = _ModelsAPI()

    openai_mod.OpenAI = _OpenAI
    sys.modules["openai"] = openai_mod

    import app  # noqa: F401  导入即执行模块级代码

    assert app.st.session_state.nick_name, "nick_name 未初始化"
    assert app.st.session_state.nature, "nature 未初始化"
    assert app.st.session_state.messages == [], "messages 未初始化"
    assert os.path.isdir(app.SESSIONS_DIR), "会话目录未创建"
    assert app.SESSIONS_DIR.startswith(_TMP), f"会话目录跑偏了: {app.SESSIONS_DIR}"
    assert app.BASE_URL and app.MODEL_NAME

    # 会话读写往返
    app.st.session_state.messages = [{"role": "user", "content": "在吗"}]
    app.save_session()
    assert app.st.session_state.current_session in app.load_sessions(), "会话未保存"
    app.delete_session(app.st.session_state.current_session)
    assert app.st.session_state.current_session not in app.load_sessions(), "会话未删除"

    # ---- 上下文截断 & 流式解析 ----
    keep = list(app.st.session_state.messages)
    app.st.session_state.messages = [{"role": "user", "content": str(i)} for i in range(50)]
    recent = app._recent_messages()
    assert len(recent) == min(app.CONTEXT_LIMIT, 50), "上下文截断条数不对"
    assert recent[-1]["content"] == "49", "截断后必须保留最新消息"
    app.st.session_state.messages = keep

    chunk = lambda txt=None, choices=True: types.SimpleNamespace(   # noqa: E731
        choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content=txt))] if choices else []
    )
    fake_stream = [chunk(choices=False), chunk(None), chunk("嗨"), chunk("呀")]
    assert list(app._stream_text(fake_stream)) == ["嗨", "呀"], "流式文本解析不对"

    kept = []
    list(app._stream_text([chunk("半"), chunk("截")], kept))
    assert kept == ["半", "截"], "keep 应记下已吐出的片段（断线时用来保住半截回复）"

    # ---- API 设置：密钥状态 / 测试连接 / 记住到本机 ----
    assert app._mask("") == "未配置"
    assert app._mask("sk-1234567890abcdef").startswith("sk-123")      # 只露头
    assert app._mask("sk-1234567890abcdef").endswith("cdef")           # 只露尾

    ok, msg = app.test_connection("", "deepseek-chat")
    assert not ok and "API Key" in msg, "空密钥应直接拒绝"

    ok, msg = app.test_connection("sk-test", "deepseek-chat")
    assert ok and "deepseek-chat" in msg, f"正常连接判断有误: {msg}"

    ok, msg = app.test_connection("sk-test", "deepseek-flash")
    assert ok and "⚠️" in msg, "模型名不在可用列表时应当给出警告"

    fail["on"] = True
    ok, msg = app.test_connection("sk-bad", "deepseek-chat")
    assert not ok and "连接失败" in msg, f"失败时应报错: {msg}"
    fail["on"] = False

    # 勾选"记住到本机" → 落盘；取消 → 删除
    app.st.session_state.model_name = "deepseek-chat"
    app._sync_config(True)
    assert os.path.exists(app.CONFIG_FILE), "勾选记住后 config.json 未生成"
    saved = app._read_config()
    assert saved["api_key"] == app.st.session_state.api_key
    assert saved["model"] == "deepseek-chat"
    app._sync_config(False)
    assert not os.path.exists(app.CONFIG_FILE), "取消记住后 config.json 未删除"

    # ---- 第二次导入：没有环境变量，覆盖侧边栏"手动输入密钥"那条分支 ----
    os.environ.pop("DEEPSEEK_API_KEY", None)
    sys.modules.pop("app", None)
    st_mod.session_state = _State(current_session="")   # 干净的界面状态
    import app as app_ui  # noqa: F401

    assert app_ui.st.session_state.api_key == "", "无来源时密钥应为空"
    assert app_ui._from_config() == "", "此时不应读到本机配置"
    assert app_ui.st.session_state.model_name, "模型名未初始化"
    assert not os.path.exists(app_ui.CONFIG_FILE), "未勾选记住时不该写 config.json"

    # 模拟：用户粘贴了密钥 + 勾选"记住到本机"
    app_ui.st.session_state.api_key = "sk-manual-1234567890"
    app_ui.st.session_state.model_name = "deepseek-chat"
    app_ui._sync_config(True)
    assert app_ui._from_config() == "sk-manual-1234567890", "记住到本机没生效"
    assert app_ui._read_config().get("model") == "deepseek-chat"

    # 模拟：用户把输入框清空（仍然勾着记住）→ 本机不能留旧密钥
    app_ui.st.session_state.api_key = ""
    app_ui._sync_config(True)
    assert not os.path.exists(app_ui.CONFIG_FILE), "清空密钥后 config.json 应被删除"

    print("OK: app.py 冒烟测试通过")
    print(f"    sessions dir -> {app.SESSIONS_DIR}")
    print(f"    model={app.MODEL_NAME}  base_url={app.BASE_URL}")
    shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
