import mne
import json
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from app.config import RAW_DATA_ROOT, VIS_DATA_ROOT
import time
from tqdm import tqdm
import os


def preprocess_dataset_all(skip_existing=True, delta_t=30, max_folders=5):
    """
    遍历 RAW_DATA_ROOT 下前 max_folders 个文件夹中的 .con / .edf / .fif / .dat 文件，以及以 .ds 结尾的文件夹，
    按照 delta_t 分段生成 waveform_0.json, waveform_1.json ... 和 psd.json 保存到 VIS_DATA_ROOT 下相同目录。
    如果 skip_existing=True，则跳过已存在的文件。
    """
    print(f"RAW_DATA_ROOT: {RAW_DATA_ROOT}")
    DATA_ROOT_PATH = Path(RAW_DATA_ROOT)
    PRECOMPUTED_ROOT_PATH = Path(VIS_DATA_ROOT)

    FILE_EXTENSIONS = {'.con', '.edf', '.fif', '.dat', '.bdf', '.set'}
    
    print("正在扫描根目录下的文件夹...")
    start_time = time.time()
    
    # 获取根目录下的所有文件夹（只处理一级子目录）
    all_folders = [f for f in DATA_ROOT_PATH.iterdir() if f.is_dir()]
    all_folders.sort()  # 按名称排序
    
    # 只取前 max_folders 个文件夹
    selected_folders = all_folders[:max_folders]
    
    print(f"找到 {len(all_folders)} 个文件夹，选择前 {len(selected_folders)} 个进行处理:")
    for i, folder in enumerate(selected_folders, 1):
        print(f"  {i}. {folder.name}")
    
    # 收集所有需要处理的文件
    allowed_files = []
    for folder in selected_folders:
        print(f"\n扫描文件夹: {folder.name}")
        folder_files = []
        for f in folder.rglob('*'):
            if f.is_file() and f.suffix in FILE_EXTENSIONS:
                folder_files.append(f)
            elif f.is_dir() and f.name.endswith('.ds'):
                folder_files.append(f)
        
        print(f"  在 {folder.name} 中找到 {len(folder_files)} 个文件")
        allowed_files.extend(folder_files)
    
    if not allowed_files:
        print(f"在选定的文件夹中没有找到允许的文件类型")
        return
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"\n扫描完成。找到文件/文件夹数量: {len(allowed_files)}")
    print(f"扫描时间: {elapsed_time:.4f} 秒")
    
    # 处理文件
    print(f"\n开始处理文件...")
    total_files = len(allowed_files)
    processed_files = 0
    successful_files = 0
    failed_files = 0
    
    # 创建总体进度条
    with tqdm(total=total_files, desc="总体进度", unit="file") as pbar:    
        # import pdb;pdb.set_trace()
        for file in allowed_files:
            processed_files += 1
            try:
                # 输出路径
                dataset_path = file.relative_to(DATA_ROOT_PATH).parent
                file_name = file.stem if file.is_file() else file.name
                out_dir = PRECOMPUTED_ROOT_PATH / dataset_path
                out_dir.mkdir(parents=True, exist_ok=True)

                # 更新进度条描述
                pbar.set_description(f"处理: {file_name[:30]}...")
                # import pdb;pdb.set_trace()
                # if file.suffix == '.set':
                #     raw = mne.io.read_raw_eeglab(file,verbose=False)
                # else:
                # ✅ 读取数据
                # if file_name
                raw = mne.io.read_raw(file, preload=True, verbose=False)
                sfreq = raw.info['sfreq']
                raw.pick_types(
                    meg=False,           # MEG 通道
                    eeg=True,           # EEG 通道  
                    stim=False,          # 刺激通道
                    eog=False,           # 眼电
                    ecg=False,           # 心电
                    emg=False,           # 肌电
                    misc=False,          # 杂项通道（temp, plet 等通常在这里）
                    ref_meg=False,       # 参考 MEG 通道
                    resp=False,          # 呼吸
                    chpi=False,          # 头部位置指示器
                    exci=False,          # 激励器
                    ias=False,           # 内部主动屏蔽
                    syst=False,          # 系统时钟
                    seeg=False,          # 立体脑电图
                    dipole=False,        # 偶极子
                    gof=False,           # 拟合优度
                    bio=False,           # 生物信号
                    ecog=False,          # 皮层脑电图
                    fnirs=False,         # 功能性近红外光谱
                    csd=False,           # 电流源密度
                    dbs=False,           # 深部脑刺激
                    temperature=False,   # 温度
                    gsr=False,           # 皮肤电反应
                    eyetrack=False,      # 眼动追踪
                    # 其他参数
                    selection=None,     # 特定通道选择
                    exclude='bads'      # 排除坏通道
                )
                # raw.resample(sfreq)

                # 获取数据信息
                data = raw.get_data()
                ch_names = raw.ch_names
                n_channels, n_times = data.shape
                duration = n_times / sfreq  # 总时长（秒）
                
                # 计算分段信息
                samples_per_segment = int(delta_t * sfreq)  # 每个分段的样本数
                n_segments = int(np.ceil(n_times / samples_per_segment))  # 总分段数
                
                # 检查是否需要跳过（如果所有分段文件都存在）
                all_waveform_files_exist = True
                for seg_idx in range(n_segments):
                    waveform_file = out_dir / f"{file_name}_wav_{seg_idx}.json"
                    if not waveform_file.exists():
                        all_waveform_files_exist = False
                        break
                
                psd_json_file = out_dir / f"{file_name}_psd.json"
                
                if True:
                    # psds, freqs = mne.time_frequency.psd_array_welch(
                    #     data, 
                    #     sfreq=sfreq, 
                    #     fmin=0, 
                    #     fmax=sfreq,
                    #     n_fft=min(2048, data.shape[1]),
                    #     n_per_seg=min(512, data.shape[1]),
                    #     verbose=False
                    # )
                    psd = raw.compute_psd()
                    psd_data = psd.get_data()  # 获取PSD数据数组
                    freqs = psd.freqs  # 获取频率点
                    ch_names = psd.ch_names
                    # 构建PSD数据结构
                    psd_data = {
                        "frequencies": freqs.tolist(),
                        "psd": {}
                    }
                    import pdb;pdb.set_trace()
                    for i, ch_name in enumerate(ch_names):
                        psd_data["psd"][ch_name] = psd[i].tolist()
                    # 保存PSD JSON文件
                    with open(psd_json_file, "w") as f:
                        json.dump(psd_data, f)
                
                if skip_existing and all_waveform_files_exist and psd_json_file.exists():
                    pbar.set_description(f"跳过: {file_name[:30]}...")
                    pbar.update(1)
                    continue

                # ---- 分段保存波形数据 ----
                # 创建分段进度条
                # segment_pbar = tqdm(total=n_segments, desc="  分段进度", leave=False, unit="segment")
                for seg_idx in range(n_segments):
                    waveform_file = out_dir / f"{file_name}_wav_{seg_idx}.json"
                    
                    # 如果文件已存在且跳过模式，则跳过
                    if skip_existing and waveform_file.exists():
                        # segment_pbar.update(1)
                        continue
                    
                    # 计算当前分段的起始和结束样本
                    start_sample = seg_idx * samples_per_segment
                    end_sample = min((seg_idx + 1) * samples_per_segment, n_times)
                    
                    # 提取当前分段的数据
                    segment_data = data[:, start_sample:end_sample]
                    
                    # 构建波形数据结构
                    waveform = {
                        "segment_index": seg_idx,
                        "total_segments": n_segments,
                        "start_time": start_sample / sfreq,
                        "end_time": end_sample / sfreq,
                        "duration": (end_sample - start_sample) / sfreq,
                        "channels": {}
                    }
                    
                    # 为每个通道添加数据
                    for i, ch_name in enumerate(ch_names):
                        waveform["channels"][ch_name] = segment_data[i].tolist()
                    
                    # 保存分段波形文件
                    with open(waveform_file, "w") as f:
                        json.dump(waveform, f)
                    
                    # segment_pbar.update(1)
                
                # segment_pbar.close()

                # ---- 计算并保存 PSD 数据为 JSON ----
                # if not (skip_existing and psd_json_file.exists()):
                

                successful_files += 1
                pbar.set_description(f"完成: {file_name[:30]}...")
                pbar.update(1)

            except Exception as e:
                failed_files += 1
                pbar.set_description(f"失败: {file_name[:30]}...")
                print(f"\n处理失败 {file}: {e}")
                pbar.update(1)
    # 输出统计信息
    print(f"\n处理完成!")
    print(f"总文件数: {total_files}")
    print(f"成功处理: {successful_files}")
    print(f"处理失败: {failed_files}")
    print(f"跳过文件: {total_files - successful_files - failed_files}")


if __name__ == "__main__":
    preprocess_dataset_all(max_folders=10)