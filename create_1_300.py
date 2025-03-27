import statistics
import time
import os
import pandas as pd
import requests
import numpy as np
from tqdm import tqdm
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置参数
API_KEY = os.getenv("E2B_API_KEY")
BASE_URL = os.getenv("E2B_BASE_URL") + "/sandboxes"
TEMPLATE_ID = os.getenv("E2B_TEMPLATE_ID")
TIMEOUT = int(os.getenv("E2B_TIMEOUT", 1200))
NUM_SANDBOXES = 300  # 300个sandbox
SANDBOX_IDS_FILE = "sandbox_ids.txt"
REQUEST_TIMEOUT = 5  # 请求超时时间，秒，单线程模式下可以设置更短


def create_sandbox(index):
    """创建一个sandbox并返回ID和创建时间"""
    start_time = time.time()

    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "templateID": TEMPLATE_ID,
        "timeout": TIMEOUT,
        "autoPause": True,
        "envVars": {
            "EXAMPLE_VAR": "example_value"
        },
        "metadata": {
            "purpose": f"performance-test-gj-{index}"
        }
    }

    try:
        response = requests.post(
            BASE_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        duration_ms = (time.time() - start_time) * 1000

        if response.status_code in [200, 201]:
            response_data = response.json()
            # 从响应中提取sandboxID和clientID
            sandbox_id = response_data.get("sandboxID")
            client_id = response_data.get("clientID")

            if not sandbox_id or not client_id:
                return None, None, duration_ms, f"响应中没有sandboxID或clientID: {response.text}"

            # 将sandboxID和clientID用横线连接
            combined_id = f"{sandbox_id}-{client_id}"
            return sandbox_id, combined_id, duration_ms, None
        else:
            return None, None, duration_ms, f"状态码: {response.status_code}, 错误: {response.text[:100]}..."
    except requests.exceptions.Timeout:
        duration_ms = (time.time() - start_time) * 1000
        return None, None, duration_ms, "请求超时"
    except requests.exceptions.RequestException as e:
        duration_ms = (time.time() - start_time) * 1000
        return None, None, duration_ms, f"请求异常: {str(e)}"

def save_sandbox_ids(combined_ids):
    """将sandbox ID保存到文件"""
    with open(SANDBOX_IDS_FILE, 'w') as f:
        for combined_id in combined_ids:
            f.write(f"{combined_id}\n")
    print(f"已将 {len(combined_ids)} 个combined ID (sandboxID-clientID) 保存到 {SANDBOX_IDS_FILE}")

def calculate_stats(times):
    """计算时间统计数据"""
    valid_times = [t for t in times if t > 0]
    if not valid_times:
        return {"min": 0, "max": 0, "avg": 0, "median": 0, "p90": 0, "p95": 0, "p99": 0}

    # 使用numpy计算百分位数，更准确
    return {
        "min": min(valid_times),
        "max": max(valid_times),
        "avg": sum(valid_times) / len(valid_times),
        "median": statistics.median(valid_times),
        "p90": np.percentile(valid_times, 90),
        "p95": np.percentile(valid_times, 95),
        "p99": np.percentile(valid_times, 99)
    }

def create_sandboxes():
    """创建指定数量的sandbox并保存ID - 单线程版本"""
    print(f"开始创建 {NUM_SANDBOXES} 个sandbox (单线程模式)...")

    # 初始化结果列表
    results = []
    sandbox_ids = []
    combined_ids = []
    create_times = []
    errors = []

    # 记录总体开始时间
    overall_start_time = time.time()

    # 计算每个请求的目标时间（为了达到每分钟300个）
    target_time_per_request = 60 / NUM_SANDBOXES  # 秒

    # 单线程循环创建sandbox
    with tqdm(total=NUM_SANDBOXES, desc="创建sandbox") as pbar:
        for i in range(NUM_SANDBOXES):
            request_start_time = time.time()

            # 创建sandbox
            sandbox_id, combined_id, create_time, error = create_sandbox(i)

            # 记录结果
            result = {
                "index": i,
                "sandbox_id": sandbox_id,
                "combined_id": combined_id,
                "create_time_ms": create_time,
                "error": error,
                "success": sandbox_id is not None
            }
            results.append(result)

            if sandbox_id and combined_id:
                sandbox_ids.append(sandbox_id)
                combined_ids.append(combined_id)
                create_times.append(create_time)
            else:
                errors.append(error)

            # 更新进度条
            pbar.update(1)

            # 显示实时成功率和速度
            elapsed = time.time() - overall_start_time
            success_rate = len(sandbox_ids) / (i + 1) * 100
            current_rate = (i + 1) / elapsed
            eta = (NUM_SANDBOXES - (i + 1)) / current_rate if current_rate > 0 else 0

            pbar.set_postfix({
                'success': f"{success_rate:.1f}%",
                'rate': f"{current_rate:.1f}/s",
                'eta': f"{eta:.1f}s"
            })

            # 计算需要等待的时间以达到目标速率
            elapsed_this_request = time.time() - request_start_time
            if elapsed_this_request < target_time_per_request and i < NUM_SANDBOXES - 1:
                time.sleep(max(0, target_time_per_request - elapsed_this_request))

    # 计算总耗时
    overall_duration = time.time() - overall_start_time

    # 保存combined IDs到文件
    if combined_ids:
        save_sandbox_ids(combined_ids)

    # 计算统计数据
    stats = calculate_stats(create_times)

    print(f"\n总耗时: {overall_duration:.2f} 秒")
    print(f"成功创建: {len(sandbox_ids)}/{NUM_SANDBOXES} ({len(sandbox_ids)/NUM_SANDBOXES*100:.1f}%)")
    print(f"创建速率: {len(sandbox_ids)/overall_duration:.2f} sandbox/秒")

    if create_times:
        print(f"创建时间统计 (ms):")
        print(f"  最小: {stats['min']:.2f}")
        print(f"  最大: {stats['max']:.2f}")
        print(f"  平均: {stats['avg']:.2f}")
        print(f"  中位数: {stats['median']:.2f}")
        print(f"  90%分位 (P90): {stats['p90']:.2f}")
        print(f"  95%分位 (P95): {stats['p95']:.2f}")
        print(f"  99%分位 (P99): {stats['p99']:.2f}")

    # 创建详细的结果数据
    df = pd.DataFrame(results)
    df.to_csv("create_results.csv", index=False)
    print("创建结果已保存到 create_results.csv")

    # 保存错误信息
    if errors:
        with open("errors.txt", "w") as f:
            for i, error in enumerate(errors):
                f.write(f"Error {i+1}: {error}\n")
        print(f"错误信息已保存到 errors.txt ({len(errors)} 个错误)")

if __name__ == "__main__":
    create_sandboxes()