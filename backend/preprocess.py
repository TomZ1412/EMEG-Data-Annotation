from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import mne
import numpy as np
from tqdm import tqdm

try:
    from app.config import RAW_DATA_ROOT, VIS_DATA_ROOT
except ModuleNotFoundError:
    from backend.app.config import RAW_DATA_ROOT, VIS_DATA_ROOT


FILE_EXTENSIONS = {".con", ".edf", ".fif", ".dat", ".bdf", ".set"}
DEFAULT_SCALING_FACTOR = 8000


def save_waveform_npz(
    output_file: Path,
    segment_data: np.ndarray,
    ch_names: list[str],
    segment_index: int,
    total_segments: int,
    start_sample: int,
    end_sample: int,
    sfreq: float,
) -> None:
    np.savez_compressed(
        output_file,
        kind=np.array("wav"),
        data=np.asarray(segment_data, dtype=np.float32),
        channels=np.asarray(ch_names),
        segment_index=np.int32(segment_index),
        total_segments=np.int32(total_segments),
        start_time=np.float32(start_sample / sfreq),
        end_time=np.float32(end_sample / sfreq),
        duration=np.float32((end_sample - start_sample) / sfreq),
        sfreq=np.float32(sfreq),
        scaling_factor=np.float32(DEFAULT_SCALING_FACTOR),
    )


def save_psd_npz(output_file: Path, psd_data: np.ndarray, freqs: np.ndarray, ch_names: list[str]) -> None:
    np.savez_compressed(
        output_file,
        kind=np.array("psd"),
        frequencies=np.asarray(freqs, dtype=np.float32),
        psd=np.asarray(psd_data, dtype=np.float32),
        channels=np.asarray(ch_names),
    )


def normalize_filter(values: str | list[str] | tuple[str, ...] | set[str] | None) -> set[str] | None:
    if values is None:
        return None
    if isinstance(values, str):
        values = [item.strip() for item in values.split(",")]
    normalized = {str(item).strip() for item in values if str(item).strip()}
    return normalized or None


def matches_subject(path: Path, subjects: set[str] | None) -> bool:
    if not subjects:
        return True
    return any(part in subjects for part in path.parts)


def get_subject_name(relative_path: Path) -> str:
    for part in relative_path.parts:
        if part.startswith("sub-"):
            return part
    return "__unknown_subject__"


def get_session_name(relative_path: Path) -> str | None:
    for part in relative_path.parts:
        if part.startswith("ses-"):
            return part
    return None


def file_allowed_by_rule(relative_path: Path, rule: dict) -> bool:
    subjects = normalize_filter(rule.get("subjects"))
    exclude_subjects = normalize_filter(rule.get("exclude_subjects"))
    sessions = normalize_filter(rule.get("sessions") or rule.get("include_sessions"))
    exclude_sessions = normalize_filter(rule.get("exclude_sessions"))

    subject = get_subject_name(relative_path)
    session = get_session_name(relative_path)

    if subjects and subject not in subjects:
        return False
    if exclude_subjects and subject in exclude_subjects:
        return False
    if sessions and session not in sessions:
        return False
    if exclude_sessions and session in exclude_sessions:
        return False
    return True


def load_selection_config(config_path: str | Path | None) -> dict | None:
    if not config_path:
        return None
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_files_for_dataset(folder: Path, root: Path, rule: dict) -> list[Path]:
    max_subjects = rule.get("max_subjects")
    max_files = rule.get("max_files")
    max_files_per_subject = rule.get("max_files_per_subject")

    selected: list[Path] = []
    subjects_seen: set[str] = set()
    files_per_subject: dict[str, int] = defaultdict(int)

    for item in sorted(folder.rglob("*")):
        # Keep .ds folders as raw inputs, but do not walk their internals as separate files.
        if item.is_file() and item.suffix.lower() not in FILE_EXTENSIONS:
            continue
        if not item.is_file() and not (item.is_dir() and item.name.endswith(".ds")):
            continue

        relative = item.relative_to(root)
        if not file_allowed_by_rule(relative, rule):
            continue

        subject = get_subject_name(relative)
        if max_subjects is not None and subject not in subjects_seen and len(subjects_seen) >= int(max_subjects):
            continue
        if max_files_per_subject is not None and files_per_subject[subject] >= int(max_files_per_subject):
            continue

        selected.append(item)
        subjects_seen.add(subject)
        files_per_subject[subject] += 1

        if max_files is not None and len(selected) >= int(max_files):
            break

    return selected


