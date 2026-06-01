from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CHANNEL_FILTERS = ("HEO", "VEO", "EKG", "EMG", "PHOTIC")
DEFAULT_FILE_SUFFIXES = ("con", "edf", "fif", "dat", "ds", "set", "bdf", "eeg", "vhdr")


@dataclass(frozen=True)
class DataProfile:
    raw_data_root: Path
    vis_data_root: Path
    annotation_file: Path
    dropped_dataset_path: Path
    cache_tree_path: Path
    file_suffixes: tuple[str, ...] = DEFAULT_FILE_SUFFIXES
    channel_filters: tuple[str, ...] = DEFAULT_CHANNEL_FILTERS
    skip_dirs: tuple[str, ...] = ("code", "stimuli", "derivatives")
    skip_exact_dirs: tuple[str, ...] = field(default_factory=tuple)
    dataset_filters: tuple[str, ...] = field(default_factory=tuple)
    root_numeric_range: tuple[int, int] | None = None
    data_source: str = "processed"
    allow_open_annotated: bool = True
    show_existing_annotations: bool = True
    show_annotation_layers: bool = True
    annotation_scope: str = "shared"
    annotation_mode: str = "bad_channel"
    score_annotation_file: Path | None = None


PROFILES = {
    "not_used": DataProfile(
        raw_data_root=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/not_used/tug_eeg/edf"),
        vis_data_root=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/not_used/processed/sfreq_256_low_0.1_high_96_time_30_stride_30/edf"),
        annotation_file=Path("/mnt/petrelfs/xiaoqinfan/ZZH/code/check_tug/bad_channels_log.jsonl"),
        dropped_dataset_path=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data_annotation_result/dropped_dataset.json"),
        cache_tree_path=Path("/mnt/petrelfs/xiaoqinfan/ZZH/code/backend/app/file_tree_cache"),
        root_numeric_range=(13, 13),
    ),
    "annotate": DataProfile(
        raw_data_root=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/pretrain/annotate_v2"),
        vis_data_root=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/pretrain/annotate_v2/processed/sfreq_256_low_0.1_high_96_time_30_stride_30"),
        annotation_file=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data_annotation_result/bad_channels_final_v2.jsonl"),
        dropped_dataset_path=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data_annotation_result/dropped_dataset.json"),
        cache_tree_path=Path("/mnt/petrelfs/xiaoqinfan/ZZH/code/backend/app_annotate/file_tree_cache"),
        skip_exact_dirs=("ds004381-1.0.2", "ds004408-1.0.8", "ds005262-1.0.1"),
    ),
    "check": DataProfile(
        raw_data_root=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/pretrain/check_processed"),
        vis_data_root=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/pretrain/check_processed/sfreq_256_low_0.1_high_96_time_30_stride_30"),
        annotation_file=Path("/mnt/petrelfs/xiaoqinfan/ZZH/code/backend/process_data/brainfiles_metadata.jsonl"),
        dropped_dataset_path=Path("/mnt/petrelfs/xiaoqinfan/ZZH/data_annotation_result/dropped_dataset.json"),
        cache_tree_path=Path("/mnt/petrelfs/xiaoqinfan/ZZH/code/backend/app_check/file_tree_cache"),
    ),
}


def _path_from_env(name: str, fallback: Path) -> Path:
    return Path(os.getenv(name, str(fallback)))


def _bool_from_env(name: str, fallback: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_from_env(name: str, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return fallback
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _default_score_annotation_file(annotation_file: Path) -> Path:
    return annotation_file.with_name(f"{annotation_file.stem}_scores{annotation_file.suffix}")


def load_profile(profile_name: str | None = None) -> DataProfile:
    name = profile_name or os.getenv("ANNO_PROFILE", "not_used")
    base = PROFILES.get(name)
    if base is None:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(f"Unknown ANNO_PROFILE '{name}'. Available profiles: {available}")

    suffixes = os.getenv("ANNO_FILE_SUFFIXES")
    channel_filters = os.getenv("ANNO_CHANNEL_FILTERS")
    annotation_file = _path_from_env("ANNO_ANNOTATION_FILE", base.annotation_file)
    score_annotation_file = _path_from_env(
        "ANNO_SCORE_ANNOTATION_FILE",
        base.score_annotation_file or _default_score_annotation_file(annotation_file),
    )

    return DataProfile(
        raw_data_root=_path_from_env("ANNO_RAW_DATA_ROOT", base.raw_data_root),
        vis_data_root=_path_from_env("ANNO_VIS_DATA_ROOT", base.vis_data_root),
        annotation_file=annotation_file,
        dropped_dataset_path=_path_from_env("ANNO_DROPPED_DATASET_PATH", base.dropped_dataset_path),
        cache_tree_path=_path_from_env("ANNO_CACHE_TREE_PATH", base.cache_tree_path),
        file_suffixes=tuple(s.strip().lower() for s in suffixes.split(",")) if suffixes else base.file_suffixes,
        channel_filters=tuple(s.strip() for s in channel_filters.split(",")) if channel_filters else base.channel_filters,
        skip_dirs=base.skip_dirs,
        skip_exact_dirs=base.skip_exact_dirs,
        dataset_filters=_csv_from_env("ANNO_DATASETS", base.dataset_filters),
        root_numeric_range=base.root_numeric_range,
        data_source=os.getenv("ANNO_DATA_SOURCE", base.data_source).strip().lower(),
        allow_open_annotated=_bool_from_env("ANNO_ALLOW_OPEN_ANNOTATED", base.allow_open_annotated),
        show_existing_annotations=_bool_from_env("ANNO_SHOW_EXISTING_ANNOTATIONS", base.show_existing_annotations),
        show_annotation_layers=_bool_from_env("ANNO_SHOW_ANNOTATION_LAYERS", base.show_annotation_layers),
        annotation_scope=os.getenv("ANNO_ANNOTATION_SCOPE", base.annotation_scope).strip().lower(),
        annotation_mode=os.getenv("ANNO_ANNOTATION_MODE", base.annotation_mode).strip().lower(),
        score_annotation_file=score_annotation_file,
    )
