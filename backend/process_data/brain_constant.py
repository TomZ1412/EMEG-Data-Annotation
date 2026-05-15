import os
import pandas as pd
from mne.io.constants import FIFF
from constant import CUSTOM_FILE_PATH


def get_exclude_channel_for_ieeg_dataset(tsv_file: str):
    df = pd.read_csv(tsv_file, sep="\t")
    target_types = ["ECOG", "SEEG"]
    exclude = df.loc[~df["type"].isin(target_types), "name"].tolist()
    return list(set(exclude))


def get_channel_type_for_ieeg_dataset(tsv_file: str):
    df = pd.read_csv(tsv_file, sep="\t")
    target_types = ["ECOG", "SEEG"]
    kind_map = {"ECOG": FIFF.FIFFV_ECOG_CH, "SEEG": FIFF.FIFFV_SEEG_CH}
    names = df.loc[df["type"].isin(target_types), "name"].tolist()
    type = df.loc[df["type"].isin(target_types), "type"].tolist()
    return {names[i]: kind_map[type[i]] for i in range(len(names))}


RENAME_DICT = {
    "ds001787-1.1.1": {
        "A1": "Fp1",
        "A2": "AF7",
        "A3": "AF3",
        "A4": "F1",
        "A5": "F3",
        "A6": "F5",
        "A7": "F7",
        "A8": "FT7",
        "A9": "FC5",
        "A10": "FC3",
        "A11": "FC1",
        "A12": "C1",
        "A13": "C3",
        "A14": "C5",
        "A15": "T7",
        "A16": "TP7",
        "A17": "CP5",
        "A18": "CP3",
        "A19": "CP1",
        "A20": "P1",
        "A21": "P3",
        "A22": "P5",
        "A23": "P7",
        "A24": "P9",
        "A25": "PO7",
        "A26": "PO3",
        "A27": "O1",
        "A28": "Iz",
        "A29": "Oz",
        "A30": "POz",
        "A31": "Pz",
        "A32": "CPz",
        "B1": "Fpz",
        "B2": "Fp2",
        "B3": "AF8",
        "B4": "AF4",
        "B5": "AFz",
        "B6": "Fz",
        "B7": "F2",
        "B8": "F4",
        "B9": "F6",
        "B10": "F8",
        "B11": "FT8",
        "B12": "FC6",
        "B13": "FC4",
        "B14": "FC2",
        "B15": "FCz",
        "B16": "Cz",
        "B17": "C2",
        "B18": "C4",
        "B19": "C6",
        "B20": "T8",
        "B21": "TP8",
        "B22": "CP6",
        "B23": "CP4",
        "B24": "CP2",
        "B25": "P2",
        "B26": "P4",
        "B27": "P6",
        "B28": "P8",
        "B29": "P10",
        "B30": "PO8",
        "B31": "PO4",
        "B32": "O2",
    },
    "ds002721-1.0.3": {"FP1": "Fp1", "FP2": "Fp2"},
    "ds004022-1.0.0": lambda x: x.replace(" ", ""),
    "ds004256-1.0.5": {
        "1": "Fp1",
        "2": "Fp2",
        "3": "F7",
        "4": "F3",
        "5": "Fz",
        "6": "F4",
        "7": "F8",
        "8": "FC5",
        "9": "FC1",
        "10": "FC2",
        "11": "FC6",
        "12": "T7",
        "13": "C3",
        "14": "Cz",
        "15": "C4",
        "16": "T8",
        "17": "TP9",
        "18": "CP5",
        "19": "CP1",
        "20": "CP2",
        "21": "CP6",
        "22": "TP10",
        "23": "P7",
        "24": "P3",
        "25": "Pz",
        "26": "P4",
        "27": "P8",
        "28": "PO9",
        "29": "O1",
        "30": "Oz",
        "31": "O2",
        "32": "PO10",
        "33": "AF7",
        "34": "AF3",
        "35": "AF4",
        "36": "AF8",
        "37": "F5",
        "38": "F1",
        "39": "F2",
        "40": "F6",
        "41": "FT9",
        "42": "FT7",
        "43": "FC3",
        "44": "FC4",
        "45": "FT8",
        "46": "FT10",
        "47": "C5",
        "48": "C1",
        "49": "C2",
        "50": "C6",
        "51": "TP7",
        "52": "CP3",
        "53": "CPz",
        "54": "CP4",
        "55": "TP8",
        "56": "P5",
        "57": "P1",
        "58": "P2",
        "59": "P6",
        "60": "PO7",
        "61": "PO3",
        "62": "POz",
        "63": "PO4",
        "64": "PO8",
    },
    "ds004460-1.1.0": lambda x: x.split("_")[1][0].lower()
    + str(int(x.split("_")[1][1:])),
    "ds005131-1.0.1": {
        "1": "Fp1",
        "2": "Fp2",
        "3": "F7",
        "4": "F3",
        "5": "Fz",
        "6": "F4",
        "7": "F8",
        "8": "FC5",
        "9": "FC1",
        "10": "FC2",
        "11": "FC6",
        "12": "T7",
        "13": "C3",
        "14": "Cz",
        "15": "C4",
        "16": "T8",
        "17": "TP9",
        "18": "CP5",
        "19": "CP1",
        "20": "CP2",
        "21": "CP6",
        "22": "TP10",
        "23": "P7",
        "24": "P3",
        "25": "Pz",
        "26": "P4",
        "27": "P8",
        "28": "PO9",
        "29": "O1",
        "30": "Oz",
        "31": "O2",
        "32": "PO10",
        "33": "AF7",
        "34": "AF3",
        "35": "AF4",
        "36": "AF8",
        "37": "F5",
        "38": "F1",
        "39": "F2",
        "40": "F6",
        "41": "FT9",
        "42": "FT7",
        "43": "FC3",
        "44": "FC4",
        "45": "FT8",
        "46": "FT10",
        "47": "C5",
        "48": "C1",
        "49": "C2",
        "50": "C6",
        "51": "TP7",
        "52": "CP3",
        "53": "CPz",
        "54": "CP4",
        "55": "TP8",
        "56": "P5",
        "57": "P1",
        "58": "P2",
        "59": "P6",
        "60": "PO7",
        "61": "PO3",
        "62": "POz",
        "63": "PO4",
        "64": "PO8",
    },
    "ds005397-1.0.3": lambda x: x.split("_")[-1],
    "ds005420-1.0.0": lambda x: x.split("-")[0].replace("EEG ", ""),
    "ds005420-1.0.0": {
        "EEG Fp1-A1A2": "Fp1",
        "EEG Fp2-A1A2": "Fp2",
        "EEG Fz-A1A2": "Fz",
        "EEG F3-A1A2": "F3",
        "EEG F4-A1A2": "F4",
        "EEG F7-A1A2": "F7",
        "EEG F8-A1A2": "F8",
        "EEG Cz-A1A2": "Cz",
        "EEG C3-A1A2": "C3",
        "EEG C4-A1A2": "C4",
        "EEG T3-A1A2": "T3",
        "EEG T4-A1A2": "T4",
        "EEG Pz-A1A2": "Pz",
        "EEG P3-A1A2": "P3",
        "EEG P4-A1A2": "P4",
        "EEG T5-A1A2": "T5",
        "EEG T6-A1A2": "T6",
        "EEG O1-A1A2": "O1",
        "EEG O2-A1A2": "O2",
    },
    "ds005415-1.0.0": lambda x: x.split("-")[0],
    "tug_eeg": lambda x: x.replace("EEG ", "").split("-")[0],
}

