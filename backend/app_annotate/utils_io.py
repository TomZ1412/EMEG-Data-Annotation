import json
from pathlib import Path
from fastapi.responses import FileResponse
from config import RAW_DATA_ROOT, VIS_DATA_ROOT
import pickle
import hashlib

def write_annotation(annotation_file: Path, record: dict, discard_threshold: int = 10):
    """
    将标注记录写入 JSONL 文件。
    每行一个数据文件的标注记录，支持子图独立标注格式。
    
    Args:
        annotation_file: 标注文件路径
        record: 标注记录
        discard_threshold: 单个子图的坏道数量阈值，超过此阈值则标记为丢弃
    """
    # 提取必要字段
    keep_keys = ['file_path', 'bad_channels', 'subblock_bad_channels', 'discarded', 'user']
    filtered_record = {k: v for k, v in record.items() if k in keep_keys}
    
    # 处理坏道数据格式
    if 'subblock_bad_channels' in filtered_record:
        # 使用新的子图坏道格式
        subblock_bad_channels = filtered_record['subblock_bad_channels']
    else:
        # 兼容旧格式：将单个坏道列表转换为子图格式
        subblock_bad_channels = {0: filtered_record.get('bad_channels', [])}
    
    # 自动判断是否弃用：如果任何一个子图的坏道数量 >= discard_threshold 则弃用
    # discarded = any(len(channels) >= discard_threshold for channels in subblock_bad_channels.values())
    discarded = False
    
    path_key = filtered_record.get("file_path")
    
    if path_key is None:
        raise ValueError("record 中缺少必要字段 'file_path'")
    
    # 构建新的标注记录
    new_annotation = {
        "file_path": path_key,
        "subblock_bad_channels": subblock_bad_channels,
        "discarded": discarded,
        "user": filtered_record.get('user', '')
        # "update_time": datetime.now().isoformat()
    }
    
    # 读取现有的所有标注记录
    existing_annotations = {}
    if annotation_file.exists():
        try:
            with annotation_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record_data = json.loads(line)
                        if 'file_path' in record_data:
                            existing_annotations[record_data['file_path']] = record_data
        except (json.JSONDecodeError, Exception) as e:
            print(f"读取标注文件失败，将创建新文件: {e}")
    
    # 更新或添加标注记录
    existing_annotations[path_key] = new_annotation
    
    # 写入 JSONL 格式
    with annotation_file.open("w", encoding="utf-8") as f:
        for annotation in existing_annotations.values():
            f.write(json.dumps(annotation, ensure_ascii=False) + '\n')
    
    # 输出更详细的日志信息
    max_bad_in_subblock = max(len(channels) for channels in subblock_bad_channels.values()) if subblock_bad_channels else 0
    print(f"标注已保存: {path_key}, 子图数量: {len(subblock_bad_channels)}, 最大坏道数(单个子图): {max_bad_in_subblock}, 是否丢弃: {discarded}")
    
def load_annotation(annotation_file: Path, file_path: str = None):
    """
    从 JSONL 文件读取标注记录。
    如果指定 file_path，则返回该文件的标注；否则返回所有标注。
    """
    annotations = {}
    
    if not annotation_file.exists():
        return annotations if file_path is None else {}
    
    try:
        with annotation_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    record_data = json.loads(line)
                    if 'file_path' in record_data:
                        annotations[record_data['file_path']] = record_data
    except (json.JSONDecodeError, Exception) as e:
        print(f"读取标注文件失败: {e}")
    
    if file_path is None:
        return annotations
    else:
        return annotations.get(file_path, {})

