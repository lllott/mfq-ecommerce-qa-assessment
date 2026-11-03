#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task B
输入：
    第一行 W Q
    接下来 W 行：warehouse_id stock fixed_cost unit_cost

    warehouse_id 可以是字母、数字或字母数字组合，例如 AU、CN、HK。
    程序把 warehouse_id 当作字符串处理，并按字符串字典序比较。

目标（按优先级）：
    1. 恰好分配 Q 件商品；
    2. 使用的仓库数量最少；
    3. 总成本最低：
           总成本 = 所选仓库 fixed_cost 之和
                  + 各仓库分配数量 * unit_cost 之和
    4. 若仓库数和成本都相同，按 warehouse_id 升序组成的序列字典序最小。

算法：
    按 warehouse_id 升序处理仓库，做二维 DP：
        dp[k][q] = 使用前若干个仓库、恰好选了 k 个仓库、
                   共分配 q 件商品时的最小总成本。
    同时用 dp_mask[k][q] 记录在最小成本下的“最优仓库集合”：
        把排好序的仓库下标映射成二进制位，编号越小，二进制位越高。
        在仓库数相同的两个集合中，二进制掩码越大，其 warehouse_id
        升序序列的字典序越小，因此相同成本时保留更大的掩码即可。

    单次“选/不选当前仓库”的转移原本是：
        dp_new[k][q] = min(
            dp_old[k][q],                              # 不选当前仓库
            min_{1 <= x <= stock} dp_old[k-1][q-x]
                                  + fixed + x * unit   # 选当前仓库，分配 x 件
        )
    其中对 x 的枚举可以用单调队列优化：
        min_x dp_old[k-1][q-x] + fixed + q*unit - (q-x)*unit
      = fixed + q*unit + min_{y=q-stock..q-1} (dp_old[k-1][y] - y*unit)
    因此主 DP 的复杂度为 O(W^2 * Q)，W <= 30, Q <= 2000，完全足够。

    找到最优仓库集合后，再在“必须选择这些仓库”的前提下，
    重新做一次一维背包，恢复每个仓库的具体分配数量。
