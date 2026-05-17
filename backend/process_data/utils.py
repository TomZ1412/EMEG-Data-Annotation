import os
import mne
import time
import random
import numpy as np
import torch
from constant import SAMPLE_RATE, LOW, HIGH, NEW_DEVICE_DATASET_LIST
import json
# from factory.brain_constant import (
from brain_constant import (
    EXCLUDE_DICT,
    RENAME_DICT,
    HPI_LIST,
    MONTAGE_DICT,
    CUSTOM_MONTAGE_DICT,
    SENSOR_TYPE_DICT,
    CUSTOM_TYPE_DICT
)
from accessor import DataAccessor, write_torch_warpper
from typing import List

DEFAULT_VIS_SCALING_FACTOR = 8000

# def filter_channel(raw, dataset: str):
#     exclude = []
#     if dataset in EXCLUDE_DICT.keys():
#         exclude = EXCLUDE_DICT[dataset]

#     for i in ["HEO", "VEO", "EKG", "EMG"]:
#         if i in raw.info.ch_names and i not in exclude:
#             exclude.append(i)

#     if dataset == "Omega":
#         indices = mne.pick_types(
#             raw.info, meg=True, eeg=False, ref_meg=False, exclude=exclude
#         )
#     else:
#         indices = mne.pick_types(
#             raw.info, meg=True, eeg=True, ref_meg=False, exclude=exclude
#         )
#     raw.pick(indices)
#     return raw


# def rename_channel(raw, dataset: str):
#     if dataset in RENAME_DICT.keys():
#         raw.rename_channels(RENAME_DICT[dataset])
#     return raw


# def set_montage(raw, dataset: str):
#     if dataset not in MONTAGE_DICT.keys() and dataset not in CUSTOM_MONTAGE_DICT.keys():
#         return raw
#     if dataset in CUSTOM_MONTAGE_DICT.keys():
#         montage = mne.channels.read_custom_montage(CUSTOM_MONTAGE_DICT[dataset])
#         raw.set_montage(montage)
#         return raw
#     montage = mne.channels.make_standard_montage(MONTAGE_DICT[dataset])
#     raw.set_montage(montage)
#     return raw


# def extract_pos_sensor_type(info):
#     """
#     kind = {1(FIFFV_MEG_CH), 2(FIFFV_EEG_CH)}
#     coil_type = {
#         1(FIFFV_COIL_EEG),
#         4001(FIFFV_COIL_MAGNES_MAG),
#         3012(FIFFV_COIL_VV_PLANAR_T1),
#         201609,                          #(AXIAL_GRAD)
#         5001,                            #(AXIAL_GRAD)
#         3022(FIFFV_COIL_VV_MAG_T1),
#         3024(FIFFV_COIL_VV_MAG_T3),
#         6001(FIFFV_COIL_KIT_GRAD),
#     }
#     """
#     pos = []
#     sensor_type = []
#     # kind_dict = {1: "meg", 2: "eeg"}
#     for i in info["chs"]:
#         kind = int(i["kind"])
#         assert kind in [1, 2], f"Unknown sensor kind:{i['kind']}"
#         coil_type = str(i["coil_type"])
#         # eeg
#         if kind == 2:
#             pos.append(np.hstack([i["loc"][:3], np.array([0.0, 0.0, 0.0])]))
#             sensor_type.append(SENSOR_TYPE_DICT["EEG"])
#         # meg
#         else:
#             xyz = i["loc"][:3]
#             dir_idx = 3
#             if "PLANAR" in coil_type:
#                 dir_idx = 1
#             dir = i["loc"][3 * dir_idx : 3 * (dir_idx + 1)]
#             pos.append(np.hstack([xyz, dir]))

#             if "MAG" in coil_type:
#                 sensor_type.append(SENSOR_TYPE_DICT["MAG"])
#             else:
#                 sensor_type.append(SENSOR_TYPE_DICT["GRAD"])

#     pos = np.stack(pos).astype(np.float32)
#     sensor_type = np.array(sensor_type).astype(np.int32)

#     return pos, sensor_type


# def get_sensor_type_mask(sensor_type: np.ndarray):
#     eeg_mask = sensor_type == SENSOR_TYPE_DICT["EEG"]
#     mag_mask = sensor_type == SENSOR_TYPE_DICT["MAG"]
#     grad_mask = sensor_type == SENSOR_TYPE_DICT["GRAD"]
#     meg_mask = mag_mask | grad_mask
#     return eeg_mask, mag_mask, grad_mask, meg_mask