def get_annotation_for_file(annotation_file: Path, file_path: str):
    """
    获取指定文件的标注信息，兼容新旧格式。
    """
    annotation_data = load_annotation(annotation_file, file_path)
    
    if not annotation_data:
        return {
            "bad_channels": [],
            "subblock_bad_channels": {},
            "discarded": False
        }
    
    # 处理格式兼容
    if 'subblock_bad_channels' in annotation_data:
        # 新格式
        subblock_bad_channels = annotation_data['subblock_bad_channels']
        # 为了兼容前端，也提供平铺的坏道列表（第一个子图的）
        bad_channels = list(subblock_bad_channels.values())[0] if subblock_bad_channels else []
    else:
        # 旧格式转换
        bad_channels = annotation_data.get('bad_channels', [])
        subblock_bad_channels = {0: bad_channels}
    
    return {
        "bad_channels": bad_channels,
        "subblock_bad_channels": subblock_bad_channels,
        "discarded": annotation_data.get('discarded', False)
    }

def get_cache_key(root: Path) -> str:
    """生成缓存键，基于路径和文件夹修改时间"""
    path_str = str(root)
    # 添加文件夹修改时间以确保缓存及时更新
    mtime = root.stat().st_mtime if root.exists() else 0
    key_data = f"{path_str}_{mtime}"
    return hashlib.md5(key_data.encode()).hexdigest()

# def list_files_recursive(root: Path, cache_dir: Path = None, use_cache: bool = True, is_root_call: bool = True):
#     """
#     返回文件夹结构用于前端显示文件树
#     支持磁盘缓存以提高性能
    
#     Args:
#         root: 要遍历的根目录
#         cache_dir: 缓存目录，如果为None则使用默认位置
#         use_cache: 是否使用缓存
#         is_root_call: 是否是根目录调用（用于控制缓存）
#     """
#     suffix_list = ['con', 'edf', 'fif', 'dat','ds','set', 'bdf', 'eeg']
#     # import pdb;pdb.set_trace()
#     # 设置缓存目录 - 只在根目录调用时创建
#     if cache_dir is None:
#         cache_dir = Path.home() / ".file_tree_cache"
#     if is_root_call:
#         cache_dir.mkdir(exist_ok=True)
    
#     # 只在根目录调用时使用缓存
#     if is_root_call:
#         cache_file = cache_dir / "tree.pkl"
        
#         # 如果使用缓存且缓存存在，直接加载
#         if use_cache and cache_file.exists():
#             try:
#                 with open(cache_file, 'rb') as f:
#                     print(f"Loading file tree from cache: {cache_file}")
#                     return pickle.load(f)
#             except (pickle.PickleError, EOFError, FileNotFoundError) as e:
#                 print(f"Cache load failed, regenerating: {e}")
    
#     # 正常遍历逻辑
#     tree = []
#     folders = []
    
#     if root == RAW_DATA_ROOT:
#         keep_folder_names = [p.name for p in VIS_DATA_ROOT.iterdir() if p.is_dir()]
    
#         # 处理前10个符合条件的文件夹（完整递归）
#         folders = [p for p in sorted(root.iterdir()) 
#                    if (p.is_dir() and 
#                        not p.name.endswith('.ds') and 
#                        p.name in keep_folder_names)][2:4]
#     else:
#         # 处理前5个符合条件的文件夹（完整递归）
#         folders = [p for p in sorted(root.iterdir()) 
#                    if p.is_dir() and not p.name.endswith('.ds')]
    
#     for folder in folders:
#         if 'code' in folder.name or 'stimuli' in folder.name or 'derivatives' in folder.name:
#             continue
#         # 递归调用时传递 is_root_call=False
#         tree.append({
#             "name": folder.name,
#             "type": "dir",
#             "children": list_files_recursive(folder, cache_dir, use_cache, is_root_call=False)
#         })
    
#     # 处理所有符合条件的文件
#     for file in sorted(root.iterdir()):
#         if file.is_file() and file.name.split('.')[-1] in suffix_list:
#             tree.append({
#                 "name": file.name,
#                 "type": "file",
#                 "path": str(file)
#             })
    