EXCLUDE_DICT = {
    "Armeni": lambda _=None: ["EEG"],
    "Omega": lambda _=None: ["EEG"],
    "ds000117-1.0.6": lambda _=None: ["Cz2", "Cpz"],
    "ds002778-1.0.5": lambda _=None: ["EXG"],
    "ds003478-1.1.0": lambda _=None: ["CB1", "CB2"],
    "ds004148-1.0.1": lambda _=None: ["Cpz"],
    "ds004186-2.0.0": lambda _=None: ["Cz"],
    "ds004998-1.2.2": lambda _=None: [
        "EEG002",
        "EEG003",
        "EEG004",
        "EEG005",
        "EEG006",
        "EEG007",
        "EEG008",
    ],
    "ds005420-1.0.0": lambda _=None: ["EEG LOC-ROC"],
    "ds005505-1.0.0": lambda _=None: ["Cz"],
    "ds005506-1.0.0": lambda _=None: ["Cz"],
    "ds005507-1.0.0": lambda _=None: ["Cz"],
    "ds005508-1.0.0": lambda _=None: ["Cz"],
    "ds005509-1.0.0": lambda _=None: ["Cz"],
    "ds005510-1.0.0": lambda _=None: ["Cz"],
    "ds005511-1.0.0": lambda _=None: ["Cz"],
    "ds005512-1.0.0": lambda _=None: ["Cz"],
    "ds005697-1.0.2": lambda _=None: ["CB1", "CB2", "Trigger"],
    "ds003555-1.0.1": lambda _=None: ["T1", "T2"],
    "ds003688-1.0.7": lambda x: get_exclude_channel_for_ieeg_dataset(
        x.replace("ieeg.vhdr", "channels.tsv")
    ),
    "ds004473-1.0.2": lambda x: get_exclude_channel_for_ieeg_dataset(
        x.replace("ieeg.edf", "channels.tsv")
    ),
    "ds004993-1.1.2": lambda x: get_exclude_channel_for_ieeg_dataset(
        x.replace("ieeg.edf", "channels.tsv")
    ),
    "ds005415-1.0.0": lambda x: get_exclude_channel_for_ieeg_dataset(
        x.replace("ieeg.edf", "channels.tsv")
    ),
    "ds005574-1.0.2": lambda x: get_exclude_channel_for_ieeg_dataset(
        x.replace("ieeg.edf", "channels.tsv")
    ),
    "ds001787-1.1.1": lambda _=None: ["GSR", "Erg", "Resp", "Plet", "Temp"],
    "ds001971-1.1.1": lambda _=None: ["TIBR", "TIBL", "HIP", "KNEE", "ANKLE"],
    "ds003061-1.1.2": lambda _=None: ["Temp"],
    "ds003490-1.1.0": lambda _=None: ["X", "Y", "Z"],
    "ds003506-1.1.0": lambda _=None: ["X", "Y", "Z"],
    "ds003509-1.1.0": lambda _=None: ["X", "Y", "Z"],
    "ds003602-1.0.1": lambda _=None: ["Startle"],
    "ds003690-1.0.0": lambda _=None: [
        "-Dia-",
        "CB",
    ],  # 注意该数据集提供了subject-level的真实坐标，因为头盔看上去有偏移
    "ds003753-1.1.0": lambda _=None: ["SCR"],
    "ds003822-1.1.0": lambda _=None: ["SCR"],
    "ds003969-1.0.0": lambda _=None: ["GSR", "Erg", "Resp", "Plet", "Temp"],
    "ds004019-1.0.0": lambda _=None: [
        "Respiration Belt",
        "SP-HandArm",
        "E129",
    ],
    "ds004200-1.0.1": lambda _=None: ["LM", "RM", "AFz"],
    "ds004315-1.0.0": lambda _=None: ["AudioOutput"],
    "ds004317-1.0.3": lambda _=None: [
        "Eye",
        "Mastoid",
        "Empty",
        "AudioOutput",
    ],
    "ds004324-1.0.0": lambda _=None: [
        "GSR",
        "x_dir",
        "y_dir",
        "z_dir",
        "MkIdx",
    ],
    "ds004367-1.0.2": lambda _=None: ["F7-0", "F7-1", "GSR"],
    "ds004444-1.0.1": lambda _=None: ["Cz"],
    "ds004446-1.0.1": lambda _=None: ["Cz"],
    "ds004447-1.0.1": lambda _=None: ["Cz"],
    "ds004448-1.0.2": lambda _=None: ["Cz"],
    "ds004477-1.0.2": lambda _=None: ["GSR", "Erg", "Resp", "Plet", "Temp"],
    "ds004515-1.0.0": lambda _=None: [
        "Eye",
        "Mastoid",
        "Empty",
        "AudioOutput",
    ],
    "ds004517-1.0.2": lambda _=None: ["GSR", "Erg", "Resp", "Plet", "Temp"],
    "ds004602-1.0.1": lambda _=None: ["E129"],
    "ds004635-3.1.0": lambda _=None: ["E129"],  # 混了些飘的通道，奇怪的频谱
    "ds004657-1.0.3": lambda _=None: ["GSR"],
    "ds004883-1.0.0": lambda _=None: ["E129"],
    "ds005034-1.0.1": lambda _=None: ["E129"],
    "ds005079-2.0.0": lambda _=None: ["GSR"],
    "ds005121-1.0.2": lambda _=None: ["SW filtered"],
    "ds005516-1.0.1": lambda _=None: ["Cz"],  # 有坏道
}

