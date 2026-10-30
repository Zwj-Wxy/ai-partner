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
    st.stop = lambda *a, **kw: None
    return st


def main() -> None:
    sys.modules["streamlit"] = _make_fake_streamlit()

    # 假的 openai（避免真的去构造客户端）
    openai_mod = types.ModuleType("openai")

    class _OpenAI:
        def __init__(self, *a, **kw):
            self.api_key = kw.get("api_key")

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

    print("OK: app.py 冒烟测试通过")
    print(f"    sessions dir -> {app.SESSIONS_DIR}")
    print(f"    model={app.MODEL_NAME}  base_url={app.BASE_URL}")
    shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