#     # 只在根目录调用时保存缓存
#     if is_root_call:
#         try:
#             with open(cache_file, 'wb') as f:
#                 pickle.dump(tree, f)
#             print(f"File tree cached to: {cache_file}")
#         except Exception as e:
#             print(f"Failed to save cache: {e}")
    
#     return tree


def list_files_recursive(root: Path, 
                         cache_dir: Path = None, 
                         use_cache: bool = True, 
                         is_root_call: bool = True,
                         range_start: int = 120, 
                         range_end: int = 150):
    suffix_list = ['con', 'edf', 'fif', 'dat', 'ds', 'set', 'bdf', 'vhdr']
    if cache_dir is None:
        cache_dir = Path.home() / ".file_tree_cache"
    
    if is_root_call:
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / "tree.pkl"
        # cache_file = cache_dir / "full_tree.pkl"
        
        if use_cache and cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    full_tree = pickle.load(f)
                    print(f"Loading from cache and filtering range {range_start}-{range_end}...")
                    
                    # # --- 关键过滤逻辑：在读取缓存后立即过滤 ---
                    # filtered_tree = []
                    # for item in full_tree:
                    #     # 如果是文件夹且名字是数字
                    #     if item["type"] == "dir":
                    #         try:
                    #             folder_num = int(item["name"])
                    #             # 判断文件夹名是否在区间内
                    #             if range_start <= folder_num <= range_end:
                    #                 filtered_tree.append(item)
                    #         except ValueError:
                    #             # 如果文件夹名不是纯数字，则跳过或根据需求保留
                    #             continue
                    #     else:
                    #         # 根目录下的文件通常直接保留，或者也根据需求过滤
                    #         filtered_tree.append(item)
                    
                    filtered_tree = full_tree       
                    return filtered_tree
            except Exception as e:
                print(f"Cache access failed: {e}")

    # --- 如果没有缓存，执行正常的递归遍历 ---
    tree = []
    
    # 获取当前目录下所有项
    try:
        items = sorted(root.iterdir())
    except PermissionError:
        return []
    skip = ['ds004381-1.0.2','ds004408-1.0.8','ds005262-1.0.1']
    for item in items:
        # 跳过特定关键词
        if any(k in item.name for k in ['code', 'stimuli', 'derivatives']):
            continue
            
        if item.is_dir():
            # 跳过 .ds
            if item.name.endswith('.ds') or item.name in skip:
                continue
            
            # 如果是根目录调用，根据数字区间过滤
            # if is_root_call:
            #     try:
            #         folder_num = int(item.name)
            #         if not (range_start <= folder_num <= range_end):
            #             continue
            #     except ValueError:
            #         # 如果不是数字名的文件夹，在根目录下不进入
            #         continue

            # 递归
            tree.append({
                "name": item.name,
                "type": "dir",
                "children": list_files_recursive(item, cache_dir, use_cache, is_root_call=False)
            })
            
        elif item.is_file():
            if item.suffix.lower().lstrip('.') in suffix_list:
                tree.append({
                    "name": item.name,
                    "type": "file",
                    "path": str(item)
                })

    # 只有当这是真正的全量扫描（非区间限制）时才建议保存为 tree.pkl
    # 或者你可以保存为 range 专属缓存
    if is_root_call:
        try:
            with open(cache_file, 'wb') as f:
                # 注意：这里保存的是过滤后的树，建议根据需求决定是否保存全量
                pickle.dump(tree, f)
        except Exception as e:
            print(f"Save cache failed: {e}")

    return tree

def clear_file_tree_cache(cache_dir: Path = None):
    """清空文件树缓存"""
    if cache_dir is None:
        cache_dir = Path.home() / ".file_tree_cache"
    
    if cache_dir.exists():
        for cache_file in cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
                print(f"Removed cache: {cache_file}")
            except Exception as e:
                print(f"Failed to remove cache {cache_file}: {e}")
        print("File tree cache cleared")
    else:
        print("Cache directory does not exist")

