import requests
import json
import time
import pandas as pd
from tqdm import tqdm
import os
import statistics
import numpy as np
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置参数
API_KEY = os.getenv("E2B_API_KEY")
BASE_URL = os.getenv("E2B_BASE_URL") + "/sandboxes"
TIMEOUT = int(os.getenv("E2B_TIMEOUT", 300))
PAUSE_RESULTS_FILE = "pause_results.csv"  # 从暂停结果文件中读取sandbox IDs

def resume_sandbox(combined_id):
    """恢复指定的sandbox并返回操作时间"""
    start_time = time.time()

    url = f"{BASE_URL}/{combined_id}/resume"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "timeout": TIMEOUT
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        duration_ms = (time.time() - start_time) * 1000

        # 从combined_id中提取sandbox_id (格式是sandboxID-clientID)
        sandbox_id = combined_id.split('-')[0] if '-' in combined_id else combined_id

        # 修改为接受更广泛的成功状态码 (200, 201, 202, 204)
        if response.status_code in [200, 201, 202, 204]:
            return combined_id, sandbox_id, duration_ms
        else:
            print(f"恢复失败 {combined_id} (sandbox_id: {sandbox_id})，状态码: {response.status_code}, 错误: {response.text}")
            return combined_id, sandbox_id, -1
    except Exception as e:
        sandbox_id = combined_id.split('-')[0] if '-' in combined_id else combined_id
        print(f"恢复失败 {combined_id} (sandbox_id: {sandbox_id})，错误: {str(e)}")
        return combined_id, sandbox_id, -1

def load_combined_ids_from_pause_results():
    """从暂停结果CSV文件加载combined ID"""
    if not os.path.exists(PAUSE_RESULTS_FILE):
        print(f"错误: {PAUSE_RESULTS_FILE} 文件不存在")
        return []

    try:
        # 读取CSV文件
        df = pd.read_csv(PAUSE_RESULTS_FILE)

        # 检查是否存在combined_id列
        if 'combined_id' in df.columns:
            # 只选择暂停成功的sandbox (pause_time_ms > 0)
            if 'pause_time_ms' in df.columns:
                successful_df = df[df['pause_time_ms'] > 0]
                combined_ids = successful_df['combined_id'].tolist()
                print(f"从 {PAUSE_RESULTS_FILE} 加载了 {len(combined_ids)} 个成功暂停的combined ID")
            else:
                combined_ids = df['combined_id'].tolist()
                print(f"从 {PAUSE_RESULTS_FILE} 加载了 {len(combined_ids)} 个combined ID")
            return combined_ids
        else:
            print(f"错误: {PAUSE_RESULTS_FILE} 中没有找到 'combined_id' 列")
            return []
    except Exception as e:
        print(f"读取CSV文件时出错: {e}")
        return []

def calculate_stats(times):
    """计算时间统计数据，包括p90和p99"""
    valid_times = [t for t in times if t > 0]
    if not valid_times:
        return {"min": 0, "max": 0, "avg": 0, "median": 0, "p90": 0, "p99": 0}

    return {
        "min": min(valid_times),
        "max": max(valid_times),
        "avg": sum(valid_times) / len(valid_times),
        "median": statistics.median(valid_times),
        "p90": np.percentile(valid_times, 90),
        "p99": np.percentile(valid_times, 99)
    }

def resume_sandboxes():
    """恢复所有从暂停结果文件加载的sandbox"""
    combined_ids = load_combined_ids_from_pause_results()
    if not combined_ids:
        return

    print(f"开始恢复 {len(combined_ids)} 个sandbox...")
    resume_results = []

    # 单线程恢复sandbox（不再有时间间隔）
    with tqdm(total=len(combined_ids), desc="恢复sandbox") as pbar:
        for i, combined_id in enumerate(combined_ids):
            # 恢复当前sandbox
            combined_id, sandbox_id, resume_time = resume_sandbox(combined_id)
            resume_results.append((combined_id, sandbox_id, resume_time))
            pbar.update(1)

            # 显示实时成功率
            success_count = len([t for _, _, t in resume_results if t > 0])
            success_rate = success_count / (i + 1) * 100
            pbar.set_postfix({'success': f"{success_rate:.1f}%"})

    # 提取恢复时间
    resume_times = [time for _, _, time in resume_results if time > 0]

    # 计算统计数据
    stats = calculate_stats(resume_times)

    print(f"\n成功恢复 {len(resume_times)}/{len(combined_ids)} 个sandbox ({len(resume_times)/len(combined_ids)*100:.1f}%)")
    print(f"恢复时间统计 (ms):")
    print(f"  最小: {stats['min']:.2f}")
    print(f"  最大: {stats['max']:.2f}")
    print(f"  平均: {stats['avg']:.2f}")
    print(f"  中位数: {stats['median']:.2f}")
    print(f"  90%分位 (P90): {stats['p90']:.2f}")
    print(f"  99%分位 (P99): {stats['p99']:.2f}")

    # 创建详细的结果数据
    results = pd.DataFrame({
        "combined_id": [cid for cid, _, _ in resume_results],
        "sandbox_id": [sid for _, sid, _ in resume_results],
        "resume_time_ms": [time for _, _, time in resume_results]
    })
    results.to_csv("resume_results.csv", index=False)
    print("恢复结果已保存到 resume_results.csv")

if __name__ == "__main__":
    resume_sandboxes()