import os
import json
import logging
import argparse
import torch
import random
import numpy as np
from collections import defaultdict
# from factory.utils import (
#     process,
#     split_pretrain_metadata,
# )
from utils import (
    process,
    split_pretrain_metadata,
)
from concurrent.futures import ProcessPoolExecutor, as_completed
from accessor import DataAccessor
from constant import SEED, LOW, HIGH, SAMPLE_RATE, RAW_PATH, PRETRAIN_METADATA_PATH,PROCESSED_PRETRAIN_PATH

def seed_everything(seed):
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_logger():
    logger = logging.getLogger(name="processor")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(name)s] [%(asctime)s.%(msecs)03d] [%(levelname)s] %(message)s",
        "%H:%M:%S",
    )

    screenHandler = logging.StreamHandler()
    screenHandler.setLevel(logging.INFO)
    screenHandler.setFormatter(formatter)
    logger.addHandler(screenHandler)

    return logger


def parse_arg():
    parser = argparse.ArgumentParser("")
    parser.add_argument("--time", type=int, default=30, help="the length of each segment")
    parser.add_argument("--stride", type=int, default=30, help="stride when segmenting")
    parser.add_argument("--max_workers", type=int, default=64)
    parser.add_argument("--selection-config", default=None, help="JSON file with per-dataset selection rules.")
    parser.add_argument("--max-files", type=int, default=None, help="Global maximum number of files after selection.")
    args = parser.parse_args()
    return args


def normalize_filter(values):
    if values is None:
        return None
    if isinstance(values, str):
        values = [item.strip() for item in values.split(",")]
    normalized = {str(item).strip() for item in values if str(item).strip()}
    return normalized or None


def path_parts(record):
    dataset = record.get("dataset", "")
    path = record.get("path", "")
    if f"/{dataset}/" in path:
        relative = path.split(f"/{dataset}/", 1)[1]
    else:
        relative = path
    return [part for part in relative.replace("\\", "/").split("/") if part]


def get_subject(record, subject_level=None):
    parts = path_parts(record)
    if subject_level is not None:
        index = int(subject_level)
        if -len(parts) <= index < len(parts):
            return parts[index]

    dataset = record.get("dataset")
    if dataset == "tug_eeg" and "edf" in parts:
        edf_index = parts.index("edf")
        if edf_index + 1 < len(parts):
            return parts[edf_index + 1]

    for part in parts:
        if part.startswith("sub-"):
            return part
    return "__unknown_subject__"


def get_session(record):
    for part in path_parts(record):
        if part.startswith("ses-"):
            return part
    return None


def record_allowed_by_rule(record, rule):
    subject = get_subject(record, rule.get("subject_level"))
    session = get_session(record)
    subjects = normalize_filter(rule.get("subjects"))
    exclude_subjects = normalize_filter(rule.get("exclude_subjects"))
    sessions = normalize_filter(rule.get("sessions") or rule.get("include_sessions"))
    exclude_sessions = normalize_filter(rule.get("exclude_sessions"))

    if subjects and subject not in subjects:
        return False
    if exclude_subjects and subject in exclude_subjects:
        return False
    if sessions and session not in sessions:
        return False
    if exclude_sessions and session in exclude_sessions:
        return False
    return True


def select_records_for_dataset(records, rule):
    max_subjects = rule.get("max_subjects")
    max_files = rule.get("max_files")
    max_files_per_subject = rule.get("max_files_per_subject")
    subject_order = []
    records_by_subject = defaultdict(list)

    for record in sorted(records, key=lambda item: item["path"]):
        if not record_allowed_by_rule(record, rule):
            continue

        subject = get_subject(record, rule.get("subject_level"))
        if subject not in records_by_subject:
            subject_order.append(subject)
        records_by_subject[subject].append(record)

    if max_subjects is not None:
        subject_order = subject_order[: int(max_subjects)]

    per_subject_limit = int(max_files_per_subject) if max_files_per_subject is not None else None
    subject_queues = {
        subject: records_by_subject[subject][:per_subject_limit]
        for subject in subject_order
    }

    selected = []
    cursor = 0
    while subject_queues:
        subject = subject_order[cursor % len(subject_order)]
        queue = subject_queues.get(subject, [])
        if queue:
            selected.append(queue.pop(0))
            if max_files is not None and len(selected) >= int(max_files):
                break
        if not queue:
            subject_queues.pop(subject, None)
            subject_order = [item for item in subject_order if item in subject_queues]
            cursor = 0
        elif subject_order:
            cursor += 1

    return selected


