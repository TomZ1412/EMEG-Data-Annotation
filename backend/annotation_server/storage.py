from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from .config import DataProfile


PROCESSED_SUFFIXES = {".json", ".npz"}
ARTIFACT_WINDOW_SECONDS = 30


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


def annotation_scope_key(record: dict, scope: str = "shared") -> str:
    file_path = record.get("file_path")
    if not file_path:
        return ""
    if scope == "user":
        return f"{file_path}\0{record.get('user', '')}"
    return file_path


def load_annotations(
    annotation_file: Path,
    file_path: str | None = None,
    user: str | None = None,
    scope: str = "shared",
) -> dict:
    annotations = {}
    if not annotation_file.exists():
        return annotations if file_path is None else {}

    scope = scope if scope in {"shared", "user"} else "shared"

    try:
        with annotation_file.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    print(f"Skip invalid annotation line {annotation_file}:{line_number}: {exc}")
                    continue
                if scope == "user" and user is not None and record.get("user") != user:
                    continue
                key = annotation_scope_key(record, scope)
                if key:
                    annotations[key] = record
    except OSError as exc:
        print(f"Failed to load annotations {annotation_file}: {exc}")

    return annotations if file_path is None else find_annotation(annotations, file_path, user, scope)


def normalize_path_key(path: str | Path | None) -> str:
    if path is None:
        return ""
    normalized = str(path).replace("\\", "/").strip()
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized


def logical_annotation_key(path: str | Path | None) -> str:
    normalized = normalize_path_key(path)
    if not normalized:
        return ""

    path_obj = Path(normalized)
    stem = path_obj.stem
    suffix = path_obj.suffix.lower()

    if "_wav_" in stem:
        base, block = stem.rsplit("_wav_", 1)
        if block.isdigit():
            stem = base
    elif stem.endswith("_psd"):
        stem = stem[:-4]

    if suffix in PROCESSED_SUFFIXES:
        suffix = ".json"

    logical = str(path_obj.with_name(f"{stem}{suffix}")).replace("\\", "/")
    while "//" in logical:
        logical = logical.replace("//", "/")
    return logical


def annotation_key_variants(path: str | Path | None) -> set[str]:
    normalized = normalize_path_key(path)
    logical = logical_annotation_key(normalized)
    variants = {value for value in (normalized, logical) if value}

    for value in list(variants):
        variants.add(value.lstrip("/"))
        variants.add(f"/{value.lstrip('/')}")
        path_obj = Path(value)
        if path_obj.suffix.lower() == ".json":
            variants.add(str(path_obj.with_suffix(".npz")).replace("\\", "/"))
        elif path_obj.suffix.lower() == ".npz":
            variants.add(str(path_obj.with_suffix(".json")).replace("\\", "/"))

    return {normalize_path_key(value) for value in variants if value}


def scoped_lookup_key(path: str | Path, user: str | None, scope: str) -> str:
    if scope == "user":
        return f"{path}\0{user or ''}"
    return str(path)


def find_annotation(
    annotations: dict,
    file_path: str | Path,
    user: str | None = None,
    scope: str = "shared",
) -> dict:
    scope = scope if scope in {"shared", "user"} else "shared"
    direct_key = scoped_lookup_key(file_path, user, scope)
    if direct_key in annotations:
        return annotations[direct_key]

    variants = annotation_key_variants(file_path)
    for key in variants:
        lookup_key = scoped_lookup_key(key, user, scope)
        if lookup_key in annotations:
            return annotations[lookup_key]

    target_logical = logical_annotation_key(file_path).lstrip("/")
    if not target_logical:
        return {}

    for key, annotation in annotations.items():
        annotation_path = key.split("\0", 1)[0] if scope == "user" else key
        if logical_annotation_key(annotation_path).lstrip("/") == target_logical:
            return annotation

    return {}


def _as_channel_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _as_subblock_channels(value: Any) -> dict:
    if isinstance(value, dict):
        return {str(key): _as_channel_list(channels) for key, channels in value.items()}
    if isinstance(value, list):
        return {"0": value}
    return {}


