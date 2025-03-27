import concurrent.futures
import os
import statistics
import time
import numpy as np
import pandas as pd
import requests
from tqdm import tqdm
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置参数
API_KEY = os.getenv("E2B_API_KEY")
BASE_URL = os.getenv("E2B_BASE_URL") + "/sandboxes"
RESULTS_CSV_FILE = "create_results.csv"
MAX_SANDBOXES_TO_PAUSE = 100  # 只暂停前100个sandbox

def pause_sandbox(combined_id):
    """暂停指定的sandbox并返回操作时间"""
    start_time = time.time()

    # 从combined_id中提取sandbox_id (格式是sandboxID-clientID)
    sandbox_id = combined_id.split('-')[0] if '-' in combined_id else combined_id

    url = f"{BASE_URL}/{combined_id}/pause"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers)
        duration_ms = (time.time() - start_time) * 1000

        # 修改为接受更广泛的成功状态码
        if response.status_code in [200, 201, 202, 204]:
            return combined_id, sandbox_id, duration_ms, None
        else:
            error_msg = f"暂停失败，状态码: {response.status_code}, 错误: {response.text[:100]}..."
            return combined_id, sandbox_id, -1, error_msg
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return combined_id, sandbox_id, -1, str(e)

def load_combined_ids_from_csv():
    """从CSV文件加载combined ID (sandboxID-clientID)"""
    if not os.path.exists(RESULTS_CSV_FILE):
        print(f"错误: {RESULTS_CSV_FILE} 文件不存在")
        return []

    try:
        # 读取CSV文件
        df = pd.read_csv(RESULTS_CSV_FILE)

        # 首先检查是否存在combined_id列
        if 'combined_id' in df.columns:
            combined_ids = df['combined_id'].dropna().tolist()
            print(f"从 {RESULTS_CSV_FILE} 加载了 {len(combined_ids)} 个combined ID")
            return combined_ids
        # 如果没有combined_id列，则检查是否存在sandbox_id列
        elif 'sandbox_id' in df.columns:
            sandbox_ids = df['sandbox_id'].dropna().tolist()
            print(f"从 {RESULTS_CSV_FILE} 加载了 {len(sandbox_ids)} 个sandbox ID")
            return sandbox_ids
        else:
            print(f"错误: {RESULTS_CSV_FILE} 中没有找到 'combined_id' 或 'sandbox_id' 列")
            return []
    except Exception as e:
        print(f"读取CSV文件时出错: {e}")
        return []

def calculate_stats(times):
    """计算时间统计数据，包括p99和p90"""
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

def pause_sandboxes():
    """暂停前100个从CSV文件加载的sandbox"""
    combined_ids = load_combined_ids_from_csv()
    if not combined_ids:
        return

    # 只取前100个sandbox
    combined_ids = combined_ids[:MAX_SANDBOXES_TO_PAUSE]

    print(f"开始暂停 {len(combined_ids)} 个sandbox...")
    pause_results = []
    errors = []

    # 使用单线程暂停sandbox
    with tqdm(total=len(combined_ids), desc="暂停sandbox") as pbar:
        for i, combined_id in enumerate(combined_ids):
            # 暂停当前sandbox
            combined_id, sandbox_id, pause_time, error = pause_sandbox(combined_id)

            if error:
                errors.append((combined_id, error))
                print(f"暂停 {combined_id} 失败: {error}")

            pause_results.append((combined_id, sandbox_id, pause_time))
            pbar.update(1)

            # 显示实时成功率
            success_count = len([t for _, _, t in pause_results if t > 0])
            success_rate = success_count / (i + 1) * 100
            pbar.set_postfix({'success': f"{success_rate:.1f}%"})

    # 提取暂停时间
    pause_times = [time for _, _, time in pause_results if time > 0]

    # 计算统计数据
    stats = calculate_stats(pause_times)

    print(f"\n成功暂停 {len(pause_times)}/{len(combined_ids)} 个sandbox ({len(pause_times)/len(combined_ids)*100:.1f}%)")
    print(f"暂停时间统计 (ms):")
    print(f"  最小: {stats['min']:.2f}")
    print(f"  最大: {stats['max']:.2f}")
    print(f"  平均: {stats['avg']:.2f}")
    print(f"  中位数: {stats['median']:.2f}")
    print(f"  90%分位 (P90): {stats['p90']:.2f}")
    print(f"  99%分位 (P99): {stats['p99']:.2f}")

    # 创建详细的结果数据
    results = pd.DataFrame({
        "combined_id": [cid for cid, _, _ in pause_results],
        "sandbox_id": [sid for _, sid, _ in pause_results],
        "pause_time_ms": [time for _, _, time in pause_results]
    })
    results.to_csv("pause_results.csv", index=False)
    print("暂停结果已保存到 pause_results.csv")

    # 保存错误信息
    if errors:
        with open("pause_errors.txt", "w") as f:
            for combined_id, error in errors:
                f.write(f"{combined_id}: {error}\n")
        print(f"错误信息已保存到 pause_errors.txt ({len(errors)} 个错误)")

if __name__ == "__main__":
    pause_sandboxes()