def update_file_tree_cache(root: Path, cache_dir: Path = None):
    """强制更新指定路径的缓存"""
    return list_files_recursive(root, cache_dir, use_cache=False)

# def list_files_recursive(root: Path):
#     suffix_list = ['con', 'edf', 'fif', 'dat','ds','set', 'bdf']
#     """返回文件夹结构用于前端显示文件树"""
#     tree = []
#     folders=[]
#     if root == RAW_DATA_ROOT:
#         keep_folder_names = [p.name for p in VIS_DATA_ROOT.iterdir() if p.is_dir()]
    
#         # 处理前10个符合条件的文件夹（完整递归）
#         folders = [p for p in sorted(root.iterdir()) 
#                    if (p.is_dir() and 
#                        not p.name.endswith('.ds') and 
#                        # 新增条件：文件夹名称必须在 VIS_DATA_ROOT 的直接子目录名称中
#                        p.name in keep_folder_names)][:20]
#     else:
#         # 处理前5个符合条件的文件夹（完整递归）
#         folders = [p for p in sorted(root.iterdir()) 
#                    if p.is_dir() and not p.name.endswith('.ds')]
#     # print(folders)
#     for folder in folders:
#         if 'code' in folder.name or 'stimuli' in folder.name or 'derivatives' in folder.name:
#             continue
#         tree.append({
#             "name": folder.name,
#             "type": "dir",
#             "children": list_files_recursive(folder)
#         })
    
#     # 处理所有符合条件的文件
#     for file in sorted(root.iterdir()):
#         if file.is_file() and file.name.split('.')[-1] in suffix_list:
#             tree.append({
#                 "name": file.name,
#                 "type": "file",
#                 "path": str(file)
#             })
    
#     return tree


import re

channels_to_keep = [
    # 标准10-20系统电极（19个）
    "EEG FP1-LE",
    "EEG FP2-LE", 
    "EEG F3-LE",
    "EEG F4-LE",
    "EEG C3-LE",
    "EEG C4-LE",
    "EEG P3-LE",
    "EEG P4-LE",
    "EEG O1-LE",
    "EEG O2-LE",
    "EEG F7-LE",
    "EEG F8-LE",
    "EEG T3-LE",  # 颞叶中部
    "EEG T4-LE",  # 颞叶中部
    "EEG T5-LE",  # 颞叶后部
    "EEG T6-LE",  # 颞叶后部
    "EEG FZ-LE",  # 额中线
    "EEG CZ-LE",  # 中央中线
    "EEG T1-LE",
    "EEG T2-LE",
    "EEG A1-LE",
    "EEG A2-LE", 
    
    
    "EEG FP1-REF",
    "EEG FP2-REF", 
    "EEG F3-REF",
    "EEG F4-REF",
    "EEG C3-REF",
    "EEG C4-REF",
    "EEG P3-REF",
    "EEG P4-REF",
    "EEG O1-REF",
    "EEG O2-REF",
    "EEG F7-REF",
    "EEG F8-REF",
    "EEG T3-REF",  # 颞叶中部
    "EEG T4-REF",  # 颞叶中部
    "EEG T5-REF",  # 颞叶后部
    "EEG T6-REF",  # 颞叶后部
    "EEG FZ-REF",  # 额中线
    "EEG CZ-REF",  # 中央中线
    "EEG T1-REF",
    "EEG T2-REF", 
    "EEG A1-REF",
    "EEG A2-REF",
]

