from pathlib import Path

RAW_DATA_ROOT = Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/pretrain/check_processed")           # 原始数据
VIS_DATA_ROOT = Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/pretrain/check_processed/sfreq_256_low_0.1_high_96_time_30_stride_30")
# RAW_DATA_ROOT = Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/not_used/tug_eeg/edf") 
# VIS_DATA_ROOT = Path("/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/not_used/processed/sfreq_256_low_0.1_high_96_time_30_stride_30/edf")
# ANNOTATION_FILE = Path("/mnt/petrelfs/xiaoqinfan/ZZH/data_annotation_result/annotations.jsonl")  # 标注结果
# ANNOTATION_FILE = Path("/mnt/petrelfs/xiaoqinfan/ZZH/data_annotation_result/annotations_notused.jsonl")  # 标注结果
# ANNOTATION_FILE = Path("/mnt/petrelfs/xiaoqinfan/ZZH/data_annotation_result/annotations_tug_test.jsonl")
ANNOTATION_FILE = Path("/mnt/petrelfs/xiaoqinfan/ZZH/code/backend/process_data/brainfiles_metadata.jsonl") 
# ANNOTATION_FILE = Path("/mnt/petrelfs/xiaoqinfan/ZZH/data_annotation_result/test.jsonl")  # 标注结果
CHECK_DATA_ROOT = Path("/mnt/petrelfs/xiaoqinfan/ZZH/visual")
DROPPED_DATASET_PATH = Path("/mnt/petrelfs/xiaoqinfan/ZZH/data_annotation_result/dropped_dataset.json")
CACHE_TREE_PATH = Path("/mnt/petrelfs/xiaoqinfan/ZZH/code/backend/app_check/file_tree_cache")
# CACHE_TREE_PATH = Path("/mnt/petrelfs/xiaoqinfan/ZZH/code/backend/app/notused_file_tree_cache")
# CACHE_TREE_PATH = Path("/mnt/petrelfs/xiaoqinfan/ZZH/code/backend/app/test_file_tree_cache")