def _as_score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    if 0 <= score <= 5:
        return score
    return None


def _as_channel_scores(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}

    scores = {}
    for channel, raw_score in value.items():
        score = _as_score(raw_score)
        if score is None or score == 0:
            continue
        scores[str(channel)] = score
    return scores


def _as_subblock_scores(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}

    subblock_scores = {}
    for key, raw_scores in value.items():
        scores = _as_channel_scores(raw_scores)
        if scores:
            subblock_scores[str(key)] = scores
    return subblock_scores


def _channels_at_threshold(scores: dict, threshold: int) -> list:
    return [
        channel
        for channel, score in scores.items()
        if isinstance(score, int) and score >= threshold
    ]


def _subblock_channels_at_threshold(subblock_scores: dict, threshold: int) -> dict:
    return {
        str(key): _channels_at_threshold(scores, threshold)
        for key, scores in subblock_scores.items()
        if _channels_at_threshold(scores, threshold)
    }


def _as_artifact_list(value: Any) -> list:
    if not isinstance(value, list):
        return []

    artifacts = []
    for item in value:
        if not isinstance(item, dict):
            continue
        channel = item.get("channel")
        start_time = item.get("start_time")
        end_time = item.get("end_time")
        if not channel:
            continue
        try:
            start = float(start_time)
            end = float(end_time)
        except (TypeError, ValueError):
            continue
        artifacts.append({
            "channel": str(channel),
            "start_time": min(start, end),
            "end_time": max(start, end),
        })
    return artifacts


def _as_subblock_artifacts(value: Any) -> dict:
    if isinstance(value, dict):
        return {str(key): _as_artifact_list(artifacts) for key, artifacts in value.items()}
    if isinstance(value, list):
        return {"0": _as_artifact_list(value)}
    return {}


def _as_artifacts(value: Any) -> list:
    if isinstance(value, list):
        return _as_artifact_list(value)
    if isinstance(value, dict):
        artifacts = []
        for key, items in value.items():
            try:
                offset = int(key) * ARTIFACT_WINDOW_SECONDS
            except (TypeError, ValueError):
                offset = 0
            for item in _as_artifact_list(items):
                artifacts.append({
                    "channel": item["channel"],
                    "start_time": item["start_time"] + offset,
                    "end_time": item["end_time"] + offset,
                })
        return artifacts
    return []


def normalize_annotation(record: dict) -> dict:
    legacy_bad_channels = record.get("bad_channels", [])
    legacy_subblock_bad_channels = record.get("subblock_bad_channels")
    psd_bad_channels = record.get("psd_bad_channels")
    wav_bad_channels = record.get("wav_bad_channels")
    artifacts = record.get("artifacts")

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
        "artifacts": _as_artifacts(artifacts),
        "discarded": bool(record.get("discarded", False)),
        "user": record.get("user", ""),
    }


def normalize_score_annotation(record: dict, score_threshold: int = 3) -> dict:
    if not record.get("file_path"):
        raise ValueError("file_path is required")

    threshold = _as_score(record.get("score_threshold"))
    if threshold is None:
        threshold = score_threshold
    threshold = max(0, min(5, int(threshold)))

    psd_scores = record.get("psd_channel_scores")
    if psd_scores is None:
        psd_scores = record.get("psd_scores")
    wav_scores = record.get("wav_channel_scores")
    if wav_scores is None:
        wav_scores = record.get("subblock_channel_scores")

    psd_channel_scores = _as_channel_scores(psd_scores)
    wav_channel_scores = _as_subblock_scores(wav_scores)
    psd_bad_channels = _channels_at_threshold(psd_channel_scores, threshold)
    wav_bad_channels = _subblock_channels_at_threshold(wav_channel_scores, threshold)

    return {
        "file_path": record["file_path"],
        "annotation_type": "channel_score",
        "psd_channel_scores": psd_channel_scores,
        "wav_channel_scores": wav_channel_scores,
        "subblock_channel_scores": wav_channel_scores,
        "score_threshold": threshold,
        "psd_bad_channels": psd_bad_channels,
        "wav_bad_channels": wav_bad_channels,
        "subblock_bad_channels": wav_bad_channels,
        "artifacts": _as_artifacts(record.get("artifacts")),
        "discarded": bool(record.get("discarded", False)),
        "user": record.get("user", ""),
    }


