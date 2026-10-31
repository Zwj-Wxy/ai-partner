# AI 智能伴侣

<p align="center">
  <img src="docs/banner.png" alt="AI 智能伴侣" width="100%">
</p>

> 一个可以"住"进你电脑的 AI 伴侣：基于 **Streamlit + DeepSeek** 的拟人化聊天应用。
> 支持自定义昵称与性格、多会话管理、本地存档；可一键打包成 Windows 绿色版 exe，也可直接部署成在线网页。

---

## ✨ 功能特性

| 特性 | 说明 |
| --- | --- |
| 💬 拟人化对话 | 自定义昵称 + 性格，模型全程代入伴侣角色，回复短、像微信聊天 |
| ⚡ 流式输出 | 回复逐字显示，不用干等 |
| 🗂 多会话管理 | 新建 / 切换 / 删除会话，自动保存到本地 `sessions/*.json` |
| 🔑 密钥自管理 | 环境变量、界面输入、本地 `config.json` 三种方式，密钥不出本机 |
| 📦 一键打包 | `pyinstaller --noconfirm --clean app.spec` 得到绿色版 exe |
| 🚀 自动发布 | 推送 tag，GitHub Actions 自动打包并上传 Release |

## 🎬 三种运行方式

### 方式一：在线网页版（最省事，不用装任何东西）

