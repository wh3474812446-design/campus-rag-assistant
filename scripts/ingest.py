"""命令行批量入库工具。

用法：
    python scripts/ingest.py data/samples
    python scripts/ingest.py path/to/学生手册.pdf
"""

import sys
from pathlib import Path

# 让脚本能 import app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.indexer import ingest_file  # noqa: E402
from app.rag.loader import SUPPORTED_EXTENSIONS  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python scripts/ingest.py <文件或目录路径>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"路径不存在: {target}")
        sys.exit(1)

    if target.is_file():
        files = [target]
    else:
        files = [p for p in target.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not files:
        print("没有找到可处理的文件。")
        return

    print(f"准备处理 {len(files)} 个文件...\n")
    for f in files:
        try:
            r = ingest_file(f)
            print(f"✅ {r['source']:30} [{r['doc_type']}] {r['chars']} 字 -> {r['chunks']} 块")
        except Exception as e:  # noqa: BLE001
            print(f"❌ {f.name}: {e}")

    print("\n完成。")


if __name__ == "__main__":
    main()
