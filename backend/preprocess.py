import time
from pathlib import Path

import mne
import numpy as np
from tqdm import tqdm

from app.config import RAW_DATA_ROOT, VIS_DATA_ROOT


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


def collect_input_files(root: Path, max_folders: int) -> list[Path]:
    folders = sorted([item for item in root.iterdir() if item.is_dir()])[:max_folders]
    allowed_files: list[Path] = []

    print(f"Found {len(folders)} top-level folders to process.")
    for index, folder in enumerate(folders, 1):
        print(f"  {index}. {folder.name}")
        for item in folder.rglob("*"):
            if item.is_file() and item.suffix.lower() in FILE_EXTENSIONS:
                allowed_files.append(item)
            elif item.is_dir() and item.name.endswith(".ds"):
                allowed_files.append(item)

    return allowed_files


def preprocess_dataset_all(skip_existing: bool = True, delta_t: int = 30, max_folders: int = 5):
    """
    Traverse RAW_DATA_ROOT, keep the existing preprocessing logic, and save visualization
    data as compressed float32 NPZ files instead of JSON.
    """
    data_root = Path(RAW_DATA_ROOT)
    output_root = Path(VIS_DATA_ROOT)

    print(f"RAW_DATA_ROOT: {data_root}")
    print(f"VIS_DATA_ROOT: {output_root}")

    start_time = time.time()
    allowed_files = collect_input_files(data_root, max_folders)
    print(f"Scan finished in {time.time() - start_time:.2f}s, found {len(allowed_files)} files.")

    if not allowed_files:
        print("No supported EEG files found.")
        return

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
    preprocess_dataset_all(max_folders=10)
