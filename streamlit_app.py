"""Streamlit 前端：RAG 知识库（上传文档 + 文件夹管理 + 聊天问答）。

启动：streamlit run streamlit_app.py
（需要后端已启动：uvicorn app.main:app）
"""

import atexit
import html
import json
import os
import subprocess
import sys
import time

import requests
import streamlit as st

# 强制让本机回环绕过代理（开了 Clash/v2ray 时也能连上后端）
os.environ["NO_PROXY"] = "127.0.0.1,localhost," + os.environ.get("NO_PROXY", "")
os.environ["no_proxy"] = os.environ["NO_PROXY"]

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
ALL_SCOPE = "🌐 全部知识库"
_ROOT = os.path.dirname(os.path.abspath(__file__))


def _backend_alive() -> bool:
    """后端健康检查（显式禁用代理，避免回环被代理拦截）。"""
    try:
        r = requests.get(
            f"{BACKEND_URL}/api/health",
            timeout=2,
            proxies={"http": None, "https": None},
        )
        return r.status_code == 200
    except requests.RequestException:
        return False


@st.cache_resource(show_spinner="正在启动后端服务（首次需加载向量模型，约 10–30 秒）…")
def ensure_backend():
    """前端自己托管后端：连不上就把 uvicorn 当子进程拉起来并守护。

    这样只需一个窗口，后端不会被误关；连不上时自动重启。
    cache_resource 保证整个会话只启动一次。
    """
    if _backend_alive():
        return None

    log = open(os.path.join(_ROOT, "backend.log"), "a", encoding="utf-8")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=_ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    atexit.register(lambda: proc.terminate())

    # 最多等 60 秒就绪
    for _ in range(60):
        if _backend_alive():
            return proc
        if proc.poll() is not None:  # 子进程已退出，启动失败
            break
        time.sleep(1)
    return proc

st.set_page_config(page_title="RAG 知识库", page_icon="📚", layout="wide")

