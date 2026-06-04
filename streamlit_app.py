"""Streamlit 前端：上传文档 + 聊天问答。

启动：streamlit run streamlit_app.py
（需要后端已启动：uvicorn app.main:app）
"""

import html
import json
import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="校园知识库问答助手", page_icon="🎓", layout="wide")


def api(path: str) -> str:
    return f"{BACKEND_URL}/api{path}"


# 模式：显示名 -> 后端参数
MODE_OPTIONS = {
    "📚 知识库问答（只照文件答）": "kb",
    "🔀 知识库 + AI 补充": "hybrid",
    "💬 通用助手（什么都能聊）": "general",
}

# ---------- 侧边栏：模式 + 文档管理 ----------
with st.sidebar:
    st.header("🧭 回答模式")
    mode_label = st.radio(
        "选择助手的回答方式",
        list(MODE_OPTIONS.keys()),
        index=0,
        help="知识库模式只依据你上传的文件；通用助手可回答任何问题。",
    )
    mode = MODE_OPTIONS[mode_label]
    st.caption(
        {
            "kb": "只依据上传的文件回答，带原文出处，绝不编造。",
            "hybrid": "优先用文件；文件没有的，用 AI 通用知识补充并标注。",
            "general": "完全放开的 DeepSeek，可写作、翻译、解释概念、写代码等。",
        }[mode]
    )

    st.divider()
    st.header("📚 知识库管理")

    uploaded = st.file_uploader(
        "上传校园文件",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
        help="学生手册 / 教务通知 / 奖学金评定办法 / 实习管理规定 / 毕业论文规范",
    )
    if uploaded and st.button("📥 构建知识库", use_container_width=True):
        for f in uploaded:
            with st.spinner(f"正在处理 {f.name} ..."):
                try:
                    resp = requests.post(
                        api("/upload"),
                        files={"file": (f.name, f.getvalue())},
                        timeout=300,
                    )
                    if resp.ok:
                        d = resp.json()
                        st.success(f"✅ {d['source']}（{d['doc_type']}）→ {d['chunks']} 块")
                    else:
                        st.error(f"❌ {f.name}：{resp.json().get('detail', resp.text)}")
                except requests.RequestException as e:
                    st.error(f"❌ 连接后端失败：{e}")

    st.divider()
    st.subheader("已入库文档")
    try:
        docs = requests.get(api("/documents"), timeout=10).json()
        if docs["total_documents"] == 0:
            st.caption("暂无文档，请先上传。")
        else:
            st.caption(f"共 {docs['total_documents']} 个文件 / {docs['total_chunks']} 个文本块")
            for d in docs["documents"]:
                c1, c2 = st.columns([4, 1])
                c1.write(f"📄 {d['source']}  \n　`{d['doc_type']}` · {d['chunks']} 块")
                if c2.button("🗑", key=f"del_{d['source']}"):
                    requests.delete(api(f"/documents/{d['source']}"), timeout=10)
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
    st.title("🎓 校园政策问答助手")
with top_right:
    st.write("")  # 占位，让按钮和标题大致齐平
    with st.popover("⚙️ API 设置", use_container_width=True):
        render_api_settings()

st.caption("基于你上传的学校文件，引用原文回答教务、实习、奖学金、转专业等问题。")

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
                safe_sent, f"<mark style='background:#ffe58f'>{safe_sent}</mark>", 1
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
                    json={"question": prompt, "mode": mode},
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