CUSTOM_TYPE_DICT = {
    "ds003688-1.0.7": lambda x: get_channel_type_for_ieeg_dataset(
        x.replace("ieeg.vhdr", "channels.tsv")
    ),
    "ds004473-1.0.2": lambda x: get_channel_type_for_ieeg_dataset(
        x.replace("ieeg.edf", "channels.tsv")
    ),
    "ds004993-1.1.2": lambda x: get_channel_type_for_ieeg_dataset(
        x.replace("ieeg.edf", "channels.tsv")
    ),
    "ds005415-1.0.0": lambda x: get_channel_type_for_ieeg_dataset(
        x.replace("ieeg.edf", "channels.tsv")
    ),
    "ds005574-1.0.2": lambda x: get_channel_type_for_ieeg_dataset(
        x.replace("ieeg.edf", "channels.tsv")
    ),
}

MONTAGE_DICT = {
    "ds005697-1.0.2": "standard_1020",
    "ds004148-1.0.1": "standard_1020",
    "ds003478-1.1.0": "standard_1020",
    "ds004902-1.0.5": "brainproducts-RNP-BA-128",
    "ds002778-1.0.5": "standard_1020",
    "ds003775-1.2.1": "biosemi64",
    "ds002721-1.0.3": "standard_1020",
    "ds005420-1.0.0": "standard_1020",
    "ds005620-1.0.0": "standard_1020",
    "ds003555-1.0.1": "standard_1020",
    "tug_eeg": "standard_1020",
    "ds001785-1.1.1": "standard_1020",
    "ds001787-1.1.1": "standard_1020",
    "ds001849-1.0.2": "standard_1020",
    "ds002720-1.0.1": "standard_1020",
    "ds003194-1.0.4": "standard_1020",
    "ds003195-1.0.4": "standard_1020",
    "ds003458-1.1.0": "standard_1020",
    "ds003474-1.1.0": "standard_1020",
    "ds003490-1.1.0": "standard_1020",
    "ds003506-1.1.0": "standard_1020",
    "ds003509-1.1.0": "standard_1020",
    "ds003517-1.1.0": "standard_1020",
    "ds003518-1.1.0": "standard_1020",
    "ds003519-1.1.0": "standard_1020",
    "ds003522-1.1.0": "standard_1020",
    "ds003523-1.1.0": "standard_1020",
    "ds003602-1.0.1": "standard_1020",
    "ds003626-2.1.2": "standard_1020",
    "ds003638-1.0.0": "standard_1020",  # 注意该数据集好像有的通道比较飘（功率谱上整体上移）
    "ds003655-1.0.2": "standard_1020",
    "ds003710-1.0.2": "standard_1020",
    "ds003753-1.1.0": "standard_1020",
    "ds003810-2.0.2": "standard_1020",
    "ds003822-1.1.0": "standard_1020",
    "ds003969-1.0.0": "standard_1020",
    "ds003987-1.0.0": "standard_1020",
    "ds004010-1.0.0": "standard_1020",
    "ds004017-1.0.3": "standard_1020",
    "ds004022-1.0.0": "standard_1020",
    "ds004067-1.0.1": "standard_1020",
    "ds004147-1.0.2": "standard_1020",
    "ds004152-1.1.2": "standard_1020",
    "ds004256-1.0.5": "standard_1020",
    "ds004262-1.0.0": "standard_1020",
    "ds004264-1.1.0": "standard_1020",
    "ds004315-1.0.0": "standard_1020",
    "ds004317-1.0.3": "standard_1020",
    "ds004324-1.0.0": "standard_1020",
    "ds004347-1.0.0": "standard_1020",
    "ds004348-1.0.5": "standard_1020",  # 睡眠分期数据集，通道数有点少，还有很多没位置的通道
    "ds004367-1.0.2": "standard_1020",
    "ds004389-1.0.0": "standard_1020",
    "ds004477-1.0.2": "standard_1020",
    "ds004515-1.0.0": "standard_1020",
    "ds004517-1.0.2": "standard_1020",
    "ds004532-1.2.0": "standard_1020",
    "ds004561-1.0.0": "standard_1020",
    "ds004572-1.3.0": "standard_1020",
    "ds004577-1.0.1": "standard_1020",
    "ds004588-1.2.0": "standard_1020",
    "ds004595-1.0.0": "standard_1020",
    "ds004603-1.1.0": "standard_1020",  # 混了些飘的通道
    "ds004626-1.0.2": "standard_1020",
    "ds004802-1.0.0": "standard_1020",
    "ds004840-1.0.1": "standard_1020",  # 通道少，有坏道
    "ds004860-1.0.0": "standard_1020",
    "ds005095-1.0.1": "standard_1020",
    "ds005114-1.0.0": "standard_1020",
    "ds005121-1.0.2": "standard_1020",
    "ds005131-1.0.1": "standard_1020",
    "ds005189-1.0.1": "standard_1020",
    "ds005273-1.0.0": "standard_1020",
    "ds005307-1.0.1": "standard_1020",
    "ds005340-1.0.4": "standard_1020",
    "ds005342-1.0.3": "standard_1020",
    "ds005363-1.0.0": "standard_1020",
    "ds005383-1.0.0": "standard_1020",
    "ds005397-1.0.3": "standard_1020",
    "ds005403-1.0.1": "standard_1020",
    "ds005416-1.0.1": "standard_1020",  # 有坏道
    "ds005594-1.0.3": "standard_1020",
    "ds005672-1.0.0": "standard_1020",
    "ds005779-1.0.1": "standard_1020",
    "ds005815-1.0.1": "standard_1020",
    "ds006036-1.0.5": "standard_1020",
}