"""

import sys
from collections import deque

INF = 10 ** 30  # 远大于任何可能成本；Python 整数不会溢出


def solve() -> None:
    # warehouse_id 不再强制转成整数，而是保留为字符串。
    # 这样 AU / CN / HK / A01 之类的编号都可以直接使用。
    data = sys.stdin.buffer.read().split()
    if not data:
        return

    W = int(data[0])
    Q = int(data[1])

    warehouses = []
    pos = 2
    for _ in range(W):
        wid = data[pos].decode("utf-8")   # 仓库编号：字符串
        stock = int(data[pos + 1])        # 库存：整数
        fixed = int(data[pos + 2])        # 固定成本：整数
        unit = int(data[pos + 3])         # 单件成本：整数
        warehouses.append((wid, stock, fixed, unit))
        pos += 4

    # 按 warehouse_id 升序处理，便于实现“字典序最小”的并列规则，
    # 也方便最终按题目要求输出。
    warehouses.sort(key=lambda x: x[0])

    # Q = 0 的特殊情况：不选仓库、成本为 0，且这是最少仓库数。
    if Q == 0:
        print("0 0")
        return

    # 总库存不足，直接无解。
    if sum(stock for _, stock, _, _ in warehouses) < Q:
        print(-1)
        return

    # 库存为 0 的仓库永远不可能被选中，提前去掉可以缩小状态空间。
    # 这不会影响 warehouse_id 的相对顺序和字典序规则。
    active = [w for w in warehouses if w[1] > 0]
    n = len(active)

    if n == 0:
        print(-1)
        return

    # dp_cost[k][q]：选恰好 k 个仓库、凑出 q 件的最小总成本。
    # dp_mask[k][q]：在上述最小成本下，最优仓库集合对应的掩码。
    dp_cost = [[INF] * (Q + 1) for _ in range(n + 1)]
    dp_mask = [[0] * (Q + 1) for _ in range(n + 1)]
    dp_cost[0][0] = 0

    # 逐个加入仓库。k 必须倒序，保证本层使用的 dp[k-1] 还是“没有当前仓库”的旧状态。
    for i, (wid, stock, fixed, unit) in enumerate(active):
        # 排在越前面的 warehouse_id 越重要，所以给它更高的二进制位。
        # 这样在仓库数相同时，掩码越大 <=> ID 序列字典序越小。
        bit = 1 << (n - 1 - i)
        cap = min(stock, Q)  # 分配数量不可能超过 Q

        # 使用 k 个仓库时，每个被选仓库至少分 1 件，因此 k <= Q。
        upper_k = min(i + 1, Q, n)

        for k in range(upper_k, 0, -1):
            prev_cost = dp_cost[k - 1]  # 旧状态，尚未考虑当前仓库
            prev_mask = dp_mask[k - 1]
            cur_cost = dp_cost[k]
            cur_mask = dp_mask[k]

            # 单调队列存储 (prev_cost[y] - y*unit, -prev_mask[y], y)。
            # 关键字越小越优：成本小优先；成本相同时 -mask 小，即 mask 大优先。
            # 相等时保留后加入的 y，因为它更晚过期，对后续 q 更有利。
            dq = deque()

            for q in range(1, Q + 1):
                # 新候选 y = q - 1，对应给当前仓库分配 x = 1 件。
                y = q - 1
                if prev_cost[y] < INF:
                    base_cost = prev_cost[y] - y * unit
                    key_cost = base_cost
                    key_mask = -prev_mask[y]

                    while dq and (dq[-1][0], dq[-1][1]) >= (key_cost, key_mask):
                        dq.pop()
                    dq.append((key_cost, key_mask, y))

                # 当前仓库最多分配 cap 件，因此 y 必须 >= q - cap。
                lower_y = q - cap
                while dq and dq[0][2] < lower_y:
                    dq.popleft()

                if not dq:
                    continue

                base_cost, neg_mask, _ = dq[0]
                candidate_cost = base_cost + fixed + q * unit
                candidate_mask = (-neg_mask) | bit

                old_cost = cur_cost[q]
                if (candidate_cost < old_cost or
                        (candidate_cost == old_cost and candidate_mask > cur_mask[q])):
                    cur_cost[q] = candidate_cost
                    cur_mask[q] = candidate_mask

    # 优先 1：仓库数量最少。从小到大找第一个能凑出 Q 件的 k。
    chosen_k = -1
    for k in range(1, n + 1):
        if dp_cost[k][Q] < INF:
            chosen_k = k
            break

    if chosen_k == -1:
        print(-1)
        return

    best_cost = dp_cost[chosen_k][Q]
    best_mask = dp_mask[chosen_k][Q]

    # 还原被选中的仓库（active 已按 warehouse_id 升序）。
    selected = [
        active[i]
        for i in range(n)
        if best_mask & (1 << (n - 1 - i))
    ]

    # ------------------------------------------------------------------
    # 恢复具体分配数量。
    #
    # 已经确定的仓库集合必须全部使用，并且每个仓库至少分 1 件。
    # 先给每个仓库分 1 件，剩余 R = Q - k 件按 unit_cost 做一维背包。
    # 因为只需恢复一条最优路径，这里保存每一层的前缀 DP 数组，
    # 再从后往前检查即可；复杂度 O(k * R)，非常小。
    # ------------------------------------------------------------------
    k = chosen_k
    remaining = Q - k

    # layers[t][q]：只考虑前 t 个被选仓库、额外分配 q 件时的最小额外成本。
    layers = [[0] + [INF] * remaining]

    for _, stock, _, unit in selected:
        prev = layers[-1]
        cur = [INF] * (remaining + 1)
        cur[0] = 0  # 额外分配 0 件，成本为 0

        cap_extra = min(stock - 1, remaining)  # 每个仓库已预分 1 件
        dq = deque()  # 存 (prev[y] - y*unit, y)

        for q in range(remaining + 1):
            if prev[q] < INF:
                base = prev[q] - q * unit
                while dq and dq[-1][0] >= base:
                    dq.pop()
                dq.append((base, q))

            lower_y = q - cap_extra
            while dq and dq[0][1] < lower_y:
                dq.popleft()

            if dq:
                cur[q] = dq[0][0] + q * unit

        layers.append(cur)

    # 从目标 remaining 倒推，找到每个仓库分到的额外数量。
    extra_qty = [0] * k
    q = remaining
    for idx in range(k - 1, -1, -1):
        _, stock, _, unit = selected[idx]
        prev = layers[idx]
        target = layers[idx + 1][q]
        cap_extra = min(stock - 1, q)
        chosen_extra = 0

        for r in range(cap_extra + 1):
            if prev[q - r] + r * unit == target:
                chosen_extra = r
                break

        extra_qty[idx] = chosen_extra
        q -= chosen_extra

    quantities = [1 + extra_qty[i] for i in range(k)]

    # 输出：第一行仓库数量与总成本，随后按 warehouse_id 升序输出。
    out = [f"{chosen_k} {best_cost}"]
    for (wid, _, _, _), qty in zip(selected, quantities):
        out.append(f"{wid} {qty}")
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    solve()