# channels_to_keep = [
#     # 标准10-20系统电极（19个）
#     "EEG FP1-LE",
#     "EEG FP2-LE", 
#     "EEG F3-LE",
#     "EEG F4-LE",
#     "EEG C3-LE",
#     "EEG C4-LE",
#     "EEG P3-LE",
#     "EEG P4-LE",
#     "EEG O1-LE",
#     "EEG O2-LE",
#     "EEG F7-LE",
#     "EEG F8-LE",
#     "EEG T3-LE",  # 颞叶中部
#     "EEG T4-LE",  # 颞叶中部
#     "EEG T5-LE",  # 颞叶后部
#     "EEG T6-LE",  # 颞叶后部
#     "EEG FZ-LE",  # 额中线
#     "EEG CZ-LE",  # 中央中线
#     "EEG PZ-LE",  # 顶中线
#     "EEG OZ-LE",  # 枕中线
    
#     # 附加EEG电极
#     "EEG T1-LE",  # 颞叶前部补充
#     "EEG T2-LE",  # 颞叶前部补充
#     "EEG A1-LE",  # 左耳参考（也可作为EEG）
#     "EEG A2-LE",  # 右耳参考（也可作为EEG）
    
#     # 伪迹参考通道（重要！）
#     # "EEG PG1-LE",  # 生理信号1 - 可能是心电/眼电
#     # "EEG PG2-LE",  # 生理信号2 - 可能是眼电/呼吸
    
#     # 运动监测通道（用于伪迹检测）
#     "EEG RLC-LE",  # 右腿/身体运动
#     "EEG LUC-LE",  # 左腿/身体运动
    
#     # 其他可能相关的EEG通道
#     "EEG SP1-LE",  # 特殊电极1（保留，除非确认无用）
#     "EEG SP2-LE",  # 特殊电极2（保留，除非确认无用）
#     "EEG 30-LE",   # 编号电极（保留，除非确认无用）
    
    
#     # 标准10-20系统电极（19个）
#     "EEG FP1-REF",
#     "EEG FP2-REF", 
#     "EEG F3-REF",
#     "EEG F4-REF",
#     "EEG C3-REF",
#     "EEG C4-REF",
#     "EEG P3-REF",
#     "EEG P4-REF",
#     "EEG O1-REF",
#     "EEG O2-REF",
#     "EEG F7-REF",
#     "EEG F8-REF",
#     "EEG T3-REF",  # 颞叶中部
#     "EEG T4-REF",  # 颞叶中部
#     "EEG T5-REF",  # 颞叶后部
#     "EEG T6-REF",  # 颞叶后部
#     "EEG FZ-REF",  # 额中线
#     "EEG CZ-REF",  # 中央中线
#     "EEG PZ-REF",  # 顶中线
#     "EEG T1-REF",
#     "EEG T2-REF",  
    
#     # 附加EEG电极
#     "EEG T1-REF",  # 颞叶前部补充
#     "EEG T2-REF",  # 颞叶前部补充
#     "EEG A1-REF",  # 左耳参考（也可作为EEG）
#     "EEG A2-REF",  # 右耳参考（也可作为EEG）
    
#     # 伪迹参考通道（重要！）
#     "EEG PG1-REF",  # 生理信号1 - 可能是心电/眼电
#     "EEG PG2-REF",  # 生理信号2 - 可能是眼电/呼吸
    
#     # 运动监测通道（用于伪迹检测）
#     "EEG ROC-REF",  # 右腿/身体运动
#     "EEG LOC-REF",  # 左腿/身体运动
    
#     # 其他可能相关的EEG通道
#     "EEG A1-REF",  # 特殊电极1（保留，除非确认无用）
#     "EEG A2-REF",  # 特殊电极2（保留，除非确认无用）
# ]
# def load_visualization(file_path: Path, channels_to_filter=None, channels_to_keep=channels_to_keep):
#     """读取可视化json文件，支持过滤指定通道或只保留指定通道
    
#     Args:
#         file_path: JSON文件路径
#         channels_to_filter: 要过滤的通道模式列表（优先使用）
#         channels_to_keep: 要保留的通道名称列表（channels_to_filter为None时使用）
#     """
#     if channels_to_filter is None:
#         # channels_to_filter = ['Temp', 'Plet', 'EXG', 'GSR']
#         channels_to_filter = ["HEO", "VEO", "EKG", "EMG", "PHOTIC"]
    
