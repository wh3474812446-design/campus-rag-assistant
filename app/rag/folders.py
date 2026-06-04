"""文件夹（知识库分区）管理：用一个 JSON 记录文件夹名，空文件夹也能存在。"""

from __future__ import annotations

import json

from app.config import BASE_DIR

DEFAULT_FOLDER = "默认"
_FOLDERS_FILE = BASE_DIR / "data" / "folders.json"


def _load() -> list[str]:
    if _FOLDERS_FILE.exists():
        try:
            data = json.loads(_FOLDERS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(x) for x in data]
        except (json.JSONDecodeError, OSError):
            pass
    return [DEFAULT_FOLDER]


def _save(folders: list[str]) -> None:
    _FOLDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _FOLDERS_FILE.write_text(
        json.dumps(folders, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_folders(extra: list[str] | None = None) -> list[str]:
    """返回文件夹列表，确保默认文件夹在最前，并并入 extra（库里已存在的）。"""
    folders = _load()
    for name in extra or []:
        if name and name not in folders:
            folders.append(name)
    if DEFAULT_FOLDER in folders:
        folders.remove(DEFAULT_FOLDER)
    return [DEFAULT_FOLDER] + sorted(folders)


def create_folder(name: str) -> bool:
    name = name.strip()
    if not name or name == DEFAULT_FOLDER:
        return False
    folders = _load()
    if name in folders:
        return False
    folders.append(name)
    _save(folders)
    return True


def delete_folder(name: str) -> bool:
    """从列表中移除文件夹（默认文件夹不可删）。文档的删除由调用方处理。"""
    name = name.strip()
    if not name or name == DEFAULT_FOLDER:
        return False
    folders = _load()
    if name not in folders:
        return False
    folders.remove(name)
    _save(folders)
    return True
