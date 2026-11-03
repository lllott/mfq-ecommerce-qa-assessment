#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从标准输入读取初始库存与 N 条指令，维护：
    on_hand              当前总库存（实际在库数量）
    reserved_dict        每个订单当前占用的预留量
    processed_event_ids  已经处理过的 event_id（用于幂等）

指令格式：
    RESERVE event_id order_id qty    在可用库存足够时增加该订单的预留
    RELEASE event_id order_id qty    释放该订单的预留
    SHIP    event_id order_id qty    发货：同时减少总库存和该订单的预留
    RESTOCK event_id qty             补货：增加总库存

逐条输出 "状态 当前on_hand 当前总预留量"，全部处理完后再按订单号字母序
输出仍然有预留（>0）的订单： "order_id 预留量"；若没有任何未结订单，
则改为输出一行 "OPEN 0"。
"""

import re
import sys
from typing import Dict, List, Optional, Set

# 只接受“纯数字”的正整数写法：拒绝 "1.5"、"abc"、"-3"、"+3"、"1e3" 等
_DIGITS_RE = re.compile(r"^\d+$")

# 每种指令要求的字段个数（含指令名本身）
_ARITY = {
    "RESERVE": 4,
    "RELEASE": 4,
    "SHIP": 4,
    "RESTOCK": 3,
}


def parse_positive_int(token: str) -> Optional[int]:
    """把 token 解析为正整数；不合法（含 0、负数、非数字）时返回 None。"""
    if not _DIGITS_RE.match(token):
        return None
    value = int(token)
    return value if value > 0 else None


def parse_non_negative_int(token: str) -> Optional[int]:
    """把 token 解析为非负整数；不合法时返回 None。"""
    if not _DIGITS_RE.match(token):
        return None
    return int(token)


class Ledger:
    """库存账本：封装状态和一条指令的处理逻辑。"""

    def __init__(self, on_hand: int) -> None:
        self.on_hand: int = on_hand
        self.reserved: Dict[str, int] = {}      # order_id -> 预留量
        self.processed: Set[str] = set()        # 已处理的 event_id
        # 缓存总预留量，避免每次 RESERVE 都 sum() 一遍，整体保持 O(1)
        self.total_reserved: int = 0

    def apply(self, tokens: List[str]) -> str:
        """处理一条已切分的指令，返回状态字符串（OK/REJECTED/DUPLICATE）。

        该方法保证：无论成功、拒绝还是重复，只要 event_id 能取到，
        处理结束后它都会出现在 processed 集合中（幂等键只消费一次）。
        """
        # 取不到 event_id，连幂等都没法记
        if len(tokens) < 2:
            return "REJECTED"
        event_id = tokens[1]

        # 处理过的 event_id 直接判重，状态不变
        if event_id in self.processed:
            return "DUPLICATE"

        # 从这里开始，该 event_id 视为已处理
        # 即使后面发现格式错误 / 数量非法 / 库存不足，也不能再次生效。
        self.processed.add(event_id)

        # 指令名与字段个数不对，一律 REJECTED，状态不变
        command = tokens[0]
        if command not in _ARITY or len(tokens) != _ARITY[command]:
            return "REJECTED"

        # qty 必须是正整数
        qty = parse_positive_int(tokens[-1])
        if qty is None:
            return "REJECTED"

        # RESTOCK 只影响总库存
        if command == "RESTOCK":
            self.on_hand += qty
            return "OK"

        # 其余三种指令都带 order_id
        order_id = tokens[2]

        # RESERVE 的可用量 = on_hand - 总预留量
        if command == "RESERVE":
            available = self.on_hand - self.total_reserved
            if qty > available:
                return "REJECTED"
            self.reserved[order_id] = self.reserved.get(order_id, 0) + qty
            self.total_reserved += qty
            return "OK"

        # RELEASE / SHIP 都受该订单当前预留量限制
        current = self.reserved.get(order_id, 0)   # 不存在即视为 0
        if qty > current:
            return "REJECTED"

        self.reserved[order_id] = current - qty
        self.total_reserved -= qty
        if command == "SHIP":
            # 发货：货真的出库，总库存同时减少
            self.on_hand -= qty
        return "OK"


def main() -> None:
    # 一次性读完标准输入，按行切分（自动兼容 \r\n）
    lines = sys.stdin.read().splitlines()

    # ---- 跳过表头前可能出现的空行，读取 "S N" ----
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines):
        return  # 空输入，无事可做

    header = lines[idx].split()
    idx += 1
    if len(header) != 2:
        # 诊断信息用 ASCII 输出，避免 Windows 控制台编码差异导致乱码
        sys.stderr.write("Error: first line must be '<initial_stock> <command_count>'\n")
        return

    on_hand = parse_non_negative_int(header[0])
    n = parse_non_negative_int(header[1])
    if on_hand is None or n is None:
        sys.stderr.write("Error: initial stock and command count must be non-negative integers\n")
        return

    ledger = Ledger(on_hand)
    out: List[str] = []   # 先收集结果，最后一次性输出，避免频繁写 stdout

    # ---- 逐条处理 N 条指令 ----
    for _ in range(n):
        if idx >= len(lines):
            break  # 实际行数不足 N 行时，按已有指令处理完毕即可
        tokens = lines[idx].split()
        idx += 1

        status = ledger.apply(tokens)
        # 每条指令后都输出：[状态] [当前on_hand] [当前总预留量]
        out.append("{} {} {}".format(status, ledger.on_hand, ledger.total_reserved))

    # ---- 收尾：按订单号字母序收集仍有预留（>0）的订单 ----
    open_orders = [
        "{} {}".format(order_id, ledger.reserved[order_id])
        for order_id in sorted(ledger.reserved)
        if ledger.reserved[order_id] > 0
    ]

    if open_orders:
        out.extend(open_orders)
    else:
        # 没有任何未结订单（含 N=0、全部释放/发货完）时，固定输出一行 "OPEN 0"
        out.append("OPEN 0")

    # 此时 out 至少包含 "OPEN 0"，因此正常输入下一定会有输出
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
