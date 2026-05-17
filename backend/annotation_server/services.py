from __future__ import annotations

import time
from pathlib import Path

from .config import DataProfile
from .storage import load_annotations, load_visualization, read_json, resolve_visualization_file, write_json


class AnnotationLocks:
    def __init__(self, timeout_seconds: int = 300):
        self.timeout_seconds = timeout_seconds
        self.active: dict[str, dict] = {}

    def cleanup(self) -> None:
        now = time.time()
        expired = [
            file_path
            for file_path, info in self.active.items()
            if now - info["timestamp"] > self.timeout_seconds
        ]
        for file_path in expired:
            self.active.pop(file_path, None)

    def acquire(self, file_path: str, user: str) -> bool:
        self.cleanup()
        current = self.active.get(file_path)
        if current and current["user"] != user:
            return False
        self.active[file_path] = {"user": user, "timestamp": time.time()}
        return True

    def release(self, file_path: str, user: str) -> None:
        current = self.active.get(file_path)
        if current and current["user"] == user:
            self.active.pop(file_path, None)

    def keep_alive(self, file_path: str, user: str) -> None:
        current = self.active.get(file_path)
        if current and current["user"] == user:
            current["timestamp"] = time.time()

    def is_occupied_by_other(self, file_path: str, user: str) -> bool:
        current = self.active.get(file_path)
        return bool(current and current["user"] != user)


def downsample_data(data: list[float], target_points: int = 1500) -> list[float]:
    if len(data) <= target_points:
        return data

    chunk_size = max(1, len(data) // max(1, target_points // 2))
    downsampled = []
    for start in range(0, len(data), chunk_size):
        chunk = data[start:start + chunk_size]
        if chunk:
            downsampled.extend((max(chunk), min(chunk)))
    return downsampled[:target_points]


def build_visualization_path(profile: DataProfile, file_path: str) -> Path:
    source = Path(file_path)
    if not source.is_absolute() and source.parts and source.parts[0] in {"data", "mnt", "home", "opt"}:
        source = Path("/") / source

    try:
        source.relative_to(profile.vis_data_root)
        return source.with_suffix(".json")
    except ValueError:
        pass

    try:
        relative = source.relative_to(profile.raw_data_root)
        return profile.vis_data_root / relative.with_suffix(".json")
    except ValueError:
        if str(profile.raw_data_root) in str(source):
            return Path(str(file_path).replace(str(profile.raw_data_root), str(profile.vis_data_root))).with_suffix(".json")
        return source.with_suffix(".json")


def load_visualization_bundle(
    profile: DataProfile,
    file_path: str,
    sub_block: int,
    optimize: bool,
    max_points_per_channel: int,
) -> dict:
    vis_file = build_visualization_path(profile, file_path)
    base_name = vis_file.stem
    total_sub_blocks = 0
    if vis_file.parent.exists():
        total_sub_blocks = len({
            item.stem
            for item in vis_file.parent.glob(f"{base_name}_wav_*.*")
            if item.suffix.lower() in {".json", ".npz"}
        })

    wav_file = Path(str(vis_file).replace(".json", f"_wav_{sub_block}.json").replace("\\", "/"))
    psd_file = Path(str(vis_file).replace(".json", "_psd.json").replace("\\", "/"))
    result = {"totalSubBlocks": total_sub_blocks}

    wav_data = load_visualization(wav_file, profile.channel_filters)
    channels = wav_data.get("channels", {})
    if optimize:
        result["wav"] = {
            name: downsample_data(values, max_points_per_channel)
            for name, values in channels.items()
        }
    else:
        result["wav"] = channels

    result["scaling_factor"] = wav_data.get("scaling_factor", 8000) if wav_data else 8000
    result["psd"] = load_visualization(psd_file, profile.channel_filters) if resolve_visualization_file(psd_file) else {}
    return result


def load_dropped_datasets(profile: DataProfile) -> dict:
    data = read_json(profile.dropped_dataset_path, {"datasets": {}})
    return data.get("datasets", {})


def mark_dataset(profile: DataProfile, dataset_path: str, action: str) -> dict:
    data = read_json(profile.dropped_dataset_path, {"datasets": {}})
    data.setdefault("datasets", {})

    if action == "discard":
        from datetime import datetime
        data["datasets"][dataset_path] = {
            "is_discarded": True,
            "marked_at": datetime.now().isoformat(),
        }
    elif action == "cancel":
        data["datasets"].pop(dataset_path, None)

    write_json(profile.dropped_dataset_path, data)
    return {"success": True, "message": f"Dataset {dataset_path} {action}ed successfully"}


def flatten_files(tree: list[dict]) -> list[str]:
    files = []

    def visit(node: dict) -> None:
        if node.get("type") == "file":
            files.append(node["path"])
        for child in node.get("children", []):
            visit(child)

    for node in tree:
        visit(node)
    return sorted(files)


def next_available_file(
    tree: list[dict],
    annotation_file: Path,
    locks: AnnotationLocks,
    user: str,
    current_file: str | None,
) -> str | None:
    annotations = load_annotations(annotation_file)
    files = flatten_files(tree)
    if not files:
        return None

    try:
        current_index = files.index(current_file) if current_file else -1
    except ValueError:
        current_index = -1

    for offset in range(1, len(files) + 1):
        file_path = files[(current_index + offset) % len(files)]
        if file_path in annotations:
            continue
        if locks.is_occupied_by_other(file_path, user):
            continue
        locks.acquire(file_path, user)
        return file_path
    return None
