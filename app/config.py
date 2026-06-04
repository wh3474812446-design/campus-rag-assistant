"""全局配置：从环境变量 / .env 文件读取。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（campus-rag-assistant/）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DeepSeek 大模型
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # 本地 embedding
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"

    # 检索 / 切分
    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k: int = 4
    retrieval_candidates: int = 10  # 混合检索时每路召回的候选数

    # 存储
    chroma_dir: str = "data/chroma"
    upload_dir: str = "data/uploads"
    collection_name: str = "campus_kb"

    # 服务
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    backend_url: str = "http://127.0.0.1:8000"

    @property
    def chroma_path(self) -> Path:
        p = BASE_DIR / self.chroma_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def upload_path(self) -> Path:
        p = BASE_DIR / self.upload_dir
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def update_env_file(values: dict[str, str]) -> None:
    """更新（或新增）.env 中的键值，保留其他行与注释，写出无 BOM 的 UTF-8。"""
    env_path = BASE_DIR / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    done: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                out.append(f"{key}={values[key]}")
                done.add(key)
                continue
        out.append(line)

    for key, val in values.items():
        if key not in done:
            out.append(f"{key}={val}")

    # Python 的 utf-8 编码不带 BOM
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