def write_annotation(annotation_file: Path, record: dict) -> None:
    if not record.get("file_path"):
        raise ValueError("file_path is required")

    annotation = normalize_annotation(record)

    annotation_file.parent.mkdir(parents=True, exist_ok=True)
    with annotation_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(annotation, ensure_ascii=False) + "\n")


def write_score_annotation(annotation_file: Path, record: dict, score_threshold: int = 3) -> None:
    annotation = normalize_score_annotation(record, score_threshold)

    annotation_file.parent.mkdir(parents=True, exist_ok=True)
    with annotation_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(annotation, ensure_ascii=False) + "\n")


def get_annotation_for_file(
    annotation_file: Path,
    file_path: str,
    user: str | None = None,
    scope: str = "shared",
) -> dict:
    annotation = load_annotations(annotation_file, file_path, user=user, scope=scope)
    if not annotation:
        return {
            "bad_channels": [],
            "psd_bad_channels": [],
            "wav_bad_channels": {},
            "subblock_bad_channels": {},
            "artifacts": {},
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
        "artifacts": _as_artifacts(annotation.get("artifacts")),
        "discarded": bool(annotation.get("discarded", False)),
    }


def get_score_annotation_for_file(
    annotation_file: Path,
    file_path: str,
    user: str | None = None,
    scope: str = "shared",
    score_threshold: int = 3,
) -> dict:
    annotation = load_annotations(annotation_file, file_path, user=user, scope=scope)
    if not annotation:
        return {
            "bad_channels": [],
            "psd_bad_channels": [],
            "wav_bad_channels": {},
            "subblock_bad_channels": {},
            "psd_channel_scores": {},
            "wav_channel_scores": {},
            "subblock_channel_scores": {},
            "score_threshold": score_threshold,
            "artifacts": [],
            "discarded": False,
        }

    payload = get_score_annotation_payload(annotation, score_threshold)
    return {
        "bad_channels": next(iter(payload["wav_bad_channels"].values()), []),
        **payload,
    }


def list_annotation_layers_for_file(
    annotation_file: Path,
    file_path: str,
) -> list[dict]:
    if not annotation_file.exists():
        return []

    target_variants = annotation_key_variants(file_path)
    target_logical = logical_annotation_key(file_path).lstrip("/")
    layers_by_user: dict[str, dict] = {}

    try:
        with annotation_file.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    print(f"Skip invalid annotation line {annotation_file}:{line_number}: {exc}")
                    continue

                record_path = record.get("file_path")
                if not record_path:
                    continue
                record_key = normalize_path_key(record_path)
                record_logical = logical_annotation_key(record_path).lstrip("/")
                if record_key not in target_variants and record_logical != target_logical:
                    continue

                try:
                    annotation = normalize_annotation(record)
                except (KeyError, TypeError, ValueError) as exc:
                    print(f"Skip invalid annotation record {annotation_file}:{line_number}: {exc}")
                    continue

                user = str(annotation.get("user") or "legacy")
                layers_by_user[user] = {
                    "user": user,
                    "annotation": get_annotation_payload(annotation),
                }
    except OSError as exc:
        print(f"Failed to load annotation layers {annotation_file}: {exc}")

    return [
        {"user": user, "annotation": layer["annotation"]}
        for user, layer in sorted(layers_by_user.items(), key=lambda item: item[0].lower())
    ]


