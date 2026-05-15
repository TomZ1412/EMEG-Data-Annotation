#!/bin/bash

# Configuration
JSONL_FILE="/mnt/petrelfs/xiaoqinfan/ZZH/code/backend/process_data/brainfiles_metadata.jsonl"
DIR1="/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/pretrain/EEG"
DIR2="/mnt/petrelfs/xiaoqinfan/ZZH/data/BrainDataBase/pretrain/check_processed"

# 检查文件是否存在
[ -f "$JSONL_FILE" ] || { echo "错误: JSONL文件 '$JSONL_FILE' 不存在"; exit 1; }

# 创建目标目录
mkdir -p "$DIR2"

# 逐行读取JSONL文件
while IFS= read -r line; do
    # 提取file_path字段的值（使用grep和sed）
    filepath=$(echo "$line" | grep -o '"file_path": "[^"]*"' | sed 's/"file_path": "//' | sed 's/"$//')
    
    # 检查是否成功提取
    if [ -z "$filepath" ]; then
        echo "警告: 无法解析行: $line"
        continue
    fi
    
    echo "处理: $filepath"
    
    # 获取文件名和相对路径
    # 从完整路径中提取相对于DIR1的部分
    relative_path="${filepath#$DIR1/}"
    
    # 检查文件是否在DIR1下
    if [ "$relative_path" = "$filepath" ]; then
        echo "  警告: 文件路径不在 $DIR1 下: $filepath"
        continue
    fi
    
    # 检查源文件是否存在
    if [ ! -f "$filepath" ]; then
        echo "  警告: 源文件不存在: $filepath"
        continue
    fi
    
    # 构建目标路径
    dest_file="$DIR2/$relative_path"
    dest_dir=$(dirname "$dest_file")
    
    # 创建目录并复制
    mkdir -p "$dest_dir"
    echo "  复制: $(basename "$filepath") -> $dest_dir/"
    cp "$filepath" "$dest_file"
    
    if [ $? -eq 0 ]; then
        echo "    ✓ 成功"
    else
        echo "    ✗ 失败"
    fi
    
done < "$JSONL_FILE"

echo "完成!"