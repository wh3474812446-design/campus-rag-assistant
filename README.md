# 📚 RAG 知识库 (RAG Knowledge Base)

> 通用本地知识库问答系统。上传任意文档 → 自动构建知识库 → 基于**原文**引用作答。
> 用文件夹把不同类型的资料分开管理，可在指定知识库范围内提问。

基于 RAG（检索增强生成）技术：本地中文向量模型负责"找到原文"，DeepSeek 大模型负责"读懂原文并作答"，**所有回答都以你上传的资料为依据，并标注来源**，避免大模型瞎编。

> 换一批文档、改一句提示词，即可变成法律、医疗、产品手册、公司制度、校园政策等任意领域的知识库。

---

## ✨ 功能特性

- 📤 **多格式上传**：支持 PDF、Word(.docx)、TXT、Markdown
- 📁 **文件夹管理**：新建文件夹把不同类型资料分区，支持按文件夹删除；可**限定在某个文件夹内提问**
- 🧱 **自动建库**：解析 → 切分 → 向量化 → 入库全自动
- 🔍 **混合检索（Hybrid Search）**：BM25 关键词 + 向量语义双路召回，RRF 融合排序，精确词/编号也不漏；来源标注命中方式
- 🎯 **重排序（Rerank）**：交叉编码器（`bge-reranker-base`）对候选段落"问题+原文"成对精排，显著提升送给大模型的原文质量（可在 `.env` 关闭）
- ⌨️ **流式输出**：回答逐字打出（打字机效果），无需干等
- 🔎 **逐句溯源**：答案每句话定位到原文具体哪一句，并在原文段落中高亮（本地 BGE 句子级比对）
- 🗣️ **三种回答模式**：知识库严格 / 知识库+AI补充 / 通用助手，随时切换
- 🔑 **网页内配置 API**：右上角即可填写/更换 DeepSeek Key、切换模型，无需改文件
- 🆓 **本地向量化**：使用 `BAAI/bge-small-zh-v1.5`，免费、离线、中文效果好
- 🖥️ **前后端分离**：FastAPI 后端 + Streamlit 网页，可单独使用 API

## 🗂️ 适用场景

任意需要"基于一批文档精准问答"的场景：校园政策、法律法规、产品手册、公司制度、课程资料、研究文献……（仓库内置 5 份校园政策示例文件可直接体验）

---

## 🏛️ 项目架构

整个系统分两个阶段：**建库**（上传文档时做一次）和**提问**（每次问答）。
核心理念：**本地负责"找料"，云端 DeepSeek 只负责"读料后讲人话"。**

### 阶段 ① 建库（上传文档时）

```
拖入文档 (PDF/Word/TXT/MD)
   │  /upload
   ▼
解析成纯文字        loader.py     (pypdf / python-docx)
   ▼
中文递归切分成小块   splitter.py
   ▼
本地 BGE 向量化     embeddings.py (sentence-transformers + BGE)
   ▼
向量 + 原文 入库     vectorstore.py → Chroma 持久化到 data/chroma/
```

### 阶段 ② 提问（混合检索 + 生成）

```
你的问题
   │  /chat
   ▼
┌────────── 多路召回 retriever.py（三路并行，粗排）──────────┐
│  ① 向量路：BGE 把问题转向量 → Chroma 找"语义相近"的块      │
│  ② 关键词路：jieba 分词 → BM25 找"词面命中"的块            │
│  ③ 标题路：问题词命中文档名 → 召回该文档的块               │
│            ▼  RRF 倒数排名融合，把三路合成一个候选排名      │
└──────────────────────────┬─────────────────────────────────┘
                         ▼
   🎯 重排 reranker.py：交叉编码器对候选"问题+原文"精排，取 TOP_K（精排）
                         ▼
   拼 prompt：原文 + 问题 + 角色设定   chain.py
                         ▼
              ☁️ DeepSeek 思考并组织语言（联网）
                         ▼
              答案 + 来源（标注命中方式：向量/关键词/标题）→ 网页
```