# def _auto_detect_bad_channels(raw_data: mne.io.Raw, threshold: int = 10):
#     spectrum = raw_data.compute_psd(tmax=1000000, average="mean", verbose=False)  # fmax
#     data = spectrum.data + 1e-16
#     ch_names = np.array(spectrum.ch_names)
#     log_data = np.log(data)
#     # Euclidean distance between channel pairs
#     distances = np.linalg.norm(log_data[:, None, :] - log_data[None, :, :], axis=2)
#     mean_distances = np.mean(distances, axis=1)

#     # Use IQR (interquartile range) to identify outliers
#     Q1 = np.percentile(mean_distances, 25)
#     Q3 = np.percentile(mean_distances, 75)
#     IQR = Q3 - Q1
#     threshold_upper = Q3 + threshold * IQR
#     threshold_lower = Q1 - threshold * IQR

#     outlier_indices = np.where(
#         (mean_distances > threshold_upper) | (mean_distances < threshold_lower)
#     )[0]
#     bad_channels = ch_names[outlier_indices].tolist()

#     return bad_channels


# def auto_detect_bad_channels(raw: mne.io.Raw, eeg_mask, mag_mask, grad_mask):
#     bad_channels = []
#     if eeg_mask.any():
#         bad_channels += _auto_detect_bad_channels(
#             raw.copy().pick(picks=mne.pick_types(raw.info, eeg=True))
#         )
#     return bad_channels


# def filter_resample_preprocess(raw, dataset: str):
#     notch_freqs = [50, 60]
#     if len(notch_freqs) > 0:
#         raw = raw.notch_filter(freqs=notch_freqs, verbose=False)
#     if dataset in HPI_LIST:
#         raw = mne.chpi.filter_chpi(raw, include_line=False, verbose=False)
#     raw = raw.resample(SAMPLE_RATE, verbose=False, n_jobs=2)
#     raw = raw.filter(LOW, HIGH, verbose=False)
#     return raw


# def normalize_pos(pos: np.ndarray, eeg_mask, meg_mask):
#     if eeg_mask.any():
#         eeg_mean = np.mean(pos[eeg_mask, :3], axis=0, keepdims=True)
#         pos[eeg_mask, :3] -= eeg_mean
#         eeg_scale = np.sqrt(3 * np.mean(np.sum(pos[eeg_mask, :3] ** 2, axis=1)))
#         pos[eeg_mask, :3] /= eeg_scale
#     if meg_mask.any():
#         meg_mean = np.mean(pos[meg_mask, :3], axis=0, keepdims=True)
#         pos[meg_mask, :3] -= meg_mean
#         meg_scale = np.sqrt(3 * np.mean(np.sum(pos[meg_mask, :3] ** 2, axis=1)))
#         pos[meg_mask, :3] /= meg_scale
#     return pos


# def sensortype_wise_normalize(
#     _data: np.ndarray, eeg_mask, mag_mask, grad_mask
# ):
#     data = _data.copy()
#     if eeg_mask.any():
#         eeg_data = data[eeg_mask, :]
#         eeg_mean = np.mean(eeg_data, axis=0, keepdims=True)
#         eeg_data = eeg_data - eeg_mean
#         eeg_std = np.std(eeg_data) + 1.0e-5
#         data[eeg_mask, :] = eeg_data / (eeg_std)

#     if mag_mask.any():
#         mag_data = data[mag_mask, :]
#         mag_mean = np.mean(mag_data, axis=0, keepdims=True)
#         mag_data = mag_data - mag_mean
#         mag_std = np.std(mag_data) + 1.0e-13
#         data[mag_mask, :] = mag_data / mag_std

#     if grad_mask.any():
#         grad_data = data[grad_mask, :]
#         grad_mean = np.mean(grad_data, axis=0, keepdims=True)
#         grad_data = grad_data - grad_mean
#         grad_std = np.std(grad_data) + 1.0e-13
#         data[grad_mask, :] = grad_data / grad_std

#     return data.astype(np.float32)


# def accept_segment(seg_data: np.ndarray, pos: np.ndarray):
#     bad = (np.isnan(seg_data).any()) | (np.isnan(pos).any())
#     return ~bad

