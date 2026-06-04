"""Streamlit 前端：上传文档 + 聊天问答。

启动：streamlit run streamlit_app.py
（需要后端已启动：uvicorn app.main:app）
"""

import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="校园知识库问答助手", page_icon="🎓", layout="wide")


def api(path: str) -> str:
    return f"{BACKEND_URL}/api{path}"


# ---------- 侧边栏：文档管理 ----------
with st.sidebar:
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


# ---------- 主区：聊天 ----------
st.title("🎓 校园政策问答助手")
st.caption("基于你上传的学校文件，引用原文回答教务、实习、奖学金、转专业等问题。")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("📎 参考来源"):
                for s in msg["sources"]:
                    st.write(f"- 《{s['source']}》（相关度 {s['score']}）")

if prompt := st.chat_input("例如：奖学金评定的成绩占比是多少？"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("正在检索原文并思考..."):
            try:
                resp = requests.post(api("/chat"), json={"question": prompt}, timeout=120)
                if resp.ok:
                    data = resp.json()
                    st.markdown(data["answer"])
                    if data["sources"]:
                        with st.expander("📎 参考来源"):
                            for s in data["sources"]:
                                st.write(f"- 《{s['source']}》（相关度 {s['score']}）")
                    st.session_state.messages.append(
                        {"role": "assistant", "content": data["answer"], "sources": data["sources"]}
                    )
                else:
                    err = resp.json().get("detail", resp.text)
                    st.error(f"出错了：{err}")
            except requests.RequestException as e:
                st.error(f"连接后端失败：{e}")
