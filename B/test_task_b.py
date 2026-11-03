#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行方式：
    py test_task_b.py

如果所有随机测试都通过，最后会输出：
    all ok

如果失败，会输出 [FAIL]、失败的测试编号、输入数据和失败原因。
"""

import itertools
import random
import subprocess
import sys
from pathlib import Path

# 固定随机种子：保证每次运行生成的测试数据完全相同。
# 这样一旦发现失败，可以稳定复现同一组数据。
RANDOM_SEED = 12345

# 随机测试的组数。数字越大，测试越充分，但运行时间也越长。
CASE_COUNT = 1000

# 测试可用的仓库编号池。
# 这里故意混合三种风格，覆盖字母、字母数字和字符串数字编号：
#   - 纯字母：AU、CN、HK
#   - 字母 + 数字：A1、B2
#   - 数字字符串：1、10、16（注意：按字符串比较，不是按数值比较）
ID_POOL = [
    "AU", "CN", "HK", "JP", "KR", "SG", "US", "UK", "DE", "FR",
    "A1", "B2", "1", "2", "10", "16",
]

# 被测程序的位置：与本测试文件放在同一个目录下。
SOLUTION_PATH = Path(__file__).resolve().parent / "task_b.py"


def brute_force(warehouses, target_qty):
    """
    用暴力枚举求标准答案。

    参数：
        warehouses：
            仓库列表，每个元素是
            (warehouse_id, stock, fixed_cost, unit_cost)
        target_qty：
            需要精确凑齐的商品数量 Q

    返回：
        None：
            没有任何方案。
        (best_key, best_plan)：
            best_key  = (使用的仓库数量, 总成本, 按字典序排列的仓库编号元组)
            best_plan = 与 best_key 对应的每个仓库分配数量元组

    说明：
        这里的 best_key 完全按照题目的优先级排列：
            第一优先级：仓库数量少
            第二优先级：总成本低
            第三优先级：仓库编号序列字典序小
        因此直接用 Python 的元组比较即可。
    """
    # 每个仓库允许分配的数量是 0 到 min(库存, Q)。
    # 例如库存 5、Q 也是 5，就枚举 0、1、2、3、4、5 件。
    ranges = [
        range(0, min(stock, target_qty) + 1)
        for _, stock, _, _ in warehouses
    ]

    best_key = None
    best_plan = None

    # itertools.product 会做笛卡尔积，枚举每个仓库分配数量的所有组合。
    # 例如两个仓库的可选数量分别是 [0,1] 和 [0,1]，
    # 就会得到 (0,0)、(0,1)、(1,0)、(1,1)。
    for plan in itertools.product(*ranges):
        # 总发货量必须精确等于 Q，否则不是合法方案。
        if sum(plan) != target_qty:
            continue

        # 分配数量大于 0 的仓库，才是真正被使用的仓库。
        used_indexes = [
            i for i, qty in enumerate(plan)
            if qty > 0
        ]

        used_count = len(used_indexes)

        # 总成本 = 固定成本之和 + 每件商品的成本之和。
        total_cost = sum(
            warehouses[i][2] + plan[i] * warehouses[i][3]
            for i in used_indexes
        )

        # 题目第三优先级比较的是按 warehouse_id 升序排列的序列。
        # warehouses 在生成时已经按编号排好序，所以这里直接取即可。
        used_ids = tuple(
            warehouses[i][0]
            for i in used_indexes
        )

        # 这个元组就是题目要求的排序关键字。
        key = (used_count, total_cost, used_ids)

        if best_key is None or key < best_key:
            best_key = key
            best_plan = plan

    if best_key is None:
        return None

    return best_key, best_plan


def make_random_case():
    """
    随机生成一组小规模测试数据。

    返回：
        (warehouses, target_qty)

    数据范围：
        仓库数：0～6
        仓库编号：从 ID_POOL 中选不重复的字符串
        库存：0～4
        固定成本：0～10
        单件成本：0～10
        需要发货数量 Q：0～9
    """
    warehouse_count = random.randint(0, 6)

    # 从混合编号池中随机抽取，并保留为字符串。
    # 这样一次随机测试就能同时覆盖字母编号和数字字符串编号。
    warehouse_ids = random.sample(ID_POOL, warehouse_count)
    warehouse_ids.sort()  # 按字符串字典序排序

    warehouses = []
    for warehouse_id in warehouse_ids:
        stock = random.randint(0, 4)
        fixed_cost = random.randint(0, 10)
        unit_cost = random.randint(0, 10)
        warehouses.append(
            (warehouse_id, stock, fixed_cost, unit_cost)
        )

    target_qty = random.randint(0, 9)
    return warehouses, target_qty


def build_input_text(warehouses, target_qty):
    """
    把测试数据拼成 task_b.py 要求的输入格式。

    例如：
        3 5
        1 5 10 2
        2 3 100 1
        3 4 50 1
    """
    lines = [f"{len(warehouses)} {target_qty}"]
    for warehouse_id, stock, fixed_cost, unit_cost in warehouses:
        lines.append(
            f"{warehouse_id} {stock} {fixed_cost} {unit_cost}"
        )
    return "\n".join(lines) + "\n"


def run_solution(input_text):
    """
    启动一个新的 Python 进程运行 task_b.py，
    把 input_text 作为标准输入传进去，并捕获输出。

    使用子进程而不是直接 import，是为了测试程序真实的
    “标准输入 -> 标准输出”行为。
    """
    return subprocess.run(
        [sys.executable, str(SOLUTION_PATH)],
        input=input_text,
        text=True,
        capture_output=True,
    )


def report_failure(case_number, input_text, reason, stdout="", stderr=""):
    """
    统一打印失败信息，然后结束测试。

    打印输入数据是为了方便复现：
    把 input_text 保存成文件，再运行 task_b.py 就能看到同样的问题。
    """
    print(f"[FAIL] 第 {case_number} 组随机测试")
    print(f"原因：{reason}")
    print("输入数据：")
    print(input_text)

    if stdout:
        print("程序输出：")
        print(stdout)

    if stderr:
        print("程序错误输出：")
        print(stderr)

    sys.exit(1)


def check_fixed_case(name, warehouses, target_qty, expected_lines):
    """
    跑一条写死的用例，并断言输出与期望逐行相同。

    随机对拍负责覆盖面，固定用例负责把题目点名的几种边界
    （无解 / 零库存仓库 / 成本并列 / 大数量）变成可读、可复现的回归。
    """
    input_text = build_input_text(warehouses, target_qty)
    result = run_solution(input_text)

    if result.returncode != 0:
        report_failure(name, input_text, "task_b.py 运行崩溃",
                       stdout=result.stdout, stderr=result.stderr)

    lines = result.stdout.strip().splitlines()
    if lines != expected_lines:
        report_failure(
            name,
            input_text,
            f"输出与期望不一致：期望 {expected_lines}，实际 {lines}",
            stdout=result.stdout,
        )


def run_fixed_cases():
    """题目点名的边界场景，逐条给出可读用例。"""
    # 1) 总库存不足：直接 -1。
    check_fixed_case(
        "无解（总库存不足）",
        [("A", 2, 1, 1), ("B", 3, 1, 1), ("C", 1, 1, 1)],
        10,
        ["-1"],
    )

    # 2) 零库存仓库永远不会被选中。
    check_fixed_case(
        "零库存仓库被忽略",
        [("A", 0, 0, 0), ("B", 3, 0, 0)],
        3,
        ["1 0", "B 3"],
    )

    # 3) 成本完全并列时，取 warehouse_id 字典序更小的那个。
    check_fixed_case(
        "成本并列按 ID 字典序",
        [("A", 5, 0, 1), ("B", 5, 0, 1)],
        2,
        ["1 2", "A 2"],
    )

    # 4) 仓库编号按字符串而不是按数值比较："10" < "2"。
    check_fixed_case(
        "编号按字符串字典序",
        [("10", 1, 0, 0), ("2", 1, 0, 0), ("9", 1, 0, 0)],
        1,
        ["1 0", "10 1"],
    )

    # 5) 上限规模：Q = 2000 时，单价更低的仓库胜出。
    check_fixed_case(
        "大数量（Q = 2000）",
        [("A", 2000, 5, 2), ("B", 2000, 7, 1)],
        2000,
        ["1 2007", "B 2000"],
    )

    # 6) 大数量 + 必须用两个仓库，验证成本累加。
    check_fixed_case(
        "大数量（需要两个仓库）",
        [("A", 1000, 5, 2), ("B", 1000, 7, 1)],
        2000,
        ["2 3012", "A 1000", "B 1000"],
    )

    # 7) 仓库数取到上限 W = 30：完全并列时只用一个仓库，且取字典序最小的编号。
    check_fixed_case(
        "W = 30 的并列最优",
        [(f"W{i:02d}", 2000, 1, 1) for i in range(30)],
        2000,
        ["1 2001", "W00 2000"],
    )


def main():
    """
    先跑固定边界用例，再生成多组随机数据与暴力法对比。
    """
    run_fixed_cases()
    random.seed(RANDOM_SEED)

    for case_number in range(1, CASE_COUNT + 1):
        warehouses, target_qty = make_random_case()

        total_stock = sum(
            stock for _, stock, _, _ in warehouses
        )

        # 总库存不足时，标准答案就是“无解”。
        # 否则调用暴力枚举，得到标准答案。
        expected = (
            brute_force(warehouses, target_qty)
            if total_stock >= target_qty
            else None
        )

        input_text = build_input_text(warehouses, target_qty)
        result = run_solution(input_text)

        # 返回码不是 0，说明 task_b.py 运行时报错了。
        if result.returncode != 0:
            report_failure(
                case_number,
                input_text,
                "task_b.py 运行崩溃",
                stdout=result.stdout,
                stderr=result.stderr,
            )

        # 按行切分程序输出。
        lines = result.stdout.strip().splitlines()

        # ---------------- 情况 1：标准答案是无解 ----------------
        if expected is None:
            if lines != ["-1"]:
                report_failure(
                    case_number,
                    input_text,
                    "标准答案是无解，应该输出 -1",
                    stdout=result.stdout,
                )
            continue

        expected_key, _expected_plan = expected
        expected_count, expected_cost, expected_ids = expected_key

        # ---------------- 情况 2：Q = 0 ----------------
        # 不选仓库、成本为 0，这是正确答案。
        if target_qty == 0:
            if lines != ["0 0"]:
                report_failure(
                    case_number,
                    input_text,
                    "Q = 0 时应该输出 0 0",
                    stdout=result.stdout,
                )
            continue

        # ---------------- 情况 3：有解 ----------------
        # 如果程序却输出 -1，说明它漏掉了可行方案。
        if not lines or lines[0].split()[0] == "-1":
            report_failure(
                case_number,
                input_text,
                "标准答案有解，但程序输出了 -1",
                stdout=result.stdout,
            )

        # 第一行必须是：[仓库数量] [总成本]
        first_line = lines[0].split()
        if len(first_line) != 2:
            report_failure(
                case_number,
                input_text,
                "第一行格式错误，应该是：仓库数量 总成本",
                stdout=result.stdout,
            )

        actual_count = int(first_line[0])
        actual_cost = int(first_line[1])

        if actual_count != expected_count:
            report_failure(
                case_number,
                input_text,
                f"最少仓库数量错误：期望 {expected_count}，实际 {actual_count}",
                stdout=result.stdout,
            )

        if actual_cost != expected_cost:
            report_failure(
                case_number,
                input_text,
                f"最低成本错误：期望 {expected_cost}，实际 {actual_cost}",
                stdout=result.stdout,
            )

        # 后面的每一行应该是：[warehouse_id] [分配数量]
        allocations = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) != 2:
                report_failure(
                    case_number,
                    input_text,
                    "仓库分配行格式错误，应该是：warehouse_id 数量",
                    stdout=result.stdout,
                )

            warehouse_id = parts[0]             # 编号是字符串
            quantity = int(parts[1])            # 数量是整数
            allocations.append((warehouse_id, quantity))

        # 检查输出是否按 warehouse_id 字符串升序排列。
        if allocations != sorted(allocations):
            report_failure(
                case_number,
                input_text,
                "输出没有按 warehouse_id 升序排列",
                stdout=result.stdout,
            )

        # 检查实际选中的仓库编号是否就是暴力法得到的最优集合。
        # 这一项可以检查第三优先级：成本和数量相同时的字典序。
        actual_ids = tuple(
            warehouse_id
            for warehouse_id, _ in allocations
        )

        if actual_ids != expected_ids:
            report_failure(
                case_number,
                input_text,
                f"仓库编号序列错误：期望 {expected_ids}，实际 {actual_ids}",
                stdout=result.stdout,
            )

        # 第一行写的仓库数量，必须和实际输出的仓库行数一致。
        if actual_count != len(allocations):
            report_failure(
                case_number,
                input_text,
                "第一行的仓库数量与实际输出的仓库行数不一致",
                stdout=result.stdout,
            )

        # 所有仓库的发货数量加起来必须刚好等于 Q。
        if sum(quantity for _, quantity in allocations) != target_qty:
            report_failure(
                case_number,
                input_text,
                "所有仓库的分配数量之和没有精确等于 Q",
                stdout=result.stdout,
            )

        # 建立“仓库编号 -> 仓库信息”的映射，方便检查库存和成本。
        warehouse_info = {
            warehouse_id: (stock, fixed_cost, unit_cost)
            for warehouse_id, stock, fixed_cost, unit_cost in warehouses
        }

        # 检查每个仓库的分配数量是否在 1 到库存之间。
        for warehouse_id, quantity in allocations:
            if warehouse_id not in warehouse_info:
                report_failure(
                    case_number,
                    input_text,
                    f"输出了不存在的仓库编号：{warehouse_id}",
                    stdout=result.stdout,
                )

            stock = warehouse_info[warehouse_id][0]
            if not (1 <= quantity <= stock):
                report_failure(
                    case_number,
                    input_text,
                    f"仓库 {warehouse_id} 的分配数量 {quantity} 超出 1～{stock}",
                    stdout=result.stdout,
                )

        # 根据程序输出的分配方案重新计算总成本，
        # 防止程序“第一行成本写对了，但分配方案不是同一个成本”。
        recalculated_cost = sum(
            warehouse_info[warehouse_id][1]
            + quantity * warehouse_info[warehouse_id][2]
            for warehouse_id, quantity in allocations
        )

        if recalculated_cost != expected_cost:
            report_failure(
                case_number,
                input_text,
                f"按输出方案重算成本为 {recalculated_cost}，"
                f"但标准答案是 {expected_cost}",
                stdout=result.stdout,
            )

    # 能走到这里，说明所有组都通过了。
    print("all ok")


if __name__ == "__main__":
    main()