def is_finite(x):
    return np.isfinite(x).all()


def arrays_to_tensors(*arrays: np.ndarray) -> List[torch.Tensor]:
    return [torch.from_numpy(arr) for arr in arrays]

def filter_channel(raw, exclude: List[str] = None, remove_bad: bool = True):
    if exclude == None:
        exclude = ["EOG", "EKG", "EMG", "ECG", "EXG", "emg", "ecg", "VEO", "HEO"]
    else:
        exclude = [
            "EOG",
            "EKG",
            "EMG",
            "ECG",
            "EXG",
            "emg",
            "ecg",
            "VEO",
            "HEO",
        ] + exclude
    channels_to_remove = raw.info["bads"] if remove_bad else []
    for i in raw.ch_names:
        for j in exclude:
            if j in i:
                channels_to_remove.append(i)
                break
    channels_to_remove = list(set(channels_to_remove))
    indices = mne.pick_types(
        raw.info,
        meg=True,
        eeg=True,
        ecog=True,
        seeg=True,
        ref_meg=False,
        exclude=channels_to_remove,
    )
    raw.pick(indices)
    return raw


def rename_channel(raw, rename_channels_map=None):
    if isinstance(rename_channels_map, dict):
        raw.rename_channels(rename_channels_map)
    elif callable(rename_channels_map):
        raw.rename_channels({i: rename_channels_map(i) for i in raw.ch_names})
    return raw


def set_montage(raw, standard_montage: str = None, custom_montage: str = None):
    if standard_montage == None and custom_montage == None:
        return raw
    if standard_montage != None:
        montage = mne.channels.make_standard_montage(standard_montage)
    if custom_montage != None:
        montage = mne.channels.read_custom_montage(custom_montage)
    exclude = [i for i in raw.info.ch_names if i not in montage.ch_names]
    indices = mne.pick_types(
        raw.info, meg=True, eeg=True, ref_meg=False, exclude=exclude
    )
    raw.pick(indices)
    raw.set_montage(montage)
    return raw


def set_channel_type(raw, custom_type: dict = None):
    if custom_type != None:
        for i in range(len(raw.info["chs"])):
            raw.info["chs"][i]["kind"] = custom_type.get(
                raw.info["chs"][i]["ch_name"], raw.info["chs"][i]["kind"]
            )
    return raw


def extract_pos_sensor_type(info):
    sensor_type = [-1] * len(info["chs"])
    eeg_indices = mne.pick_types(info, eeg=True)
    mag_indices = mne.pick_types(info, meg="mag")
    grad_indices = mne.pick_types(info, meg="grad")
    ecog_indices = mne.pick_types(info, ecog=True)
    seeg_indices = mne.pick_types(info, seeg=True)
    for i in eeg_indices:
        sensor_type[i] = SENSOR_TYPE_DICT["EEG"]
    for i in mag_indices:
        sensor_type[i] = SENSOR_TYPE_DICT["MAG"]
    for i in grad_indices:
        sensor_type[i] = SENSOR_TYPE_DICT["GRAD"]
    for i in ecog_indices:
        sensor_type[i] = SENSOR_TYPE_DICT["ECOG"]
    for i in seeg_indices:
        sensor_type[i] = SENSOR_TYPE_DICT["SEEG"]
    pos = []
    for i in range(len(sensor_type)):
        channel_info = info["chs"][i]
        coil_type = str(channel_info["coil_type"])
        if sensor_type[i] not in [SENSOR_TYPE_DICT["MAG"], SENSOR_TYPE_DICT["GRAD"]]:
            pos.append(np.hstack([channel_info["loc"][:3], np.array([0.0, 0.0, 0.0])]))
        else:
            xyz = channel_info["loc"][:3]
            dir_idx = 3
            if "PLANAR" in coil_type:
                dir_idx = 1
            dir = channel_info["loc"][3 * dir_idx : 3 * (dir_idx + 1)]
            pos.append(np.hstack([xyz, dir]))

    sensor_type = np.array(sensor_type, dtype=np.int32)
    pos = np.stack(pos).astype(np.float32)
    return pos, sensor_type