# 深空黑 + 冷蓝辉光 科幻暗色风格
_CSS = """
<style>
:root{
  --bg:#0A0A0B; --panel:#161719; --panel-2:#1C1D20;
  --text:#EAEAEC; --muted:#8A8B90; --line:rgba(255,255,255,.08);
  --accent:#7AA2FF;
}

/* 深空黑底 + 柔和冷蓝辉光（多层渐变，整页平滑过渡，无硬边） */
.stApp{
  background:
    radial-gradient(1300px 820px at 52% -12%, rgba(110,150,255,.12), transparent 62%),
    radial-gradient(820px 680px at 6% 4%, rgba(120,150,255,.07), transparent 55%),
    linear-gradient(180deg, #0C0D11 0%, #0A0A0B 55%, #08080A 100%);
  background-attachment: fixed;
}

/* 顶栏透明：消除顶部那条突兀的纯黑横带，让背景贯通 */
[data-testid="stHeader"]{ background:transparent; box-shadow:none; }
[data-testid="stToolbar"]{ right:1rem; }

/* 标题：粗壮无衬线、近白 */
h1,h2,h3,h4{
  font-family:"Inter","Segoe UI","PingFang SC","Microsoft YaHei",sans-serif !important;
  color:#F4F5F7 !important; font-weight:700; letter-spacing:.4px;
}

/* 正文 */
.stApp, p, li, label, span{ color:var(--text); }
[data-testid="stCaptionContainer"], .stCaption{ color:var(--muted) !important; letter-spacing:.3px; }

/* 侧边栏：更深 + 细分隔线 */
section[data-testid="stSidebar"]{
  background:#101113; border-right:1px solid var(--line);
}

/* 次要按钮：深色描边 */
.stButton button[kind="secondary"]{
  background:var(--panel-2); color:var(--text);
  border:1px solid var(--line); border-radius:10px; font-weight:600;
  transition:all .15s ease;
}
.stButton button[kind="secondary"]:hover{ border-color:var(--accent); color:#fff; }

/* 主要按钮：白底黑字胶囊 + 蓝辉光（对应 INITIALIZE UPLINK） */
.stButton button[kind="primary"], .stFormSubmitButton button{
  background:#F5F6F8; color:#0A0A0B;
  border:none; border-radius:999px; font-weight:700;
  box-shadow:0 0 24px rgba(120,160,255,.18); transition:all .15s ease;
}
.stButton button[kind="primary"]:hover, .stFormSubmitButton button:hover{
  background:#fff; box-shadow:0 0 32px rgba(120,160,255,.35);
}

/* 输入框 / 下拉 / 文本域：深色卡片 */
[data-baseweb="select"]>div, .stTextInput input, .stTextArea textarea{
  background:var(--panel-2) !important; border-color:var(--line) !important; color:var(--text) !important;
}

/* 聊天输入框：深色圆角卡片 */
[data-testid="stChatInput"]{
  background:var(--panel-2); border:1px solid var(--line); border-radius:14px;
}

/* 展开块 / 聊天气泡：深色卡片 */
[data-testid="stExpander"], [data-testid="stChatMessage"]{
  background:var(--panel); border:1px solid var(--line); border-radius:14px;
}

/* 链接与强调用冷蓝 */
a, a:visited{ color:var(--accent); }

/* 顶部留白 */
.block-container{ padding-top:2.5rem; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

# 确保后端在线（连不上则自动拉起并等待就绪）
ensure_backend()
if not _backend_alive():
    st.error(
        "后端服务启动失败。请关闭本窗口后重新双击「一键启动 RAG 知识库」重试；"
        "若仍失败，请打开项目目录下的 backend.log 查看报错。"
    )
    st.stop()


def api(path: str) -> str:
    return f"{BACKEND_URL}/api{path}"


def fetch_folders() -> list:
    try:
        return requests.get(api("/folders"), timeout=10).json()["folders"]
    except requests.RequestException:
        return ["默认"]


# 模式：显示名 -> 后端参数
MODE_OPTIONS = {
    "📚 知识库问答（只照资料答）": "kb",
    "🔀 知识库 + AI 补充": "hybrid",
    "💬 通用助手（什么都能聊）": "general",
}

# ---------- 侧边栏：模式 + 文件夹 + 文档管理 ----------
with st.sidebar:
    st.header("🧭 回答模式")
    mode_label = st.radio(
        "选择助手的回答方式",
        list(MODE_OPTIONS.keys()),
        index=0,
        help="知识库模式只依据你上传的资料；通用助手可回答任何问题。",
    )
    mode = MODE_OPTIONS[mode_label]
    st.caption(
        {
            "kb": "只依据上传的资料回答，带原文出处，绝不编造。",
            "hybrid": "优先用资料；资料没有的，用 AI 通用知识补充并标注。",
            "general": "完全放开的 DeepSeek，可写作、翻译、解释概念、写代码等。",
        }[mode]
    )

    folders = fetch_folders()

    # 提问范围：在哪个文件夹内检索
    query_folder = None
    if mode != "general":
        scope = st.selectbox("🔭 提问范围", [ALL_SCOPE] + folders, index=0)
        query_folder = None if scope == ALL_SCOPE else scope

    st.divider()
    st.header("📁 知识库管理")

    # 新建文件夹
    with st.expander("➕ 新建文件夹"):
        new_folder = st.text_input("文件夹名称", placeholder="如：法律法规 / 产品手册")
        if st.button("创建", use_container_width=True):
            name = new_folder.strip()
            if name:
                r = requests.post(api("/folders"), json={"name": name}, timeout=10)
                if r.ok:
                    st.success(f"已创建「{name}」")
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "创建失败"))

    # 上传到指定文件夹
    target_folder = st.selectbox("📂 上传到文件夹", folders, index=0)
    uploaded = st.file_uploader(
        "上传文档",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
        help="支持 PDF / Word / TXT / Markdown，任意领域的资料均可",
    )
    if uploaded and st.button("📥 构建知识库", use_container_width=True):
        for f in uploaded:
            with st.spinner(f"正在处理 {f.name} ..."):
                try:
                    resp = requests.post(
                        api("/upload"),
                        files={"file": (f.name, f.getvalue())},
                        data={"folder": target_folder},
                        timeout=300,
                    )
                    if resp.ok:
                        d = resp.json()
                        st.success(f"✅ {d['source']} → 「{d['folder']}」{d['chunks']} 块")
                    else:
                        st.error(f"❌ {f.name}：{resp.json().get('detail', resp.text)}")
                except requests.RequestException as e:
                    st.error(f"❌ 连接后端失败：{e}")
        st.rerun()

    st.divider()
    st.subheader("📑 已入库文档")
    try:
        docs = requests.get(api("/documents"), timeout=10).json()
        # 按文件夹聚合展示
        by_folder: dict = {f: [] for f in folders}
        for d in docs["documents"]:
            by_folder.setdefault(d["folder"], []).append(d)

        if docs["total_documents"] == 0:
            st.caption("暂无文档，请先上传。")
        else:
            st.caption(f"共 {docs['total_documents']} 个文件 / {docs['total_chunks']} 个文本块")

        for folder in by_folder:
            items = by_folder[folder]
            head_l, head_r = st.columns([4, 1])
            head_l.markdown(f"**📁 {folder}** （{len(items)}）")
            if folder != "默认":
                if head_r.button("🗑", key=f"delfolder_{folder}", help="删除整个文件夹"):
                    requests.delete(api(f"/folders/{folder}"), timeout=15)
                    st.rerun()
            if not items:
                st.caption("　（空文件夹）")
            for d in items:
                c1, c2 = st.columns([4, 1])
                c1.write(f"　📄 {d['source']} · {d['chunks']} 块")
                if c2.button("🗑", key=f"del_{folder}_{d['source']}"):
                    requests.delete(
                        api(f"/documents/{d['source']}"),
                        params={"folder": folder},
                        timeout=10,
                    )
                    st.rerun()
    except requests.RequestException:
        st.warning("⚠️ 后端未连接。请先运行 `uvicorn app.main:app`。")


# ---------- 顶部：标题 + 右上角 API 设置 ----------
def render_api_settings() -> None:
    """右上角「API 设置」弹出框：填/换 key、选模型、测试连接。"""
    try:
        cfg = requests.get(api("/config"), timeout=10).json()
    except requests.RequestException:
        st.error("后端未连接，无法配置。")
        return

    if cfg["configured"]:
        st.success(f"已配置　当前 Key：`{cfg['api_key_masked']}`")
    else:
        st.warning("尚未配置 API Key，请在下方填写后保存。")

    new_key = st.text_input(
        "DeepSeek API Key",
        type="password",
        placeholder="sk-...（留空则不修改）",
        help="在 https://platform.deepseek.com 的「API Keys」里新建获取",
    )
    models = ["deepseek-chat", "deepseek-reasoner"]
    cur_model = cfg["model"] if cfg["model"] in models else models[0]
    model = st.selectbox("模型", models, index=models.index(cur_model))
    base_url = st.text_input("API 地址（一般不用改）", value=cfg["base_url"])

    c1, c2 = st.columns(2)
    if c1.button("💾 保存", use_container_width=True, type="primary"):
        payload = {"model": model, "base_url": base_url}
        if new_key.strip():
            payload["api_key"] = new_key.strip()
        try:
            r = requests.post(api("/config"), json=payload, timeout=15)
            if r.ok:
                st.success("已保存！")
                st.rerun()
            else:
                st.error(f"保存失败：{r.text}")
        except requests.RequestException as e:
            st.error(f"保存失败：{e}")
    if c2.button("🔌 测试连接", use_container_width=True):
        with st.spinner("测试中..."):
            try:
                r = requests.post(api("/config/test"), timeout=30).json()
                if r["ok"]:
                    st.success(r["message"])
                else:
                    st.error(f"失败：{r['message'][:300]}")
            except requests.RequestException as e:
                st.error(f"测试失败：{e}")


top_left, top_right = st.columns([0.72, 0.28])
with top_left:
    st.title("📚 RAG 知识库")
with top_right:
    st.write("")  # 占位，让按钮和标题大致齐平
    with st.popover("⚙️ API 设置", use_container_width=True):
        render_api_settings()

_scope_tip = "全部知识库" if query_folder is None else f"「{query_folder}」"
st.caption(f"上传任意文档自动建库，基于原文引用作答。当前提问范围：{_scope_tip}")

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_sources(sources: list) -> None:
    if sources:
        with st.expander("📎 参考来源"):
            for s in sources:
                st.write(
                    f"- 《{s['source']}》（{s.get('method', '向量')}命中 · 相关度 {s['score']}）"
                )


def render_trace(items: list) -> None:
    if not items:
        st.caption("未能为答案找到明确对应的原文句子。")
        return
    for it in items:
        label = f"「{it['answer_sentence'][:36]}…」 → 《{it['source']}》(相似度 {it['score']})"
        with st.expander(label):
            safe_chunk = html.escape(it["chunk_text"])
            safe_sent = html.escape(it["source_sentence"])
            highlighted = safe_chunk.replace(
                safe_sent, f"<mark style='background:#E7C46B;color:#1C1B19'>{safe_sent}</mark>", 1
            )
            st.markdown(
                f"<div style='line-height:1.8'>{highlighted}</div>",
                unsafe_allow_html=True,
            )


def do_trace(answer_text: str) -> list:
    try:
        r = requests.post(api("/trace"), json={"answer": answer_text}, timeout=120)
        return r.json().get("items", []) if r.ok else []
    except requests.RequestException:
        return []


# ---------- 历史消息 ----------
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            render_sources(msg.get("sources"))
            if msg.get("sources"):  # 只有基于知识库的回答才溯源
                if msg.get("trace") is None:
                    if st.button("🔎 逐句溯源", key=f"trace_{idx}"):
                        with st.spinner("正在逐句比对原文..."):
                            msg["trace"] = do_trace(msg["content"])
                        st.rerun()
                else:
                    st.markdown("**🔎 逐句溯源**（点开每句看原文依据，黄色为依据句）")
                    render_trace(msg["trace"])


# ---------- 新提问（流式） ----------
if prompt := st.chat_input("例如：奖学金评定的成绩占比是多少？"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        sources_holder: list = []
        error_holder: list = []

        def token_gen():
            try:
                resp = requests.post(
                    api("/chat/stream"),
                    json={"question": prompt, "mode": mode, "folder": query_folder},
                    stream=True,
                    timeout=300,
                )
            except requests.RequestException as e:
                error_holder.append(str(e))
                return
            resp.encoding = "utf-8"  # SSE 默认编码会导致中文乱码，强制 utf-8
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if "sources" in obj:
                    sources_holder.extend(obj["sources"])
                elif "token" in obj:
                    yield obj["token"]
                elif "error" in obj:
                    error_holder.append(obj["error"])

        answer_text = st.write_stream(token_gen())
        if error_holder:
            st.error(f"出错了：{error_holder[0]}")
        render_sources(sources_holder)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer_text or "（无内容）",
            "sources": sources_holder,
            "trace": None,
        }
    )
    st.rerun()