def collect_input_files_from_config(root: Path, config: dict) -> list[Path]:
    dataset_rules = config.get("datasets", {})
    if not isinstance(dataset_rules, dict) or not dataset_rules:
        raise ValueError("selection config must contain a non-empty 'datasets' object")

    selected: list[Path] = []
    for dataset_name, rule in dataset_rules.items():
        folder = root / dataset_name
        if not folder.exists() or not folder.is_dir():
            print(f"Skip missing dataset folder: {dataset_name}")
            continue
        rule = rule or {}
        dataset_files = collect_files_for_dataset(folder, root, rule)
        print(f"{dataset_name}: selected {len(dataset_files)} files")
        selected.extend(dataset_files)

    global_max_files = config.get("max_files")
    if global_max_files is not None:
        selected = selected[: int(global_max_files)]
    return selected


def collect_input_files(
    root: Path,
    max_folders: int | None = None,
    datasets: set[str] | None = None,
    subjects: set[str] | None = None,
    max_files: int | None = None,
) -> list[Path]:
    folders = sorted([item for item in root.iterdir() if item.is_dir()])
    if datasets:
        folders = [folder for folder in folders if folder.name in datasets]
    if max_folders is not None:
        folders = folders[:max_folders]

    allowed_files: list[Path] = []

    print(f"Found {len(folders)} top-level folders to process.")
    for index, folder in enumerate(folders, 1):
        print(f"  {index}. {folder.name}")
        for item in folder.rglob("*"):
            relative = item.relative_to(root)
            if not matches_subject(relative, subjects):
                continue
            if item.is_file() and item.suffix.lower() in FILE_EXTENSIONS:
                allowed_files.append(item)
            elif item.is_dir() and item.name.endswith(".ds"):
                allowed_files.append(item)
            if max_files is not None and len(allowed_files) >= max_files:
                return allowed_files

    return allowed_files


def preprocess_dataset_all(
    skip_existing: bool = True,
    delta_t: int = 30,
    max_folders: int | None = 5,
    datasets: str | list[str] | tuple[str, ...] | set[str] | None = None,
    subjects: str | list[str] | tuple[str, ...] | set[str] | None = None,
    max_files: int | None = None,
    selection_config: str | Path | dict | None = None,
):
    """
    Traverse RAW_DATA_ROOT, keep the existing preprocessing logic, and save visualization
    data as compressed float32 NPZ files instead of JSON.
    """
    data_root = Path(RAW_DATA_ROOT)
    output_root = Path(VIS_DATA_ROOT)

    print(f"RAW_DATA_ROOT: {data_root}")
    print(f"VIS_DATA_ROOT: {output_root}")

    start_time = time.time()
    config = selection_config if isinstance(selection_config, dict) else load_selection_config(selection_config)
    if config:
        print("Using selection config.")
        allowed_files = collect_input_files_from_config(data_root, config)
        print(f"Scan finished in {time.time() - start_time:.2f}s, selected {len(allowed_files)} files.")
        if not allowed_files:
            print("No supported EEG files selected.")
            return
        return process_files(allowed_files, data_root, output_root, skip_existing, delta_t)

    dataset_filter = normalize_filter(datasets)
    subject_filter = normalize_filter(subjects)

    if dataset_filter:
        print(f"Dataset filter: {', '.join(sorted(dataset_filter))}")
    if subject_filter:
        print(f"Subject filter: {', '.join(sorted(subject_filter))}")
    if max_files is not None:
        print(f"Max files: {max_files}")

    allowed_files = collect_input_files(
        data_root,
        max_folders=max_folders,
        datasets=dataset_filter,
        subjects=subject_filter,
        max_files=max_files,
    )
    print(f"Scan finished in {time.time() - start_time:.2f}s, found {len(allowed_files)} files.")

    if not allowed_files:
        print("No supported EEG files found.")
        return

    return process_files(allowed_files, data_root, output_root, skip_existing, delta_t)