详见下文 [检索流程：多路召回 → 融合 → 精排](#-检索流程多路召回--融合--精排)。

### 本地 vs 云端

| 在哪 | 做什么 | 成本 |
|---|---|---|
| 🖥️ **本地** | 文档解析、切分、BGE 向量化、Chroma 向量库、jieba 分词、BM25、RRF 融合、rerank 重排、前后端 | 免费、离线、不出本机 |
| ☁️ **云端** | 仅"读检索到的原文 → 生成回答"由 DeepSeek 完成 | 联网，按量计费 |

### 本地模型

| 模型 | 用途 | 大小 |
|---|---|---|
| **BAAI/bge-small-zh-v1.5** | 文本向量化（中文专用，512 维） | ~100 MB，首次自动下载并缓存 |
| **BAAI/bge-reranker-base** | 重排序交叉编码器（可在 `.env` 关闭） | ~1.1 GB，首次自动下载并缓存 |
| **jieba 词典** | 中文分词（供 BM25 使用，非神经网络） | 随依赖安装 |

> DeepSeek 不是本地模型，它在云端，需要 API Key + 联网。

### 目录结构

```
local-rag-qa/
├── app/
│   ├── config.py            # 配置（读/写 .env）
│   ├── main.py              # FastAPI 入口
│   ├── schemas.py           # 请求/响应模型
│   ├── api/routes.py        # 接口：/upload /chat /documents /config
│   └── rag/
│       ├── loader.py        # PDF/Word/TXT/MD 解析
│       ├── splitter.py      # 中文文本切分
│       ├── embeddings.py    # 本地 BGE 向量化
│       ├── vectorstore.py   # Chroma 向量库读写（按文件夹分区）
│       ├── retriever.py     # 混合检索（BM25 + 向量，RRF 融合）
│       ├── reranker.py      # 交叉编码器重排序（精排候选）
│       ├── folders.py       # 文件夹（知识库分区）管理
│       ├── tracer.py        # 逐句溯源（句子级语义比对）
│       ├── indexer.py       # 入库流水线
│       └── chain.py         # 三种模式问答（调 DeepSeek）
├── streamlit_app.py         # 网页前端（聊天 / 上传 / 模式 / API 设置）
├── scripts/ingest.py        # 命令行批量入库
├── data/samples/            # 5 份学校政策示例文件，可直接测试
├── install.bat              # Windows 一键安装（装依赖 + 建桌面快捷方式）
├── create_shortcut.ps1      # 生成桌面快捷方式（被 install.bat 调用）
├── start.bat                # 一键启动（前后端 + 自动开网页）
├── .streamlit/config.toml   # streamlit 主题 / 配置
├── requirements.txt
└── .env.example
```

---

## 🧭 检索流程：多路召回 → 融合 → 精排

本项目的检索是工业级 RAG 常用的**两段式**结构：先"广撒网"召回候选（**召回**，要全、要快），再"精挑细选"重排（**精排**，要准）。

### 第一段：多路召回（粗排）

单一检索方法都有盲区，所以**三路并行**召回，互相补盲：

| 路 | 方法 | 擅长 | 弥补的短板 |
|---|---|---|---|
| ① 向量路 | BGE 语义向量 + Chroma | 懂同义/换种说法（"薪资"≈"工资"） | — |
| ② 关键词路 | jieba 分词 + BM25 | 精确词、编号、专有名词（"第五条""8000元"） | 向量对精确词不敏感 |
| ③ 标题路 | 问题词命中文档名 | 主题对口的整份文档 | 正文未必含问题词，但文件名点题 |

三路各召回一批候选后，用 **RRF（Reciprocal Rank Fusion，倒数排名融合）** 合并：
某个文本块的融合分 = `Σ 1/(K + 它在各路里的排名)`（K=60）。RRF 只看排名、不看各路分数量纲，因此能稳健地把"被多路同时选中、且排名靠前"的块顶上来。来源里会标注它被哪几路命中（如 `向量+关键词+标题`）。

### 第二段：重排精排（rerank）

召回是"双塔/词频"式的粗筛——问题和段落分开编码，省算力但不够准。
精排用**交叉编码器**（`bge-reranker-base`）把"问题 + 每个候选段落"**拼在一起读**，输出更精准的相关度分，对候选重新排序，最后只取 `TOP_K` 段送给大模型。

```
问题
 ├─ 向量路 ┐
 ├─ 关键词路 ├─→ 各召回 N 个候选 ─→ RRF 融合（粗排，取前 RERANK_CANDIDATES 个）
 └─ 标题路 ┘
                         └─→ 交叉编码器重排（精排）─→ TOP_K 段 ─→ DeepSeek
```

### 相关参数（`.env`）

- `RETRIEVAL_CANDIDATES`：每路召回的候选数（实际取 `max(TOP_K×3, 该值)`）
- `RERANK_CANDIDATES`：进入重排的候选数（融合后取前 N 个精排）
- `TOP_K`：精排后最终送给大模型的段落数
- `USE_RERANK` / `USE_TITLE_ROUTE`：可分别关闭重排 / 标题路

> 设计取舍：召回阶段宁可多召（提高"不漏"的召回率），把"准不准"交给更强但更慢的 rerank 在小候选集上解决——既快又准。

---

## 🚀 快速开始

### 🟢 最简单：Windows 一键安装（推荐新手）

1. 安装 [Python 3.10+](https://www.python.org/downloads/)（安装时勾选 **Add Python to PATH**）
2. 下载本项目（绿色 `Code` 按钮 → Download ZIP，解压）
3. **双击 `install.bat`** —— 自动装好依赖，并在**桌面生成「RAG 知识库」快捷方式**
4. **双击桌面的「RAG 知识库」图标** —— 自动启动并打开网页（以后每次用都点它）
5. 在网页**右上角「⚙️ API 设置」**里填入你的 DeepSeek API Key → 保存 → 即可开始提问

> DeepSeek API Key 在 https://platform.deepseek.com 注册后于「API Keys」新建。
> Key 在网页里随时可设置/更换，无需改任何文件。
> 内置 5 份**学校政策示例文件**（在 `data/samples/`，已预置到「默认」文件夹），可立即试问。

下面是手动方式（适合开发者 / macOS / Linux）。

### 1. 准备环境

```bash
git clone https://github.com/<你的用户名>/local-rag-qa.git
cd local-rag-qa

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

| 方法   | 路径                       | 说明                            |
| ------ | -------------------------- | ------------------------------- |
| POST   | `/api/upload`              | 上传文件到指定文件夹并自动入库   |
| POST   | `/api/chat`                | 提问，返回答案 + 来源            |
| POST   | `/api/chat/stream`         | 流式提问（SSE）                  |
| POST   | `/api/trace`               | 逐句溯源，返回答案每句的原文依据 |
| GET    | `/api/documents`           | 查看已入库文档列表（含文件夹）   |
| DELETE | `/api/documents/{source}`  | 删除某个文档（可带 `?folder=`）  |
| GET    | `/api/folders`             | 文件夹列表                      |
| POST   | `/api/folders`             | 新建文件夹                      |
| DELETE | `/api/folders/{name}`      | 删除文件夹及其下所有文档        |
| GET/POST | `/api/config`            | 查看 / 更新 DeepSeek 配置       |
| GET    | `/api/health`              | 健康检查                        |

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
| `TOP_K`               | `4`                      | 最终送给大模型的段落数     |
| `RETRIEVAL_CANDIDATES`| `10`                     | 多路召回时每路召回的候选数 |
| `USE_TITLE_ROUTE`     | `true`                   | 是否启用第三路（标题匹配） |
| `USE_RERANK`          | `true`                   | 是否启用交叉编码器重排     |
| `RERANKER_MODEL_NAME` | `BAAI/bge-reranker-base` | 重排模型（首次约下载 1.1GB）|
| `RERANK_CANDIDATES`   | `20`                     | 进入重排的候选数           |

---

## 🛠️ 技术栈

- **后端**：FastAPI + Uvicorn
- **前端**：Streamlit
- **向量库**：Chroma（本地持久化）
- **向量模型**：sentence-transformers + BGE 中文模型（`bge-small-zh-v1.5`）
- **混合检索**：rank-bm25（关键词）+ jieba（中文分词）+ RRF 融合
- **大模型**：DeepSeek（OpenAI 兼容接口）
- **文档解析**：pypdf / python-docx

---

## 📝 说明与免责

- 示例文件（`data/samples/`）均为虚构内容，仅用于演示，请勿当作真实政策。
- 回答质量取决于上传文件的完整性；找不到依据时助手会如实说明。
- `.env` 与上传的文件、向量库默认不纳入版本控制（见 `.gitignore`）。

## 📄 License

MIT
