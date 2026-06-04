# 🎓 校园知识库问答助手 (Campus RAG Assistant)

> 面向大学生的校园政策问答助手。上传学校文件 → 自动构建知识库 → 基于**原文**回答教务、实习、奖学金、转专业、毕业论文等问题。

基于 RAG（检索增强生成）技术：本地中文向量模型负责"找到原文"，DeepSeek 大模型负责"读懂原文并作答"，**所有回答都以你上传的文件为依据，并标注来源**，避免大模型瞎编。

---

## ✨ 功能特性

- 📤 **多格式上传**：支持 PDF、Word(.docx)、TXT、Markdown
- 🧱 **自动建库**：解析 → 切分 → 向量化 → 入库全自动
- 🔍 **基于原文回答**：检索最相关的段落喂给大模型，回答附带来源文件
- 🏷️ **文档自动归类**：按文件名识别学生手册 / 教务通知 / 奖学金 / 实习 / 毕业论文等类型
- 🆓 **本地向量化**：使用 `BAAI/bge-small-zh-v1.5`，免费、离线、中文效果好
- 🖥️ **前后端分离**：FastAPI 后端 + Streamlit 网页，可单独使用 API

## 🗂️ 适用文档

学生手册 · 教务通知 · 奖学金评定办法 · 实习管理规定 · 毕业论文规范 ……（任意校园政策文件均可）

---

## 🏛️ 项目架构

```
用户提问
   │
   ▼
[Streamlit 前端] ──HTTP──> [FastAPI 后端]
                               │
                ┌──────────────┼───────────────┐
                ▼              ▼                ▼
          文档解析+切分    BGE 本地向量化      DeepSeek 大模型
          (loader/splitter) (embeddings)       (chain)
                              │                    ▲
                              ▼                    │
                        [Chroma 向量库] ──检索原文──┘
```

目录结构：

```
campus-rag-assistant/
├── app/
│   ├── config.py            # 配置（读 .env）
│   ├── main.py              # FastAPI 入口
│   ├── schemas.py           # 请求/响应模型
│   ├── api/routes.py        # 接口：/upload /chat /documents
│   └── rag/
│       ├── loader.py        # PDF/Word/TXT/MD 解析
│       ├── splitter.py      # 中文文本切分
│       ├── embeddings.py    # 本地 BGE 向量化
│       ├── vectorstore.py   # Chroma 向量库读写
│       ├── indexer.py       # 入库流水线
│       └── chain.py         # RAG 问答（调 DeepSeek）
├── streamlit_app.py         # 网页前端
├── scripts/ingest.py        # 命令行批量入库
├── data/samples/            # 5 份示例文件，可直接测试
├── requirements.txt
└── .env.example
```

---

## 🚀 快速开始

### 1. 准备环境

```bash
git clone <你的仓库地址>
cd campus-rag-assistant

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

> 首次运行会自动下载约 100MB 的中文向量模型（来自 HuggingFace）。

### 2. 配置 DeepSeek API Key

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

编辑 `.env`，填入你在 [platform.deepseek.com](https://platform.deepseek.com) 获取的 Key：

```
DEEPSEEK_API_KEY=sk-你的真实key
```

### 3. 启动后端

```bash
uvicorn app.main:app --reload
# 或 Windows 双击 run_backend.bat
```

打开 http://127.0.0.1:8000/docs 可看到交互式 API 文档。

### 4. 启动前端

另开一个终端：

```bash
streamlit run streamlit_app.py
# 或 Windows 双击 run_frontend.bat
```

浏览器访问 http://localhost:8501，在左侧上传文件，右侧开始提问。

### 5. （可选）用示例文件快速体验

```bash
python scripts/ingest.py data/samples
```

然后直接在前端提问，例如：

- 奖学金评定的成绩占比是多少？
- 转专业需要满足什么条件？
- 毕业论文查重率不能超过多少？
- 实习成绩不及格会怎样？
- 补考一般安排在什么时候？

---

## 🔌 API 说明

| 方法   | 路径                       | 说明                     |
| ------ | -------------------------- | ------------------------ |
| POST   | `/api/upload`              | 上传文件并自动入库       |
| POST   | `/api/chat`                | 提问，返回答案 + 来源    |
| GET    | `/api/documents`           | 查看已入库文档列表       |
| DELETE | `/api/documents/{source}`  | 删除某个文档及其向量     |
| GET    | `/api/health`              | 健康检查                 |

提问示例：

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "奖学金一等奖学金有多少钱？"}'
```

返回：

```json
{
  "answer": "根据《奖学金评定办法》，一等奖学金为每人每年 8000 元……",
  "sources": [{"source": "奖学金评定办法.txt", "score": 0.82}]
}
```

---

## ⚙️ 可调参数（`.env`）

| 变量                  | 默认值                   | 说明                       |
| --------------------- | ------------------------ | -------------------------- |
| `DEEPSEEK_MODEL`      | `deepseek-chat`          | 使用的 DeepSeek 模型       |
| `EMBEDDING_MODEL_NAME`| `BAAI/bge-small-zh-v1.5` | 本地向量模型（可换 large） |
| `CHUNK_SIZE`          | `500`                    | 文本切块大小               |
| `CHUNK_OVERLAP`       | `80`                     | 相邻块重叠字符数           |
| `TOP_K`               | `4`                      | 每次检索的段落数           |

---

## 🛠️ 技术栈

- **后端**：FastAPI + Uvicorn
- **前端**：Streamlit
- **向量库**：Chroma（本地持久化）
- **向量模型**：sentence-transformers + BGE 中文模型
- **大模型**：DeepSeek（OpenAI 兼容接口）
- **文档解析**：pypdf / python-docx

---

## 📝 说明与免责

- 示例文件（`data/samples/`）均为虚构内容，仅用于演示，请勿当作真实政策。
- 回答质量取决于上传文件的完整性；找不到依据时助手会如实说明。
- `.env` 与上传的文件、向量库默认不纳入版本控制（见 `.gitignore`）。

## 📄 License

MIT