#     if not file_path.exists():
#         return {}
    
#     with file_path.open("r", encoding="utf-8") as f:
#         json_data = json.load(f)
#     # import pdb;pdb.set_trace()    
#     # # 构建正则表达式模式
#     # patterns = [
#     #     re.compile(r'^EXG\d*$', re.IGNORECASE),  # EXG后跟任何数字
#     #     re.compile(r'^Temp$', re.IGNORECASE),    # Temp
#     #     re.compile(r'^Plet$', re.IGNORECASE),    # Plet  
#     #     re.compile(r'^Resp$', re.IGNORECASE),
#     #     re.compile(r'^X$', re.IGNORECASE),
#     #     re.compile(r'^Y$', re.IGNORECASE),
#     #     re.compile(r'^Z$', re.IGNORECASE),
#     #     re.compile(r'^x.*$', re.IGNORECASE),
#     #     re.compile(r'^y.*$', re.IGNORECASE),
#     #     re.compile(r'^z.*$', re.IGNORECASE),
#     #     re.compile(r'^EKG$', re.IGNORECASE),
#     #     re.compile(r'^TRIG$', re.IGNORECASE),
#     #     re.compile(r'^EoG$', re.IGNORECASE),
#     #     re.compile(r'^EOG.*$', re.IGNORECASE),
#     #     re.compile(r'^ECG\d*$', re.IGNORECASE),
#     #     re.compile(r'^VEOG$', re.IGNORECASE),
#     #     re.compile(r'^HEOG$', re.IGNORECASE),
#     #     re.compile(r'^HEO$', re.IGNORECASE),
#     #     re.compile(r'^VEO$', re.IGNORECASE),
#     #     re.compile(r'^Erg\d*$', re.IGNORECASE), 
#     #     re.compile(r'^BIP\d*$', re.IGNORECASE), 
#     #     re.compile(r'^KNEE$', re.IGNORECASE),
#     #     re.compile(r'^ANKLE$', re.IGNORECASE),
#     #     re.compile(r'^HIP\d*$', re.IGNORECASE),
#     #     re.compile(r'^EMG.*$', re.IGNORECASE),
#     #     re.compile(r'^SCR$', re.IGNORECASE),
#     #     re.compile(r'^AudioOutput$', re.IGNORECASE),
#     #     re.compile(r'^Empty$', re.IGNORECASE),
#     #     re.compile(r'^DC\d*$', re.IGNORECASE),
#     #     re.compile(r'^A2$', re.IGNORECASE),
#     #     re.compile(r'^GSR\d*$', re.IGNORECASE),     # GSR
#     # ]
    
#     # # 根据你的EEG数据建议的保留通道
#     # if channels_to_keep is not None:
#     #     # 将保留通道列表转换为小写，便于不区分大小写比较
#     #     keep_channels_lower = [ch.lower() for ch in channels_to_keep]
        
#     #     def should_keep_channel(channel_name):
#     #         # 检查是否在保留列表中（不区分大小写）
#     #         return channel_name.lower() in keep_channels_lower
#     # # 处理 'channels' 字段
#     # if 'channels' in json_data and isinstance(json_data['channels'], dict):
#     #     if channels_to_keep is not None:
#     #         # 只保留指定通道
#     #         json_data['channels'] = {
#     #             channel_name: channel_data 
#     #             for channel_name, channel_data in json_data['channels'].items()
#     #             if should_keep_channel(channel_name)
#     #         }
#     #     else:
#     #         # 过滤指定通道模式
#     #         json_data['channels'] = {
#     #             channel_name: channel_data 
#     #             for channel_name, channel_data in json_data['channels'].items()
#     #             if not any(pattern.match(channel_name) for pattern in patterns)
#     #         }
#     json_data['channels'] = {
#         channel_name: channel_data 
#         for channel_name, channel_data in json_data['channels'].items()
#         if all(i.lower() not in channel_name.lower() for i in channels_to_filter)
#     }
    