CUSTOM_MONTAGE_DICT = {
    "ds001971-1.1.1": lambda x: "/mnt/shared-storage-user/brainllm-share/xiaoqinfan/BrainOmni/share/custom_files/ds001971-1.1.1.tsv",
    "ds003688-1.0.7": lambda x: os.path.join(
        x.rsplit("/", 1)[0],
        [i for i in os.listdir(x.rsplit("/", 1)[0]) if "electrodes.tsv" in i][0],
    ),
    "ds004444-1.0.1": (
        lambda x: "/mnt/shared-storage-user/brainllm-share/xiaoqinfan/BrainOmni/share/custom_files/ds004444-1.0.1.tsv"
    ),
    "ds004446-1.0.1": (
        lambda x: "/mnt/shared-storage-user/brainllm-share/xiaoqinfan/BrainOmni/share/custom_files/ds004444-1.0.1.tsv"
    ),
    "ds004447-1.0.1": (
        lambda x: "/mnt/shared-storage-user/brainllm-share/xiaoqinfan/BrainOmni/share/custom_files/ds004444-1.0.1.tsv"
    ),
    "ds004448-1.0.2": (
        lambda x: "/mnt/shared-storage-user/brainllm-share/xiaoqinfan/BrainOmni/share/custom_files/ds004444-1.0.1.tsv"
    ),
    "ds004460-1.1.0": (
        lambda x: "/mnt/shared-storage-user/brainllm-share/xiaoqinfan/BrainOmni/share/custom_files/ds004460-1.1.0.tsv"
    ),  # 单侧EEG通道？
    "ds004473-1.0.2": lambda x: os.path.join(
        x.rsplit("/", 1)[0],
        [i for i in os.listdir(x.rsplit("/", 1)[0]) if "ACPC_electrodes.tsv" in i][0],
    ),
    "ds004706-1.0.0": (
        lambda x: "/mnt/shared-storage-user/brainllm-share/xiaoqinfan/BrainOmni/share/custom_files/ds004706-1.0.0.tsv"
    ),
    "ds004993-1.1.2": lambda x: os.path.join(
        x.rsplit("/", 1)[0],
        [i for i in os.listdir(x.rsplit("/", 1)[0]) if "electrodes.tsv" in i][0],
    ),
    "ds005415-1.0.0": lambda x: os.path.join(
        x.rsplit("/", 1)[0],
        [i for i in os.listdir(x.rsplit("/", 1)[0]) if "ACPC_electrodes.tsv" in i][0],
    ),
    "ds005574-1.0.2": lambda x: os.path.join(
        x.rsplit("/", 1)[0],
        [i for i in os.listdir(x.rsplit("/", 1)[0]) if "Other_electrodes.tsv" in i][0],
    ),
}

