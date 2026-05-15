from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any

from .config import DataProfile


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        content = path.read_text(encoding="utf-8").strip()
        return json.loads(content) if content else default
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to read JSON {path}: {exc}")
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_annotations(annotation_file: Path, file_path: str | None = None) -> dict:
    annotations = {}
    if not annotation_file.exists():
        return annotations if file_path is None else {}

    try:
        with annotation_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                key = record.get("file_path")
                if key:
                    annotations[key] = record
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load annotations {annotation_file}: {exc}")

    return annotations if file_path is None else annotations.get(file_path, {})


def normalize_annotation(record: dict) -> dict:
    subblock_bad_channels = record.get("subblock_bad_channels")
    if subblock_bad_channels is None:
        subblock_bad_channels = {"0": record.get("bad_channels", [])}

    return {
        "file_path": record["file_path"],
        "subblock_bad_channels": subblock_bad_channels,
        "discarded": bool(record.get("discarded", False)),
        "user": record.get("user", ""),
    }


def write_annotation(annotation_file: Path, record: dict) -> None:
    if not record.get("file_path"):
        raise ValueError("file_path is required")

    annotations = load_annotations(annotation_file)
    annotation = normalize_annotation(record)
    annotations[annotation["file_path"]] = annotation

    annotation_file.parent.mkdir(parents=True, exist_ok=True)
    with annotation_file.open("w", encoding="utf-8") as handle:
        for item in annotations.values():
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def get_annotation_for_file(annotation_file: Path, file_path: str) -> dict:
    annotation = load_annotations(annotation_file, file_path)
    if not annotation:
        return {"bad_channels": [], "subblock_bad_channels": {}, "discarded": False}

    subblock_bad_channels = annotation.get("subblock_bad_channels")
    if subblock_bad_channels is None:
        bad_channels = annotation.get("bad_channels", [])
        subblock_bad_channels = {"0": bad_channels}
    else:
        bad_channels = next(iter(subblock_bad_channels.values()), [])

    return {
        "bad_channels": bad_channels,
        "subblock_bad_channels": subblock_bad_channels,
        "discarded": bool(annotation.get("discarded", False)),
    }


def get_cache_key(root: Path) -> str:
    mtime = root.stat().st_mtime if root.exists() else 0
    return hashlib.md5(f"{root}_{mtime}".encode()).hexdigest()


def list_files_recursive(
    root: Path,
    profile: DataProfile,
    cache_dir: Path | None = None,
    use_cache: bool = True,
    is_root_call: bool = True,
) -> list[dict]:
    cache_dir = cache_dir or profile.cache_tree_path

    if is_root_call:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "tree.pkl"
        if use_cache and cache_file.exists():
            try:
                with cache_file.open("rb") as handle:
                    return pickle.load(handle)
            except Exception as exc:
                print(f"Cache access failed: {exc}")

    try:
        items = sorted(root.iterdir())
    except (FileNotFoundError, PermissionError):
        return []

    tree = []
    for item in items:
        if item.name in profile.skip_exact_dirs:
            continue
        if any(token in item.name for token in profile.skip_dirs):
            continue

        if item.is_dir():
            if item.name.endswith(".ds"):
                continue
            if is_root_call and profile.root_numeric_range is not None:
                try:
                    folder_num = int(item.name)
                except ValueError:
                    continue
                start, end = profile.root_numeric_range
                if not (start <= folder_num <= end):
                    continue

            tree.append({
                "name": item.name,
                "type": "dir",
                "children": list_files_recursive(item, profile, cache_dir, use_cache, False),
            })
        elif item.is_file() and item.suffix.lower().lstrip(".") in profile.file_suffixes:
            tree.append({"name": item.name, "type": "file", "path": str(item)})

    if is_root_call:
        try:
            with (cache_dir / "tree.pkl").open("wb") as handle:
                pickle.dump(tree, handle)
        except Exception as exc:
            print(f"Save cache failed: {exc}")

    return tree


def load_visualization(file_path: Path, channel_filters: tuple[str, ...]) -> dict:
    if not file_path.exists():
        return {}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load visualization {file_path}: {exc}")
        return {}

    def keep_channel(name: str) -> bool:
        return all(token.lower() not in name.lower() for token in channel_filters)

    channels = data.get("channels")
    data["channels"] = {
        name: values for name, values in channels.items() if keep_channel(name)
    } if isinstance(channels, dict) else {}

    psd = data.get("psd")
    if isinstance(psd, dict):
        data["psd"] = {
            name: values for name, values in psd.items() if keep_channel(name)
        }

    return data