#     # 处理 'psd' 字段
#     if 'psd' in json_data and isinstance(json_data['psd'], dict):
#         if channels_to_keep is not None:
#             # 只保留指定通道
#             json_data['psd'] = {
#                 channel_name: channel_data 
#                 for channel_name, channel_data in json_data['psd'].items()
#                 if should_keep_channel(channel_name)
#             }
#         else:
#             # 过滤指定通道模式
#             json_data['psd'] = {
#                 channel_name: channel_data 
#                 for channel_name, channel_data in json_data['psd'].items()
#                 if not any(pattern.match(channel_name) for pattern in patterns)
#             }
    
#     return json_data


def load_visualization(file_path: Path, channels_to_filter=None, channels_to_keep=None):
    """读取可视化json文件"""
    if channels_to_filter is None:
        channels_to_filter = ["HEO", "VEO", "EKG", "EMG", "PHOTIC"]
    
    if not file_path.exists():
        print(f"ERROR: File does not exist: {file_path}")
        return {}
    
    try:
        with file_path.open("r", encoding="utf-8") as f:
            json_data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load JSON from {file_path}: {e}")
        return {}
    
    # 使用 get() 避免 KeyError
    channels = json_data.get('channels')
    if channels is None:
        print(f"WARNING: 'channels' key not found in {file_path}")
        print(f"Available keys: {list(json_data.keys())}")
        json_data['channels'] = {}
    elif isinstance(channels, dict):
        if channels_to_keep is not None:
            keep_channels_lower = [ch.lower() for ch in channels_to_keep]
            json_data['channels'] = {
                channel_name: channel_data 
                for channel_name, channel_data in channels.items()
                if channel_name.lower() in keep_channels_lower
            }
        else:
            json_data['channels'] = {
                channel_name: channel_data 
                for channel_name, channel_data in channels.items()
                if all(i.lower() not in channel_name.lower() for i in channels_to_filter)
            }
    else:
        print(f"WARNING: 'channels' is not a dict (type: {type(channels)})")
        json_data['channels'] = {}
    
    psd_data = json_data.get('psd')
    if psd_data is not None and isinstance(psd_data, dict):
        if channels_to_keep is not None:
            keep_channels_lower = [ch.lower() for ch in channels_to_keep]
            json_data['psd'] = {
                channel_name: channel_data 
                for channel_name, channel_data in psd_data.items()
                if channel_name.lower() in keep_channels_lower
            }
        else:
            json_data['psd'] = {
                channel_name: channel_data 
                for channel_name, channel_data in psd_data.items()
                if all(i.lower() not in channel_name.lower() for i in channels_to_filter)
            }
    
    return json_data

def get_psd_image_path(file_path: Path):
    """根据原始文件路径生成PSD图片路径"""
    # 假设PSD图片存放在precomputed目录，文件名规则为：原文件名_psd.png
    # 例如: raw_data/subject1/session1.fif -> precomputed/subject1/session1_psd.png
    # import pdb; pdb.set_trace()
    # psd_path = file_path.with_suffix('').with_suffix('_psd.png')
    psd_path = file_path.parent / f"{file_path.stem}_psd.png"
    # 转换目录结构，从raw_data到precomputed
    psd_path = Path(str(psd_path).replace('raw_data', 'precomputed').replace('\\', '/'))
    
    # 检查文件是否存在
    if psd_path.exists():
        return str(psd_path)
    else:
        # # 如果不存在，尝试其他可能的命名规则
        # alternative_path = file_path.with_suffix('').with_suffix('_psd.jpg')
        # alternative_path = Path(str(alternative_path).replace('raw_data', 'precomputed'))
        # if alternative_path.exists():
        #     return str(alternative_path)
        # else:
        #     return None
        return None