def apply_selection_config(brain_files, config_path, logger):
    if not config_path:
        return brain_files

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    dataset_rules = config.get("datasets", {})
    if not isinstance(dataset_rules, dict) or not dataset_rules:
        raise ValueError("selection config must contain a non-empty 'datasets' object")

    records_by_dataset = defaultdict(list)
    for record in brain_files:
        records_by_dataset[record.get("dataset")].append(record)

    selected = []
    for dataset, rule in dataset_rules.items():
        dataset_records = records_by_dataset.get(dataset, [])
        dataset_selected = select_records_for_dataset(dataset_records, rule or {})
        logger.info(f"selection {dataset}: {len(dataset_selected)} / {len(dataset_records)} files")
        selected.extend(dataset_selected)

    if config.get("max_files") is not None:
        selected = selected[: int(config["max_files"])]

    return selected

import json
ROOT = '/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/pretrain/EEG/'
dataset_map = {
    'ds003478-1.1.0': '.set',
    'ds004796-1.0.9': None,
    'ds005505-1.0.0': '.set',
    'ds005506-1.0.0': '.set',
    'ds005507-1.0.0': '.set',
    'ds005508-1.0.0': '.set',
    'ds005509-1.0.0': '.set',
    'ds005510-1.0.0': '.set',
    'ds005511-1.0.0': '.set',
    'ds005512-1.0.0': '.set',
    'ds005620-1.0.0': '.vhdr',
    'ds005697-1.0.2': '.set'
}
import csv

def load_brainfiles_from_json(json_path):
    with open(json_path,'r') as f:
        data = json.load(f) 
    result = []
    all_dataset = set()
    
    # 用于统计每个dataset的坏道个数
    dataset_bad_channels = {}
    
    # 用于存储要写入jsonl的数据
    jsonl_records = []
    
    # skip = ["ds005697-1.0.2","ds003478-1.1.0", "ds004796-1.0.9", "tug_eeg"]
    skip = ["tug_eeg", "ds004796-1.0.9"]
    for path, bad_channels_list in data.items():
        dataset = path.split('/')[0]  # 获取第一个 '/' 前的部分
        if dataset in skip :
            continue
        bad_count = len(bad_channels_list) if bad_channels_list else 0  # 获取坏道个数（列表的第一个元素）
        if bad_count <= 10:
            continue
        # 处理路径
        if dataset == 'tug_eeg':
            path = '/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/not_used/' + path + dataset_map[dataset]
            # path = '/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/not_used/' + path
        else:
            path = ROOT + path + dataset_map[dataset]
        
        result.append({'path': path, 'dataset': dataset, 'bad_channels': bad_count})
        all_dataset.add(dataset)
        
        # 统计每个dataset的坏道个数
        if dataset not in dataset_bad_channels:
            dataset_bad_channels[dataset] = []
        dataset_bad_channels[dataset].append(bad_count)
        
        # 准备jsonl记录
        # 将坏道列表转换为数字索引格式（假设bad_channels_list已经是数字列表）
        # 如果bad_channels_list是通道名字符串列表，需要先转换为数字索引
        if bad_channels_list and isinstance(bad_channels_list[0], str):
            # 如果坏道是通道名，需要转换为数字索引
            # 这里假设有一个函数或映射来转换，如果没有，保持原样或根据需求调整
            subblock_bad_channels = {"0": list(range(len(bad_channels_list)))}  # 示例：使用索引作为数字
        else:
            # 如果已经是数字列表，直接使用
            subblock_bad_channels = {"0": bad_channels_list if bad_channels_list else []}
        
        jsonl_record = {
            "file_path": path,
            "subblock_bad_channels": subblock_bad_channels,
            "discarded": False,
            "user": "BBB"
        }
        jsonl_records.append(jsonl_record)
    # 写入jsonl文件
    jsonl_output_path = "./brainfiles_metadata.jsonl"  # 可以修改为需要的路径
    with open(jsonl_output_path, 'w') as jsonl_file:
        for record in jsonl_records:
            jsonl_file.write(json.dumps(record) + '\n')
    
    # 计算每个dataset的最大和平均坏道个数
    dataset_stats = {}
    for dataset, bad_list in dataset_bad_channels.items():
        dataset_stats[dataset] = {
            'max': max(bad_list),
            'mean': sum(bad_list) / len(bad_list),
            'count': len(bad_list),
            'all_bad_channels': bad_list
        }
    # 写入CSV文件 - 每个dataset的统计信息
    # stats_csv_path = './dataset_statistics.csv'
    # with open(stats_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
    #     fieldnames = ['dataset', 'file_count', 'max_bad_channels', 'mean_bad_channels']
    #     writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    #     writer.writeheader()
    #     for dataset, stats in dataset_stats.items():
    #         writer.writerow({
    #             'dataset': dataset,
    #             'file_count': stats['count'],
    #             'max_bad_channels': stats['max'],
    #             'mean_bad_channels': f"{stats['mean']:.2f}"
    #         })
    # print(f"统计信息已保存到: {stats_csv_path}")
    
    # import pdb;pdb.set_trace()
    # print(result)
    
    # return result, dataset_stats
    return result


