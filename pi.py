import math
from decimal import Decimal, getcontext
import time

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

print("开始持续计算π值...")
while current_digits <= max_digits:
    start_time = time.time()
    print(f"\\n计算π到{current_digits}位...")

    try:
        pi_value = calculate_pi(current_digits)
        end_time = time.time()

        print(f"π计算结果 (前50位): {pi_value[:50]}...")
        print(f"总计算位数: {len(pi_value)-1}")
        print(f"计算耗时: {end_time - start_time:.2f} 秒")

        # 每次计算完后增加位数
        current_digits = int(current_digits * 1.5)  # 每次增加50%的位数

    except Exception as e:
        print(f"计算出错: {str(e)}")
        break