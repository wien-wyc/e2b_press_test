import os
import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from queue import Queue
import signal
import sys
from collections import defaultdict
import argparse
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox

# 加载环境变量
load_dotenv()
pid = os.getpid()

# 从环境变量获取配置
API_KEY = os.getenv("E2B_API_KEY")
BASE_URL = os.getenv("E2B_BASE_URL")
TEMPLATE_ID = os.getenv("E2B_TEMPLATE_ID")
TIMEOUT = int(os.getenv("E2B_TIMEOUT", 240))


# 使用线程安全的列表存储sandbox信息
sandbox_queue = Queue()
sandbox_lock = Lock()

operation_times = defaultdict(list)

def calculate_percentiles(times):
    if not times:
        return 0, 0, 0

    sorted_times = sorted(times)
    length = len(sorted_times)

    # 计算p99的索引
    p99_idx = int(length * 0.99)
    if p99_idx == length:
        p99_idx = length - 1

    # 计算p90的索引
    p90_idx = int(length * 0.90)
    if p90_idx == length:
        p90_idx = length - 1

    # 计算平均值
    avg = sum(sorted_times) / length

    return sorted_times[p99_idx], sorted_times[p90_idx], avg

def signal_handler(sig, frame):
    print_info()
    sys.exit(0)


def print_info():
    print(f"\n\n===  {pid} Operation Statistics ===")
    # Open CSV file in append mode
    with open(f'report_{pid}.csv', 'a') as csvfile:
        # Write header if file is empty
        if csvfile.tell() == 0:
            csvfile.write("timestamp,operation,count,p99,p90,avg\n")

        # Get current timestamp
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")

        for op in ['create', 'pause', 'resume']:
            if operation_times[op]:
                p99, p90, avg = calculate_percentiles(operation_times[op])
                count = len(operation_times[op])

                # Print to console
                print(f"{op.capitalize()}:")
                print(f"  Count: {count}")
                print(f"  P99: {p99:.4f}s")
                print(f"  P90: {p90:.4f}s")
                print(f"  Avg: {avg:.4f}s")

                # Write to CSV
                csvfile.write(f"{current_time},{op},{count},{p99:.4f},{p90:.4f},{avg:.4f}\n")

    print("============================")


def create_single_sandbox():
    """创建单个sandbox"""
    start_time = time.time()
    try:
        # 创建sandbox
        sbx = Sandbox(template=TEMPLATE_ID, timeout=300*2)
        sandbox_id = sbx.get_info().sandbox_id
        duration = time.time() - start_time
        operation_times['create'].append(duration)
        print(f"sandbox {sandbox_id} create time: {duration}s")

        # 使用SDK上传python程序
        for file_path in upload_files:
            with open(file_path, "rb") as file:
                file_content = file.read()
                file_name = file_path.split('/')[-1]
                sbx.files.write(f"/home/user/{file_name}", file_content)

        # 在sandbox中执行上传的python程序
        if upload_files:
            first_file = upload_files[0].split('/')[-1]
            execution = sbx.commands.run(f"python /home/user/{first_file}")
            print(f"{sandbox_id}: stdout: {execution.stdout}")

        print(f"sandbox [{sandbox_id}] code execution time: {time.time() - start_time}s")

        sandbox_queue.put({"id": sandbox_id, "running": True})
    except Exception as e:
        print(f"Error creating sandbox: {str(e)}")


def connect_sandbox(sandbox_id):
    """连接sandbox"""
    try:
        start_time = time.time()
        sbx = Sandbox.connect(sandbox_id=sandbox_id)
        print(f"sandbox {sandbox_id} create time: {time.time() - start_time}s")

        execution = sbx.commands.run("ls -l /home/user")
        print(f"{sandbox_id}: ls -l /home/user: {execution.stdout}")

        # 随机上传一个文件(pi.py会运行在后台)
        file_to_run = random.choice(upload_files)
        file_name = file_to_run.split('/')[-1]

        with open(file_to_run, "rb") as file:
            file_content = file.read()
            sbx.files.write(f"/home/user/{file_name}", file_content)
            if 'pi.py' in file_name:
                # 运行pi.py在后台
                sbx.commands.run(f"python /home/user/{file_name}", background=True)
                print(f"{sandbox_id}: Running {file_name} in background")
            else:
                # 正常运行文件并等待输出
                execution = sbx.commands.run(f"python /home/user/{file_name}")
                print(f"{sandbox_id}: stdout: {execution.stdout}")

        print(f"sandbox [{sandbox_id}] code execution time: {time.time() - start_time}s")
        return True

    except Exception as e:
        print(f"Error connecting sandbox: {str(e)}")
        return False