HPI_LIST = [
    "camcan1630",
    "ds000117-1.0.6",
    "ds004330-1.0.0",
]

SENSOR_TYPE_DICT = {"EEG": 0, "MAG": 1, "GRAD": 2, "ECOG": 3, "SEEG": 4}

NOT_USED_DATASET_LIST = [
    "ds003078-1.0.0",  # IEEG_MRI no electrode
    "ds003848-1.0.3",  # IEEG_MRI not ACPC system
    "ds004624-1.2.2",  # IEEG_MRI unknown file tye
    "ds005169-1.0.0",  # IEEG_MRI ScanRAS system
    # "ds005574-1.0.2",  # IEEG_MRI podcast other system
]

_montage = [
    "standard_1005",
    "standard_1020",
    "standard_alphabetic",
    "standard_postfixed",
    "standard_prefixed",
    "standard_primed",
    "biosemi16",
    "biosemi32",
    "biosemi64",
    "biosemi128",
    "biosemi160",
    "biosemi256",
    "easycap-M1",
    "easycap-M10",
    "easycap-M43",
    "EGI_256",
    "GSN-HydroCel-32",
    "GSN-HydroCel-64_1.0",
    "GSN-HydroCel-65_1.0",
    "GSN-HydroCel-128",
    "GSN-HydroCel-129",
    "GSN-HydroCel-256",
    "GSN-HydroCel-257",
    "mgh60",
    "mgh70",
    "artinis-octamon",
    "artinis-brite23",
    "brainproducts-RNP-BA-128",
]