def get_sensor_type_mask(sensor_type: np.ndarray):
    eeg_mask = sensor_type == SENSOR_TYPE_DICT["EEG"]
    mag_mask = sensor_type == SENSOR_TYPE_DICT["MAG"]
    grad_mask = sensor_type == SENSOR_TYPE_DICT["GRAD"]
    ecog_mask = sensor_type == SENSOR_TYPE_DICT["ECOG"]
    seeg_mask = sensor_type == SENSOR_TYPE_DICT["SEEG"]
    meg_mask = mag_mask | grad_mask
    return eeg_mask, meg_mask, ecog_mask, seeg_mask


def split_to_segments_save(
    accessor: DataAccessor,
    data: np.ndarray,
    sfreq: int,
    wav_ch_names: list,
    psd: np.ndarray,
    psd_freqs: list,
    psd_ch_names: list,
    # pos: np.ndarray,
    # sensor_type: np.ndarray,
    # eeg_mask: np.ndarray,
    # mag_mask: np.ndarray,
    # grad_mask: np.ndarray,
    # meg_mask: np.ndarray,
    path: str,
    dataset: str,
    ready_path: str,
    TIME:int,
    STRIDE:int
):
    segments_metadata = []
    start = 0
    # end = int(start + TIME * SAMPLE_RATE)
    # stride_length = int(STRIDE * SAMPLE_RATE)
    end = int(start + TIME * sfreq)
    stride_length = int(STRIDE * sfreq)
    # print(stride_length)
    # print(sfreq)
    # print(end)
    n_segments = data.shape[1] // stride_length + 1
    # dataset_name = accessor.get_dataset_folder_name(path)
    dataset_name = dataset

    dataset_to_file_path = f"{dataset_name}/" + path.split(f"/{dataset_name}/")[-1]
    brain_file_folder_path = os.path.join(ready_path, dataset_to_file_path).rsplit(
        ".", 1
    )[0]
    # accessor.mkdir(brain_file_folder_path)
    # import pdb;pdb.set_trace()
    # accessor.mkdir(os.path.dirname(brain_file_folder_path))
    os.makedirs(os.path.dirname(brain_file_folder_path),exist_ok=True)
    peak_to_peak = np.ptp(data, axis=1)
    percentile_20 = np.percentile(peak_to_peak, 20)
    scale_factor = 0
    if percentile_20 > 0:
        scale_factor = 2.5 / percentile_20
    else:
        scale_factor = 1.0
    
    # psd_path = os.path.join(
    #             brain_file_folder_path, f"psd.json"
    #         )
    psd_path = brain_file_folder_path + "_psd.npz"
    np.savez_compressed(
        psd_path,
        kind=np.array("psd"),
        frequencies=np.asarray(psd_freqs, dtype=np.float32),
        psd=np.asarray(psd, dtype=np.float32),
        channels=np.asarray(psd_ch_names),
    )
    # while end < data.shape[1]:
    while start < data.shape[1]:
        # seg_data, _ = sensortype_wise_normalize(
        #     data[:, start:end], eeg_mask, mag_mask, grad_mask, meg_mask
        # )
        seg_data = data[:, start:end]
        # if accept_segment(seg_data, pos):
        if True:
            # seg_data_path = os.path.join(
            #     brain_file_folder_path, f"{len(segments_metadata)}_data.pt"
            # )
            # seg_data_dict = {
            #     "x": torch.from_numpy(seg_data),
            #     "pos": torch.from_numpy(pos),
            #     "sensor_type": torch.from_numpy(sensor_type),
            # }
            # accessor.write(seg_data_dict, seg_data_path, write_torch_warpper)
            # seg_data_path = os.path.join(
            #     brain_file_folder_path, f"wav_{len(segments_metadata)}.json"
            # )
            seg_data_path = brain_file_folder_path + f"_wav_{len(segments_metadata)}.npz"
            np.savez_compressed(
                seg_data_path,
                kind=np.array("wav"),
                data=np.asarray(seg_data, dtype=np.float32),
                channels=np.asarray(wav_ch_names),
                segment_index=np.int32(len(segments_metadata)),
                total_segments=np.int32(n_segments),
                start_time=np.float32(start / sfreq),
                end_time=np.float32(end / sfreq),
                duration=np.float32((end - start) / sfreq),
                sfreq=np.float32(sfreq),
                scaling_factor=np.float32(scale_factor if scale_factor > 0 else DEFAULT_VIS_SCALING_FACTOR),
            )
            # import pdb;pdb.set_trace()
            time.sleep(0.01)
            metadata = {
                "dataset": dataset,
                "path": seg_data_path,
                "channels": seg_data.shape[0],
                # "is_eeg": bool((sensor_type == SENSOR_TYPE_DICT["EEG"]).all()),
                # "is_meg": bool(
                #     (
                #         (sensor_type == SENSOR_TYPE_DICT["MAG"])
                #         | (sensor_type == SENSOR_TYPE_DICT["GRAD"])
                #     ).all()
                # ),
            }
            segments_metadata.append(metadata)
        start += stride_length
        end += stride_length
    return segments_metadata


