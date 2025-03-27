from e2b_code_interpreter import Sandbox
import time
import concurrent.futures
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 无限π计算脚本 - 会持续计算直到被终止
pi_script = """
import math
from decimal import Decimal, getcontext
import time
import sys

# 接收进程ID作为命令行参数
process_id = int(sys.argv[1])

# 使用Chudnovsky算法计算π
def calculate_pi(digits):
    getcontext().prec = digits + 10

    C = 426880 * Decimal(10005).sqrt()
    M = Decimal(1)
    L = Decimal(13591409)
    X = Decimal(1)
    K = Decimal(6)
    S = L

    for i in range(1, digits // 14 + 10):
        M = M * (K**3 - 16*K) // (i**3)
        L += 545140134
        X *= -262537412640768000
        S += (M * L) / X
        K += 12

    pi = C / S
    return str(pi)[:digits+1]

# 持续计算π，不断增加位数
start_digits = 1000
max_digits = 1000000000  # 设置一个非常大的上限，实际上不会达到
current_digits = start_digits

print(f"进程 #{process_id} 开始持续计算π值...")
while current_digits <= max_digits:
    start_time = time.time()
    print(f"\\n进程 #{process_id} 计算π到{current_digits}位...")
    
    try:
        pi_value = calculate_pi(current_digits)
        end_time = time.time()
        
        print(f"进程 #{process_id} π计算结果 (前50位): {pi_value[:50]}...")
        print(f"进程 #{process_id} 总计算位数: {len(pi_value)-1}")
        print(f"进程 #{process_id} 计算耗时: {end_time - start_time:.2f} 秒")
        
        # 每次计算完后增加位数
        current_digits = int(current_digits * 1.5)  # 每次增加50%的位数
        
    except Exception as e:
        print(f"进程 #{process_id} 计算出错: {str(e)}")
        break
"""
num_boxes = 31
# 创建和配置单个Sandbox的函数
def create_and_run_sandbox(index):
    try:
        print(f"\n=== 创建 Sandbox #{index} ===")

        # 创建新的sandbox实例
        sbx = Sandbox(
            api_key=os.getenv("E2B_API_KEY"),
            template=os.getenv("E2B_TEMPLATE_ID"),
            domain=os.getenv("E2B_DOMAIN"),
            timeout=int(os.getenv("E2B_TIMEOUT", 3600)),
            metadata={"purpose": "performance-test-gj"}
        )

        sandbox_id = sbx.sandbox_id
        print(f"Sandbox #{index} ID: {sandbox_id}")

        # 创建计算π的Python脚本
        sbx.commands.run(f'cat > calculate_pi.py << \'EOF\'\n{pi_script}\nEOF')

        # 在同一个sandbox中启动4个计算进程
        print(f"在Sandbox #{index}中启动4个π计算进程...")
        for i in range(1, 5):
            sbx.commands.run(f"nice -n {i*5} nohup python3 calculate_pi.py {i} > pi_output_{i}.log 2>&1 &")
            print(f"Sandbox #{index} - 进程 #{i} 已启动")

        # 确认进程已启动
        result = sbx.commands.run("ps aux | grep python")
        python_processes = result.stdout.count("calculate_pi.py")

        if python_processes >= 4:
            print(f"Sandbox #{index} (ID: {sandbox_id}) 所有4个计算进程已成功启动")

            # 显示CPU负载情况
            cpu_info = sbx.commands.run("top -bn1 | head -n 5").stdout
            print(f"Sandbox #{index} CPU负载情况:\n{cpu_info}")

            return True, index, sandbox_id
        else:
            print(f"Sandbox #{index} (ID: {sandbox_id}) 只有{python_processes}个计算进程启动成功")
            return False, index, sandbox_id

    except Exception as e:
        print(f"Sandbox #{index} 创建或配置出错: {str(e)}")
        return False, index, "创建失败"

# 主程序
print("开始并行创建{}个Sandbox，每个Sandbox运行4个计算进程",num_boxes)

# 使用线程池并行创建Sandbox
successful_sandboxes = []
failed_sandboxes = []
# 设置较小的线程池大小以避免API限制
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    # 提交所有任务
    future_to_index = {executor.submit(create_and_run_sandbox, i): i for i in range(1, num_boxes)}

    # 处理结果
    for future in concurrent.futures.as_completed(future_to_index):
        success, index, sandbox_id = future.result()
        if success:
            successful_sandboxes.append((index, sandbox_id))
        else:
            failed_sandboxes.append((index, sandbox_id))

# 打印统计信息
print("\n========== 创建结果统计 ==========")
print(f"成功创建的Sandbox数量: {len(successful_sandboxes)}")
print(f"失败的Sandbox数量: {len(failed_sandboxes)}")

print("\n成功创建的Sandbox列表:")
for index, sandbox_id in successful_sandboxes:
    print(f"Sandbox #{index}: {sandbox_id}")

if failed_sandboxes:
    print("\n创建失败的Sandbox列表:")
    for index, sandbox_id in failed_sandboxes:
        print(f"Sandbox #{index}: {sandbox_id}")

# 计算总进程数
total_processes = len(successful_sandboxes) * 4
print(f"\n成功创建的总计算进程数: {total_processes}")

print("\n所有Sandbox持续计算已启动!")
print("注意: 每个Sandbox中运行4个进程，计算将在后台继续，每个进程的输出保存在各自的日志文件中")