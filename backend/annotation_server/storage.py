from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from .config import DataProfile


PROCESSED_SUFFIXES = {".json", ".npz"}


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


def _as_channel_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_subblock_channels(value: Any) -> dict:
    if isinstance(value, dict):
        return {str(key): _as_channel_list(channels) for key, channels in value.items()}
    if isinstance(value, list):
        return {"0": value}
    return {}


def normalize_annotation(record: dict) -> dict:
    legacy_bad_channels = record.get("bad_channels", [])
    legacy_subblock_bad_channels = record.get("subblock_bad_channels")
    psd_bad_channels = record.get("psd_bad_channels")
    wav_bad_channels = record.get("wav_bad_channels")

    if psd_bad_channels is None:
        psd_bad_channels = legacy_bad_channels if isinstance(legacy_bad_channels, list) else []
    if wav_bad_channels is None:
        wav_bad_channels = legacy_subblock_bad_channels
    if wav_bad_channels is None:
        wav_bad_channels = legacy_bad_channels if isinstance(legacy_bad_channels, dict) else {}

    return {
        "file_path": record["file_path"],
        "psd_bad_channels": _as_channel_list(psd_bad_channels),
        "wav_bad_channels": _as_subblock_channels(wav_bad_channels),
        "subblock_bad_channels": _as_subblock_channels(wav_bad_channels),
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
        return {
            "bad_channels": [],
            "psd_bad_channels": [],
            "wav_bad_channels": {},
            "subblock_bad_channels": {},
            "discarded": False,
        }

    psd_bad_channels = annotation.get("psd_bad_channels")
    wav_bad_channels = annotation.get("wav_bad_channels")
    legacy_bad_channels = annotation.get("bad_channels", [])
    legacy_subblock_bad_channels = annotation.get("subblock_bad_channels")

    if psd_bad_channels is None:
        psd_bad_channels = legacy_bad_channels if isinstance(legacy_bad_channels, list) else []
    if wav_bad_channels is None:
        wav_bad_channels = legacy_subblock_bad_channels
    if wav_bad_channels is None:
        wav_bad_channels = legacy_bad_channels if isinstance(legacy_bad_channels, dict) else {}

    wav_bad_channels = _as_subblock_channels(wav_bad_channels)

    return {
        "bad_channels": next(iter(wav_bad_channels.values()), []),
        "psd_bad_channels": _as_channel_list(psd_bad_channels),
        "wav_bad_channels": wav_bad_channels,
        "subblock_bad_channels": wav_bad_channels,
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
        cache_file = cache_dir / f"tree_{profile.data_source}.pkl"
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
            with (cache_dir / f"tree_{profile.data_source}.pkl").open("wb") as handle:
                pickle.dump(tree, handle)
        except Exception as exc:
            print(f"Save cache failed: {exc}")

    return tree


def processed_logical_name(file_name: str) -> str | None:
    stem = Path(file_name).stem
    if "_wav_" in stem:
        base, block = stem.rsplit("_wav_", 1)
        return base if block.isdigit() else None
    if stem.endswith("_psd"):
        return stem[:-4]
    return None


def list_processed_files_recursive(
    root: Path,
    profile: DataProfile,
    cache_dir: Path | None = None,
    use_cache: bool = True,
    is_root_call: bool = True,
) -> list[dict]:
    cache_dir = cache_dir or profile.cache_tree_path

    if is_root_call:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "tree_processed.pkl"
        if use_cache and cache_file.exists():
            try:
                with cache_file.open("rb") as handle:
                    return pickle.load(handle)
            except Exception as exc:
                print(f"Processed cache access failed: {exc}")

    try:
        items = sorted(root.iterdir())
    except (FileNotFoundError, PermissionError):
        return []

    tree = []
    logical_files: dict[str, Path] = {}

    for item in items:
        if item.name in profile.skip_exact_dirs:
            continue
        if any(token in item.name for token in profile.skip_dirs):
            continue

        if item.is_dir():
            children = list_processed_files_recursive(item, profile, cache_dir, use_cache, False)
            if children:
                tree.append({"name": item.name, "type": "dir", "children": children})
        elif item.is_file() and item.suffix.lower() in PROCESSED_SUFFIXES:
            logical_name = processed_logical_name(item.name)
            if logical_name:
                logical_files.setdefault(logical_name, item.parent / f"{logical_name}.json")

    for name, logical_path in sorted(logical_files.items()):
        tree.append({"name": name, "type": "file", "path": str(logical_path)})

    if is_root_call:
        try:
            with (cache_dir / "tree_processed.pkl").open("wb") as handle:
                pickle.dump(tree, handle)
        except Exception as exc:
            print(f"Save processed cache failed: {exc}")

    return tree


def list_data_files(
    profile: DataProfile,
    use_cache: bool = True,
) -> list[dict]:
    if profile.data_source == "raw":
        return list_files_recursive(profile.raw_data_root, profile, profile.cache_tree_path, use_cache)
    return list_processed_files_recursive(profile.vis_data_root, profile, profile.cache_tree_path, use_cache)


def resolve_visualization_file(file_path: Path) -> Path | None:
    candidates = [file_path]
    if file_path.suffix.lower() == ".json":
        candidates.insert(0, file_path.with_suffix(".npz"))
    elif file_path.suffix.lower() == ".npz":
        candidates.append(file_path.with_suffix(".json"))

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def keep_channel(name: str, channel_filters: tuple[str, ...]) -> bool:
    return all(token.lower() not in name.lower() for token in channel_filters)


def scalar_value(value: np.ndarray | Any) -> Any:
    return value.item() if hasattr(value, "shape") and value.shape == () else value


def load_npz_visualization(file_path: Path, channel_filters: tuple[str, ...]) -> dict:
    try:
        with np.load(file_path, allow_pickle=False) as data:
            files = set(data.files)
            channels = [str(name) for name in data["channels"].tolist()] if "channels" in files else []

            if "data" in files:
                values = np.asarray(data["data"], dtype=np.float32)
                return {
                    "segment_index": int(scalar_value(data["segment_index"])) if "segment_index" in files else 0,
                    "total_segments": int(scalar_value(data["total_segments"])) if "total_segments" in files else 1,
                    "start_time": float(scalar_value(data["start_time"])) if "start_time" in files else 0.0,
                    "end_time": float(scalar_value(data["end_time"])) if "end_time" in files else 0.0,
                    "duration": float(scalar_value(data["duration"])) if "duration" in files else 0.0,
                    "scaling_factor": float(scalar_value(data["scaling_factor"])) if "scaling_factor" in files else 8000,
                    "channels": {
                        channel: values[index].tolist()
                        for index, channel in enumerate(channels)
                        if index < values.shape[0] and keep_channel(channel, channel_filters)
                    },
                }

            if "psd" in files:
                values = np.asarray(data["psd"], dtype=np.float32)
                frequencies = np.asarray(data["frequencies"], dtype=np.float32) if "frequencies" in files else np.array([], dtype=np.float32)
                return {
                    "frequencies": frequencies.tolist(),
                    "psd": {
                        channel: values[index].tolist()
                        for index, channel in enumerate(channels)
                        if index < values.shape[0] and keep_channel(channel, channel_filters)
                    },
                }
    except Exception as exc:
        print(f"Failed to load NPZ visualization {file_path}: {exc}")

    return {}


def load_json_visualization(file_path: Path, channel_filters: tuple[str, ...]) -> dict:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load visualization {file_path}: {exc}")
        return {}

    channels = data.get("channels")
    data["channels"] = {
        name: values for name, values in channels.items() if keep_channel(name, channel_filters)
    } if isinstance(channels, dict) else {}

    psd = data.get("psd")
    if isinstance(psd, dict):
        data["psd"] = {
            name: values for name, values in psd.items() if keep_channel(name, channel_filters)
        }

    return data


def load_visualization(file_path: Path, channel_filters: tuple[str, ...]) -> dict:
    resolved = resolve_visualization_file(file_path)
    if resolved is None:
        return {}
    if resolved.suffix.lower() == ".npz":
        return load_npz_visualization(resolved, channel_filters)
    return load_json_visualization(resolved, channel_filters)