NO_CHANGE_LIST = [
    "ds002218-2.0.0",
    "ds002691-1.1.0",
    "ds003004-1.1.1",  # 部分数据高频异常震荡，头盔形状很奇怪
    "ds003570-1.0.0",  # 注意有boundary标记
    "ds003739-1.0.3",  # 注意提供了具体的头盔形状（虽然长得很奇怪），高频有点吵
    "ds003800-1.0.0",  # 注意到原始的值有点平坦有点小？
    "ds003801-1.0.0",  # 注意有62.5hz的一个工频 TODO
    "ds003825-1.2.0",
    "ds003885-1.0.8",
    "ds003887-1.2.3",
    "ds004000-1.0.0",  # 设备奇奇怪怪
    "ds004015-1.0.2",  # 围绕着耳朵的EEG设备，可能和听觉相关 TODO
    "ds004018-2.0.0",
    "ds004043-1.1.0",
    "ds004151-1.0.0",
    "ds004252-1.0.2",
    "ds004295-1.0.0",
    "ds004357-1.0.1",
    "ds004362-1.0.0",
    "ds004369-1.0.1",  # 似乎只有眼睛附近的eeg数据，不知道是什么任务，挺有意思
    "ds004502-1.0.1",
    "ds004504-1.0.8",
    "ds004574-1.0.0",
    "ds004579-1.0.0",
    "ds004580-1.0.0",
    "ds004582-1.0.0",
    "ds004584-1.0.0",
    "ds004587-1.0.0",
    "ds004660-1.0.2",
    "ds004661-1.1.0",
    "ds004784-1.0.4",  # 蛮不错的，而且有很多别的通道，频谱图也正常，但是不是eeg，不知道是做什么的
    "ds004816-1.0.1",
    "ds004817-1.0.1",
    "ds004841-1.0.1",  # 有坏道
    "ds004842-1.0.0",
    "ds004843-1.0.0",
    "ds004844-1.0.0",
    "ds004849-1.0.0",
    "ds004850-1.0.0",
    "ds004852-1.0.0",
    "ds004853-1.0.0",
    "ds004854-1.0.0",
    "ds004855-1.0.0",
    "ds004942-1.0.0",
    "ds004951-1.0.0",
    "ds004995-1.0.2",  # 有坏道
    "ds005087-1.0.1",
    "ds005089-1.0.1",
    "ds005106-1.5.0",  # 坏道多
    "ds005296-1.0.0",
    "ds005305-1.0.1",
    "ds005406-1.0.0",
    "ds005429-1.0.0",
    "ds005565-1.0.3",
    "ds005586-2.0.0",
    "ds005866-1.0.1",
    "ds005868-1.0.1",
    "ds005907-1.0.0",
    "ds005960-1.0.0",
    "ds006018-1.2.1",
]