def create_sandbox(max_workers=10):
    """创建多个sandbox"""
    total_time = time.time()
    with ThreadPoolExecutor(max_workers) as executor:
        futures = [executor.submit(create_single_sandbox) for _ in range(sandbox_num)]
        for future in futures:
            future.result()
    print(f"total time: {time.time() - total_time}s")

def select_sandbox():
    """选择sandbox进行暂停或者恢复操作"""
    with ThreadPoolExecutor(max_workers=5) as executor:
        for _ in range(20):
            try:
                # 获取当前所有sandbox状态
                current_sandboxes = []
                while not sandbox_queue.empty():
                    current_sandboxes.append(sandbox_queue.get())

                if not current_sandboxes:
                    continue

                random_sandbox = random.choice(current_sandboxes)
                if random_sandbox["running"]:
                    future = executor.submit(pause_sandbox, random_sandbox["id"])
                    if not future.result():
                        # 如果暂停失败，创建新的sandbox替换
                        executor.submit(create_single_sandbox)
                    else:
                        random_sandbox["running"] = False
                        current_sandboxes[current_sandboxes.index(random_sandbox)]=random_sandbox
                else:
                    future = executor.submit(resume_sandbox, random_sandbox["id"])
                    if not future.result():
                        # 如果恢复失败，创建新的sandbox替换
                        print(f"sandbox {random_sandbox['id']} resume failed, create new sandbox")
                        current_sandboxes.remove(random_sandbox)
                        executor.submit(create_single_sandbox)

                    else:
                        # 恢复后连接sandbox, 并运行对应的文件
                        run_code = connect_sandbox(random_sandbox["id"])
                        if run_code:
                            random_sandbox["running"] = True
                            current_sandboxes[current_sandboxes.index(random_sandbox)]=random_sandbox

                        else:
                            # 如果连接失败，创建新的sandbox替换
                            print(f"sandbox {random_sandbox['id']} connect failed, create new sandbox")
                            current_sandboxes.remove(random_sandbox)
                            executor.submit(create_single_sandbox)
                            continue

                # 将处理后的sandbox信息放回队列
                for sandbox in current_sandboxes:
                    sandbox_queue.put(sandbox)
                print_info()

            except Exception as e:
                print(f"Error in select_sandbox: {str(e)}")


def pause_sandbox(combined_id):
    """使用RESTAPI暂停Sandbox"""
    url = f"{BASE_URL}/sandboxes/{combined_id}/pause"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    start_time = time.time()
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        duration = time.time() - start_time
        operation_times['pause'].append(duration)
        print(f"暂停成功! sandboxID: {combined_id}, 耗时: {duration:.4f} 秒")


        return True
    except Exception as e:
        print(f"暂停 Sandbox {combined_id} 失败: {str(e)}, 耗时: {time.time() - start_time:.4f} 秒")
        return False



def resume_sandbox(combined_id):
    """使用RESTAPI恢复Sandbox"""
    url = f"{BASE_URL}/sandboxes/{combined_id}/resume"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "timeout": TIMEOUT
    }

    start_time = time.time()
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        duration = time.time() - start_time
        operation_times['resume'].append(duration)
        print(f"恢复成功! sandboxID: {combined_id}, 耗时: {duration:.4f} 秒")


        return True
    except Exception as e:
        print(f"恢复 Sandbox {combined_id} 失败: {str(e)}, 耗时: {time.time() - start_time:.4f} 秒")
        return False


if __name__ == "__main__":
    # 设置参数解析器
    parser = argparse.ArgumentParser(description='Sandbox management script')
    parser.add_argument('--workers', type=int, default=1,
                      help='Number of workers (default: 10)')
    parser.add_argument('--sandboxes', type=int, default=20,
                      help='Number of sandboxes to create (default: 20)')
    parser.add_argument('--files', nargs='+', default=["./hello.py", "./pi.py"],
                      help='List of files to upload (default: ./hello.py ./pi.py)')

    # 解析参数
    args = parser.parse_args()

    # 更新变量
    worker_num = args.workers
    sandbox_num = args.sandboxes
    upload_files = args.files

    print(f"API_URL: {BASE_URL} {TEMPLATE_ID} " )
    print(f"worker_num: {worker_num} sandbox_num: {sandbox_num} upload_files: {upload_files} " )
    # 注册信号处理ctrl+c
    signal.signal(signal.SIGINT, signal_handler)

    create_sandbox(max_workers=worker_num)
    while True:
        select_sandbox()
        time.sleep(1)