def list_score_annotation_layers_for_file(
    annotation_file: Path,
    file_path: str,
    score_threshold: int = 3,
) -> list[dict]:
    if not annotation_file.exists():
        return []

    target_variants = annotation_key_variants(file_path)
    target_logical = logical_annotation_key(file_path).lstrip("/")
    layers_by_user: dict[str, dict] = {}

    try:
        with annotation_file.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    print(f"Skip invalid annotation line {annotation_file}:{line_number}: {exc}")
                    continue

                record_path = record.get("file_path")
                if not record_path:
                    continue
                record_key = normalize_path_key(record_path)
                record_logical = logical_annotation_key(record_path).lstrip("/")
                if record_key not in target_variants and record_logical != target_logical:
                    continue

                try:
                    annotation = normalize_score_annotation(record, score_threshold)
                except (KeyError, TypeError, ValueError) as exc:
                    print(f"Skip invalid score annotation record {annotation_file}:{line_number}: {exc}")
                    continue

                user = str(annotation.get("user") or "legacy")
                layers_by_user[user] = {
                    "user": user,
                    "annotation": get_score_annotation_payload(annotation, score_threshold),
                }
    except OSError as exc:
        print(f"Failed to load score annotation layers {annotation_file}: {exc}")

    return [
        {"user": user, "annotation": layer["annotation"]}
        for user, layer in sorted(layers_by_user.items(), key=lambda item: item[0].lower())
    ]


def get_annotation_payload(annotation: dict) -> dict:
    wav_bad_channels = _as_subblock_channels(
        annotation.get("wav_bad_channels") or annotation.get("subblock_bad_channels")
    )
    return {
        "bad_channels": next(iter(wav_bad_channels.values()), []),
        "psd_bad_channels": _as_channel_list(annotation.get("psd_bad_channels")),
        "wav_bad_channels": wav_bad_channels,
        "subblock_bad_channels": wav_bad_channels,
        "artifacts": _as_artifacts(annotation.get("artifacts")),
        "discarded": bool(annotation.get("discarded", False)),
    }


def get_score_annotation_payload(annotation: dict, score_threshold: int = 3) -> dict:
    threshold = _as_score(annotation.get("score_threshold"))
    if threshold is None:
        threshold = score_threshold
    threshold = max(0, min(5, int(threshold)))

    psd_channel_scores = _as_channel_scores(
        annotation.get("psd_channel_scores") or annotation.get("psd_scores")
    )
    wav_channel_scores = _as_subblock_scores(
        annotation.get("wav_channel_scores") or annotation.get("subblock_channel_scores")
    )
    psd_bad_channels = _channels_at_threshold(psd_channel_scores, threshold)
    wav_bad_channels = _subblock_channels_at_threshold(wav_channel_scores, threshold)

    return {
        "psd_bad_channels": psd_bad_channels,
        "wav_bad_channels": wav_bad_channels,
        "subblock_bad_channels": wav_bad_channels,
        "psd_channel_scores": psd_channel_scores,
        "wav_channel_scores": wav_channel_scores,
        "subblock_channel_scores": wav_channel_scores,
        "score_threshold": threshold,
        "artifacts": _as_artifacts(annotation.get("artifacts")),
        "discarded": bool(annotation.get("discarded", False)),
    }


def get_cache_key(root: Path) -> str:
    mtime = root.stat().st_mtime if root.exists() else 0
    return hashlib.md5(f"{root}_{mtime}".encode()).hexdigest()


def file_tree_cache_name(profile: DataProfile, prefix: str) -> str:
    dataset_key = ",".join(profile.dataset_filters) if profile.dataset_filters else "all"
    digest = hashlib.md5(dataset_key.encode()).hexdigest()[:8]
    return f"{prefix}_{digest}.pkl"


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
        cache_file = cache_dir / file_tree_cache_name(profile, f"tree_{profile.data_source}")
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
        if is_root_call and profile.dataset_filters and item.is_dir() and item.name not in profile.dataset_filters:
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
            with (cache_dir / file_tree_cache_name(profile, f"tree_{profile.data_source}")).open("wb") as handle:
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
        cache_file = cache_dir / file_tree_cache_name(profile, "tree_processed")
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
        if is_root_call and profile.dataset_filters and item.is_dir() and item.name not in profile.dataset_filters:
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
            with (cache_dir / file_tree_cache_name(profile, "tree_processed")).open("wb") as handle:
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