if __name__ == "__main__":
    args = parse_arg()
    TIME = args.time
    STRIDE = args.stride
    max_workers = args.max_workers
    logger = get_logger()
    logger.info("initializing accessor...")
    accessor = DataAccessor(read_only=False)

    # pretrain data part
    processed_pretrain_path = os.path.join(
        PROCESSED_PRETRAIN_PATH,
        f"sfreq_{SAMPLE_RATE}_low_{LOW}_high_{HIGH}_time_{TIME}_stride_{STRIDE}",
    )

    pretrain_metadata_path = os.path.join(
        PRETRAIN_METADATA_PATH,
        f"sfreq_{SAMPLE_RATE}_low_{LOW}_high_{HIGH}_time_{TIME}_stride_{STRIDE}",
    )
    
    os.makedirs(
        processed_pretrain_path,
        exist_ok=True,
    )

    os.makedirs(
        pretrain_metadata_path,
        exist_ok=True,
    )

    finish_path = os.path.join(pretrain_metadata_path, "finish.json")
    info_path = os.path.join(pretrain_metadata_path, "info.json")
    
    logger.info(f"Output path: {processed_pretrain_path}")
    logger.info(f"MetaData path: {pretrain_metadata_path}")

    logger.info("searching_brain_files...")
    brain_files = accessor.search_brain_files(root_path=RAW_PATH)
    brain_files = [file for file in brain_files if file['dataset']!='processed']
    brain_files = apply_selection_config(brain_files, args.selection_config, logger)
    if args.max_files is not None:
        brain_files = brain_files[: args.max_files]
    # import pdb;pdb.set_trace()
    # _brain_files = [file for file in brain_files if file['dataset'][4:8] in ['5505','5506','5507','5508','5509','5510','5511','5512']]
    # brain_files = _brain_files
    # brain_files = load_brainfiles_from_json('./detected_bad_channels.json')
    # brain_files = [{'path':'/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/not_used/tug_eeg/edf/125/aaaaasmu/s001_2015/01_tcp_ar/aaaaasmu_s001_t000.edf',
    #                'dataset':'tug_eeg'}]
    logger.info("loading archives...")
    if os.path.exists(finish_path):
        with open(finish_path, "r") as f:
            finish = json.load(f)
    else:
        finish = []

    if os.path.exists(info_path):
        with open(info_path, "r") as f:
            metadata_list = json.load(f)
    else:
        metadata_list = []

    logger.info("filtering brain files...")
    brain_files = [i for i in brain_files if i["path"] not in finish]
    logger.info(f"process {len(brain_files)} sample")
    # import pdb;pdb.set_trace()
    logger.info("start processing...")
    counter = 0
    # for i in brain_files:
    #     process(accessor,
    #             i["path"],
    #             i["dataset"],
    #             processed_pretrain_path,
    #             TIME,
    #             STRIDE,
    #             )
    # process(accessor,
    #     brain_files[0]["path"],
    #     brain_files[0]["dataset"],
    #     processed_pretrain_path,
    #     TIME,
    #     STRIDE,
    #     )
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i in brain_files:
            futures.append(
                executor.submit(
                    process,
                    accessor,
                    i["path"],
                    i["dataset"],
                    processed_pretrain_path,
                    TIME,
                    STRIDE,
                )
            )
        for future in as_completed(futures):
            try:
                segments_metadata, finished_path = future.result()
                metadata_list += segments_metadata
                finish.append(finished_path)
                counter += 1
                if counter % 1000 == 0:
                    with open(finish_path, "w") as f:
                        json.dump(finish, f)
                    with open(info_path, "w") as f:
                        json.dump(metadata_list, f)

            except Exception as e:
                logger.info(f"An error occurred: {e}")

    logger.info("finish processing ...")
    metadata_list = sorted(metadata_list, key=lambda x: x["path"])
    with open(finish_path, "w") as f:
        json.dump(finish, f)
    with open(info_path, "w") as f:
        json.dump(metadata_list, f)

    seed_everything(seed=SEED)
    # train, val, test, new_device_dataset_dict = split_pretrain_metadata(metadata_list)
    # with open(os.path.join(pretrain_metadata_path, "train.json"), "w") as f:
    #     json.dump(train, f, indent=4)
    # with open(os.path.join(pretrain_metadata_path, "val.json"), "w") as f:
    #     json.dump(val, f, indent=4)
    # with open(os.path.join(pretrain_metadata_path, "test.json"), "w") as f:
    #     json.dump(test, f, indent=4)
    # for dataset in new_device_dataset_dict.keys():
    #     with open(os.path.join(pretrain_metadata_path, f"{dataset}.json"), "w") as f:
    #         json.dump(new_device_dataset_dict[dataset], f, indent=4)
    logger.info("All processing completed successfully!")