BAD_DATA_LIST = [
    "ds002034-1.0.3",  # 很脏
    "ds002893-2.0.0",  # h5py读取
    "ds003343-2.0.1",  # 读不了
    "ds003380-1.0.0",  # 脏且通道不标准
    "ds003420-1.0.2",  # 看起来有点脏，而且给的electrode和raw里面的ch name对不上
    "ds003421-1.0.2",  # 同上
    "ds003516-1.1.3",  # epoch数据
    "ds003670-1.1.0",  # 工频干扰极多，数据脏
    "ds003702-1.0.2",  # vhdr 找不到对应的 vmrk 文件，尽管好像有
    "ds003751-1.0.6",  # 非常脏的数据
    "ds003774-1.0.2",  # no file founded
    "ds003805-1.0.0",  # epoch 数据
    "ds003838-1.0.6",  # h5py
    "ds003944-1.0.1",  # markerfile读取报错
    "ds003947-1.0.1",  # 同上
    "ds004033-1.0.0",  # h5py
    "ds004040-1.0.0",  # 数据脏
    "ds004075-1.0.0",  # 读取不到vmrk文件
    "ds004078-1.2.1",  # no file founded
    "ds004105-1.0.0",  # no file founded
    "ds004117-1.0.1",  # h5py
    "ds004118-1.0.1",  # no file founded
    "ds004119-1.0.1",  # no file founded
    "ds004120-1.0.0",  # no file founded
    "ds004121-1.0.0",  # no file founded
    "ds004122-1.0.0",  # no file founded
    "ds004123-1.0.0",  # no file founded
    "ds004166-1.0.0",  # 数据读不出来
    "ds004279-1.1.2",  # 奇怪的频谱拱形sin
    "ds004284-1.0.0",  # 没有pos
    "ds004306-1.0.2",  # 找不到fdt数据
    "ds004350-2.0.0",  # 找不到fdt数据
    "ds004356-2.2.1",  # 10000hz，诡异
    "ds004368-1.0.2",  # 分段读不了
    "ds004381-1.0.2",  # 诡异差分
    "ds004388-1.0.0",  # 好脏'
    "ds004408-1.0.8",  # 没有位置
    "ds004511-1.0.2",  # 没有位置
    "ds004519-1.0.1",  # epoch
    "ds004520-1.0.1",  # epoch
    "ds004521-1.0.1",  # epoch
    "ds004554-1.0.4",  # epoch
    "ds004563-1.0.1",  # no loc
    "ds004598-1.0.0",  # no loc
    "ds004621-1.0.3",  # no loc
    "ds004625-1.0.2",  # 读不了
    "ds004745-1.0.1",  # no loc
    "ds004771-1.0.0",  # epoch
    "ds004785-1.0.1",  # epoch
    "ds004952-1.2.2",  # no vmrk
    "ds004980-1.0.0",  # no loc
    "ds005021-1.2.1",  # no file founded
    "ds005028-1.0.0",  # too short(1.00s)
    "ds005048-1.0.1",  # h5py
    "ds005170-1.1.2",  # no loc
    "ds005178-1.0.0",  # no file foundd
    "ds005185-1.0.2",  # no loc
    "ds005207-1.0.0",  # no file founded
    "ds005262-1.0.1",  # 录的什么东西？？？
    "ds005274-1.0.0",  # no vmrk
    "ds005343-1.0.0",  # 频谱很脏
    "ds005486-1.0.1",  # 数据脏
    "ds005520-1.0.1",  # no vmrk
    "ds005555-1.1.0",  # 两个通道，还没loc
    "ds005648-1.0.0",  # no loc
    "ds005688-1.0.1",  # 太少
    "ds005692-1.0.0",  # no loc
    "ds005863-2.0.0",  # no vmrk
    "ds005946-1.0.1",  # epoch
    "ds006095-1.0.0",  # 读不了
    "ds006104-1.0.1",  # 脏的懒得喷
    "ds006126-1.0.0",  # 太少，名字怪
    "ds006171-1.0.0",  # 脏，名字怪
]