把本仓库导入 [Streamlit Community Cloud](https://share.streamlit.io) 即可得到一个公网网址，手机也能打开。
详见下文 [部署成在线网页版](#-部署成在线网页版)。

### 方式二：下载 Windows 绿色版

到本仓库的 **Releases** 页面下载 `AI-Partner-Windows-x64.zip`：

1. 解压到任意目录（路径别带空格更稳）；
2. 双击 `启动AI智能伴侣.bat`，浏览器会自动打开 `http://localhost:8501`；
3. 第一次运行在左侧「🔑 API 设置」里填入 DeepSeek API Key 即可开聊。

> 程序完全离线运行在你的电脑上，聊天记录保存在同目录的 `sessions/` 文件夹。

### 方式三：从源码运行（开发者）

```powershell
git clone https://github.com/YOUR_NAME/AI-Partner.git
cd AI-Partner
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DEEPSEEK_API_KEY = "sk-你的密钥"   # 也可以运行后在界面里填
streamlit run app.py
```

## 🔑 配置 API 密钥

**最省事的做法**：打开应用 → 左侧边栏「🔑 API 设置」→ 粘贴 `sk-...` 回车 → 点「🔍 测试连接」看到绿色的"连接正常"即可。
勾选「记住到本机」后，下次启动不用再填；取消勾选会自动删掉本机存的那份。

密钥优先级（从高到低）：

1. **环境变量** `DEEPSEEK_API_KEY`（一旦存在，界面里的输入框会变只读，避免两处互相覆盖）
2. **Streamlit Secrets**（仅在线部署时）：`.streamlit/secrets.toml` 中写 `DEEPSEEK_API_KEY = "sk-..."`，或在 Streamlit Cloud 的 App settings → Secrets 里粘贴
3. **本地 `config.json`**：界面里勾选"记住到本机"后生成，形如 `{"api_key": "sk-...", "model": "deepseek-chat"}`
4. **界面手动输入**：仅当前会话有效，关掉就没了

其他可调项：接口地址 `DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）、模型 `DEEPSEEK_MODEL`；
模型名也可以直接在侧边栏「模型」里改（DeepSeek 官方可用 `deepseek-chat`、`deepseek-reasoner`，
写错名字接口会直接返回 400，所以「测试连接」会顺手告诉你当前模型在不在可用列表里）。

> ⚠️ **密钥就是钱**。`config.json`、`.streamlit/secrets.toml` 已被 `.gitignore` 排除，**永远不要**把它们提交到 GitHub。
> `config.json` 在 Windows 上是明文 JSON，别把这台机器上的这个文件发给别人。

### 速度与花费的几个默认值

| 项目 | 默认 | 说明 |
| --- | --- | --- |
| 每次带多少条历史 `AI_PARTNER_CONTEXT` | 20 | 只发最近 20 条。全量发送会越聊越慢、越聊越贵，还容易撞上上下文上限直接 400；设 `0` 表示不截断 |
| 请求超时 | 60 秒 | 网络卡住时不会一直转圈 |
| 自动重试 | 2 次 | 偶发的 429、连接被重置由 SDK 自动重试 |
| 历史渲染上限 | 60 条 | 更早的消息收进「更早的 N 条消息」折叠区，长会话打开也不卡 |

侧边栏底部会显示当前真实生效的「上下文：每次带最近 N 条消息」。

## 📦 打包成 Windows exe

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-build.txt

pyinstaller --noconfirm --clean app.spec

# 把启动脚本和说明书塞进产物目录
Copy-Item packaging\*.bat dist\AI智能伴侣\ -Force
Copy-Item docs\使用说明.md dist\AI智能伴侣\ -Force
```

或直接跑一键脚本：`powershell -ExecutionPolicy Bypass -File scripts\build.ps1`

> ⚠️ **`app.spec` 里的 `copy_metadata("streamlit")` 不能删。**
> Streamlit 在 `import` 时会用 `importlib.metadata` 读自己的版本号，如果打包时没把
> `streamlit-x.y.z.dist-info` 一起带上，exe 一启动就直接崩，报
> `PackageNotFoundError: No package metadata was found for streamlit`
> ——控制台窗口一闪就没，看不出所以然。

这个包以前就坏在这里。PyInstaller 只顺着 `import` 链打包 `.py` 代码，
而 Streamlit 还依赖两样"不是代码"的东西——

| 缺什么 | 症状 | 谁负责补 |
| --- | --- | --- |
| `streamlit-x.y.z.dist-info`（元数据） | 启动瞬间崩：`PackageNotFoundError` | `app.spec` 里的 `copy_metadata("streamlit")` |
| `streamlit/static/`（前端 JS/CSS） | 服务起来了，但浏览器一片白 | `app.spec` 里的 `collect_all("streamlit")` |

所以打包链路现在是三道闸：

1. `python scripts/verify_bundle.py` —— 检查产物里 exe / app.py / resources / static / dist-info 是否齐全，还比对包内 `app.py` 与源码的 sha256，防止发出旧代码打的包；
2. `python tests/test_apptest.py` —— 用**真 Streamlit** 的 `AppTest` 把页面渲染三遍（无 key / 填了 key / 清空 key），确认不抛异常；
3. CI 里的「Launch check」—— 真的把 exe 跑起来，等 `http://127.0.0.1:8501` 返回 200 才允许发布。

三道闸任意一道不过，Release 就不会生成。

> 实测记录（2026-10-31）：Python 3.13.9 + Streamlit 1.66.0 + PyInstaller 6.22.3 打包，
> exe 启动后 `http://127.0.0.1:8501` 返回 200、`_stcore/health` 返回 `ok`，
> `AppTest` 三种情形均无异常。

产物结构（约 200 MB，PyInstaller **onedir 模式**，比 onefile 启动快很多）：

```
dist/AI智能伴侣/
├── AI智能伴侣.exe        # 主程序
├── 启动AI智能伴侣.bat    # 双击启动
├── 使用说明.md
└── _internal/            # 依赖，别删、别单独拷走 exe
```

## 🚀 发布到 GitHub

### 第 1 步：本地初始化仓库

```powershell
cd C:\Users\张维杰\Desktop\ai_partner
git init
git add .
git commit -m "feat: AI 智能伴侣 v1.0.0"
git branch -M main
```

### 第 2 步：在 GitHub 上建一个空仓库

打开 <https://github.com/new>，仓库名填 `AI-Partner`，**不要**勾选 "Add a README"（否则会冲突），创建后拿到地址。

### 第 3 步：推上去

```powershell
git remote add origin https://github.com/YOUR_NAME/AI-Partner.git
git push -u origin main
```

> 首次 push 会弹窗要求登录，用浏览器授权即可。
> 想用命令行登录：装 [GitHub CLI](https://cli.github.com/) 后执行 `gh auth login`，
> 之后可以 `gh repo create AI-Partner --public --source=. --push` 一步建仓并推送。

### 第 4 步：打标签，让云端自动打包成 Release

```powershell
git tag v1.0.0
git push origin v1.0.0
```

推送 tag 后，`.github/workflows/build-release.yml` 会在 GitHub 的 Windows 机器上自动：
装依赖 → 语法检查 → PyInstaller 打包 → 压缩 → **创建 Release 并附上 `AI-Partner-Windows-x64.zip`**。
进度看仓库的 **Actions** 页，几分钟后 **Releases** 页就有下载链接了。

### 手动发布（不想用 Actions 时）

```powershell
Compress-Archive -Path .\dist\AI智能伴侣 -DestinationPath AI-Partner-Windows-x64.zip
```

然后在仓库页面 **Releases → Draft a new release**，选择/新建 tag `v1.0.0`，把 zip 拖进附件框，发布即可。

### ⚠️ 关于 GitHub 的体积限制

| 限制 | 数值 | 对本项目意味着 |
| --- | --- | --- |
| 单个文件（进仓库） | 100 MB | ❌ **不要把 exe / `_internal` 提交进仓库**，`.gitignore` 已排除 |
| 仓库建议大小 | < 1 GB | ✅ 仓库里只放源码（几 MB） |
| Release 单个附件 | 2 GB | ✅ 打好的 200 MB zip 放 Release 完全够用 |

**一句话：代码进仓库，成品进 Release。** 这也是几乎所有开源项目的标准做法。

## ☁️ 部署成在线网页版

### 方案 A：Streamlit Community Cloud（免费，推荐）

1. 先把仓库推到 GitHub（公开仓库）；
2. 打开 <https://share.streamlit.io> → **New app**；
3. Repository 选 `YOUR_NAME/AI-Partner`，Branch `main`，Main file path 填 `app.py`；
4. **Advanced settings → Secrets** 里粘贴：
   ```toml
   DEEPSEEK_API_KEY = "sk-你的密钥"
   ```
5. 点 **Deploy**，等 1~2 分钟，就得到 `https://xxx.streamlit.app` 的公网地址。

### 方案 B：Hugging Face Spaces（国内访问通常更快）

新建 Space → SDK 选 **Streamlit** → 上传本仓库文件 → 在 *Settings → Variables and secrets* 添加 `DEEPSEEK_API_KEY`。

> 在线版注意：多用户会共享同一份 `sessions/`，且容器重启会丢文件。
> 想长期保存，把 `sessions` 换成数据库或对象存储（后续可扩展）。

## 📁 项目结构

```
ai_partner/
├── app.py                      # 应用主程序（Streamlit 页面 + 对话逻辑）
├── launcher.py                 # PyInstaller 打包入口（内部拉起 streamlit）
├── app.spec                    # PyInstaller 配置
├── requirements.txt            # 运行依赖
├── requirements-build.txt      # 打包依赖
├── resources/                  # 静态资源（logo 等）
├── packaging/                  # 提供给最终用户的启动/停止脚本
├── docs/使用说明.md            # 给最终用户看的说明书
├── docs/banner.png             # README 横幅
├── docs/original/05.ai_partner_4.py  # 最初那份单文件源码（存档）
├── tests/test_smoke.py         # 冒烟测试（假 Streamlit，不需要网络）
├── tests/test_apptest.py       # 真 Streamlit 的 AppTest 渲染测试
├── .streamlit/config.toml      # 主题与运行参数
├── scripts/build.ps1           # 一键打包脚本
├── scripts/verify_bundle.py    # 产物完整性检查（缺 static/元数据就报错）
├── scripts/make_banner.py      # 重新生成横幅
└── .github/workflows/
    └── build-release.yml       # 推 tag 自动打包并发 Release
```

## ❓ 常见问题

**Q：双击 exe 一闪就没了？**
说明启动报错。在 PowerShell 里执行 `.\AI智能伴侣.exe`，就能看到真实错误信息。

如果看到的是 `PackageNotFoundError: No package metadata was found for streamlit`，
那不是你电脑的问题，是这个包在打包时漏了 Streamlit 的元数据——换一个最新 Release 里的包，
或者干脆按下面的「源码运行」跑。本仓库的 `app.spec` 已经修掉了这个坑，CI 也会先把 exe 跑起来验证再发布。

**Q：提示端口被占用？**
换个端口：`set AI_PARTNER_PORT=8600` 再启动；或关掉占用 8501 的进程。

**Q：`_internal` 能删吗？能只发给别人 exe 吗？**
不能。PyInstaller onedir 模式下 exe 只是引导程序，必须和 `_internal/` 一起分发。真要单文件就改成 onefile，但启动会慢很多（每次解压 200 MB）。

**Q：杀毒软件报毒？**
PyInstaller 产物被误报很常见。可选做法：给 exe 加代码签名证书，或在 Release 说明里写明"未签名，请自行校验"。

**Q：聊天记录在哪？**
程序目录下的 `sessions/*.json`；若程序目录不可写（如装在 `C:\Program Files`），会自动落到 `%USERPROFILE%\.ai_partner\sessions\`。
也可以用环境变量 `AI_PARTNER_HOME` 指定一个数据目录（比如放到 U 盘或网盘同步盘里），会话与 `config.json` 都会跟着走。

**Q：怎么自测有没有改坏？**
三条命令，都不需要真的 API Key、不花钱：

```powershell
python -m py_compile app.py launcher.py     # 语法
python tests/test_smoke.py                  # 冒烟（假 Streamlit，不联网）
python tests/test_apptest.py                # 真 Streamlit 渲染页面（需要装了 streamlit）
python scripts/verify_bundle.py             # 打完包后检查产物齐不齐
```

## 📄 许可证

[MIT](LICENSE) —— 随便用、随便改，保留版权声明即可。

---

如果这个项目帮到了你，点个 ⭐ 就是最好的支持。