def split_pretrain_metadata(data):
    new_device_dataset_dict = {}
    for dataset in NEW_DEVICE_DATASET_LIST:
        new_device_dataset_dict[dataset] = [i for i in data if i["dataset"] == dataset]
    data = [i for i in data if i["dataset"] not in NEW_DEVICE_DATASET_LIST]
    random.shuffle(data)
    N = len(data)
    train = data[: int(N * 0.85)]
    val = data[int(N * 0.85) : int(N * 0.95)]
    test = data[int(N * 0.95) :]
    return train, val, test, new_device_dataset_dict

import math
def filter_resample_preprocess(raw):
    raw = raw.notch_filter(freqs=[50, 60], verbose=False)
    raw = raw.filter(
        0.5,
        math.floor(min(SAMPLE_RATE / 3.0, raw.info["sfreq"] / 3.0)),
        verbose=False,
    )
    raw = raw.resample(SAMPLE_RATE, verbose=False)
    return raw

def process(
    accessor: DataAccessor,
    path: str,
    dataset: str,
    ready_path: str,
    TIME:int,
    STRIDE:int
):
    # raw = accessor.read_brain_file(path)
    # raw = filter_channel(raw)
    # raw = rename_channel(raw)

    # raw = set_montage(raw, dataset)

    # # pos, sensor_type = extract_pos_sensor_type(raw.info)
    # # eeg_mask, mag_mask, grad_mask, meg_mask = get_sensor_type_mask(sensor_type)
    # # pos = normalize_pos(pos, eeg_mask, meg_mask)

    # raw = filter_resample_preprocess(raw, dataset)
    
    # raw = raw.drop channels(
    #     [i["ch name"] for i in raw.info["chs"] if not is finite(i["loc"][:3])]
    # )
    # # bad_channels = auto_detect_bad_channels(raw, eeg_mask, mag_mask, grad_mask)
    # # if len(bad_channels) > 0:
    # #     raw.info["bads"] += bad_channels
    # # raw.interpolate_bads(
    # #     reset_bads=True, mode="accurate", origin=(0.0, 0.0, 0.04), verbose=False
    # # )
    # import pdb;pdb.set_trace()
    raw = accessor.read_brain_file(path)
    raw = filter_channel(raw, exclude=EXCLUDE_DICT.get(dataset, lambda _: None)(path))  # 用于广泛的去除通道，并且通过exclude去除一些特别情形（比如原始的type没设置正确）
    raw = rename_channel(raw, rename_channels_map=RENAME_DICT.get(dataset, None))  # 仅用于montage命名矫正
    raw = set_montage(
        raw, standard_montage=MONTAGE_DICT.get(dataset, None), 
    )  # 用于补充loc
    try:
        raw = raw.drop_channels(
            [i["ch_name"] for i in raw.info["chs"] if not is_finite(i["loc"][:3])]
        )
    except Exception as e:
        pass
    raw = set_channel_type(raw, custom_type=CUSTOM_TYPE_DICT.get(dataset, lambda _: None)(path))
    raw = filter_resample_preprocess(raw)  
    data = raw.get_data()
    sfreq = raw.info['sfreq']
    wav_ch_names = raw.ch_names
    psd = raw.compute_psd()
    psd_data = psd.get_data()
    psd_freqs = psd.freqs
    psd_freqs = psd_freqs.tolist()
    psd_ch_names = psd.ch_names
    del raw
    # data float64 everything not normalized
    segments_metadata = split_to_segments_save(
        accessor,
        data,
        sfreq,
        wav_ch_names,
        psd_data,
        psd_freqs,
        psd_ch_names,
        # pos,
        # sensor_type,
        # eeg_mask,
        # mag_mask,
        # grad_mask,
        # meg_mask,
        path,
        dataset,
        ready_path,
        TIME,
        STRIDE
    )
    return segments_metadata, path