def process_files(
    allowed_files: list[Path],
    data_root: Path,
    output_root: Path,
    skip_existing: bool,
    delta_t: int,
):

    successful_files = 0
    failed_files = 0

    with tqdm(total=len(allowed_files), desc="preprocess", unit="file") as pbar:
        for file in allowed_files:
            file_name = file.stem if file.is_file() else file.name
            try:
                dataset_path = file.relative_to(data_root).parent
                out_dir = output_root / dataset_path
                out_dir.mkdir(parents=True, exist_ok=True)

                pbar.set_description(f"processing: {file_name[:30]}")

                raw = mne.io.read_raw(file, preload=True, verbose=False)
                sfreq = raw.info["sfreq"]
                raw.pick_types(
                    meg=False,
                    eeg=True,
                    stim=False,
                    eog=False,
                    ecg=False,
                    emg=False,
                    misc=False,
                    ref_meg=False,
                    resp=False,
                    chpi=False,
                    exci=False,
                    ias=False,
                    syst=False,
                    seeg=False,
                    dipole=False,
                    gof=False,
                    bio=False,
                    ecog=False,
                    fnirs=False,
                    csd=False,
                    dbs=False,
                    temperature=False,
                    gsr=False,
                    eyetrack=False,
                    selection=None,
                    exclude="bads",
                )

                data = raw.get_data()
                ch_names = raw.ch_names
                _, n_times = data.shape
                samples_per_segment = int(delta_t * sfreq)
                n_segments = int(np.ceil(n_times / samples_per_segment))

                psd_file = out_dir / f"{file_name}_psd.npz"
                waveform_files_exist = all(
                    (out_dir / f"{file_name}_wav_{seg_idx}.npz").exists()
                    for seg_idx in range(n_segments)
                )

                if skip_existing and waveform_files_exist and psd_file.exists():
                    pbar.set_description(f"skipped: {file_name[:30]}")
                    successful_files += 1
                    pbar.update(1)
                    continue

                if not (skip_existing and psd_file.exists()):
                    psd = raw.compute_psd()
                    save_psd_npz(psd_file, psd.get_data(), psd.freqs, psd.ch_names)

                for seg_idx in range(n_segments):
                    waveform_file = out_dir / f"{file_name}_wav_{seg_idx}.npz"
                    if skip_existing and waveform_file.exists():
                        continue

                    start_sample = seg_idx * samples_per_segment
                    end_sample = min((seg_idx + 1) * samples_per_segment, n_times)
                    segment_data = data[:, start_sample:end_sample]
                    save_waveform_npz(
                        waveform_file,
                        segment_data,
                        ch_names,
                        seg_idx,
                        n_segments,
                        start_sample,
                        end_sample,
                        sfreq,
                    )

                successful_files += 1
                pbar.set_description(f"done: {file_name[:30]}")
                pbar.update(1)

            except Exception as exc:
                failed_files += 1
                pbar.set_description(f"failed: {file_name[:30]}")
                print(f"\nFailed to preprocess {file}: {exc}")
                pbar.update(1)

    print("\nPreprocess finished.")
    print(f"Total files: {len(allowed_files)}")
    print(f"Successful: {successful_files}")
    print(f"Failed: {failed_files}")
    print(f"Skipped: {len(allowed_files) - successful_files - failed_files}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess EEG files into compressed float32 NPZ visualization files.")
    parser.add_argument("--max-folders", type=int, default=10, help="Maximum number of top-level dataset folders to scan.")
    parser.add_argument("--datasets", default=None, help="Comma-separated dataset folder names, e.g. ds001785-1.1.1,ds002721-1.0.3.")
    parser.add_argument("--subjects", default=None, help="Comma-separated subject/session path parts, e.g. sub-01,sub-02.")
    parser.add_argument("--max-files", type=int, default=None, help="Maximum number of raw files to preprocess after filtering.")
    parser.add_argument("--selection-config", default=None, help="Path to a JSON file with per-dataset selection rules.")
    parser.add_argument("--delta-t", type=int, default=30, help="Segment duration in seconds.")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate files even when matching NPZ outputs already exist.")
    args = parser.parse_args()

    preprocess_dataset_all(
        skip_existing=not args.overwrite,
        delta_t=args.delta_t,
        max_folders=args.max_folders,
        datasets=args.datasets,
        subjects=args.subjects,
        max_files=args.max_files,
        selection_config=args.selection_config,
    )
