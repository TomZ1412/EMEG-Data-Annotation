import os
import json
import logging
import argparse
import torch
import random
import numpy as np
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
    args = parser.parse_args()
    return args

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
