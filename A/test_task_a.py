# -*- coding: utf-8 -*-
"""task_a.py 的 pytest 测试。

思路：所有用例都以「文本」为单位，通过 subprocess 把文本喂给脚本的
标准输入，再断言脚本的标准输出。这样测试的是真实的可执行行为，
不依赖脚本内部的函数/类名，重构实现也不会让测试失效。

运行方式：
    py -m pytest -q test_task_a.py
    py -m pytest -q test_task_a.py -v
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

# 被测脚本与本测试文件放在同一目录，避免依赖当前工作目录
SCRIPT = Path(__file__).resolve().parent / "task_a.py"


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

def run_ledger(stdin_text: str) -> List[str]:
    """把 stdin_text 作为标准输入运行脚本，返回按行切分后的标准输出。"""
    assert SCRIPT.is_file(), "找不到被测脚本: {}".format(SCRIPT)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    # 正常路径下脚本不应崩溃，也不该往 stderr 写任何东西
    assert proc.returncode == 0, "脚本异常退出: {!r}".format(proc.stderr)
    return proc.stdout.splitlines()


def split_status(lines: List[str], n: int) -> Tuple[List[str], List[str]]:
    """把输出切成前 n 条指令结果 + 末尾的未结订单块。"""
    assert len(lines) >= n, "输出行数不足 {} 行: {!r}".format(n, lines)
    return lines[:n], lines[n:]


# ---------------------------------------------------------------------------
# 1. 正常流程：RESERVE / SHIP / RELEASE / RESTOCK 的库存计算
# ---------------------------------------------------------------------------

def test_normal_flow_all_four_commands():
    """四种指令串起来跑，逐条核对 on_hand 与总预留量。"""
    out = run_ledger(
        "100 6\n"
        "RESERVE e1 o1 30\n"   # 可用 100 -> 预留 30
        "RESTOCK e2 20\n"      # 库存 120，预留不变
        "SHIP e3 o1 10\n"      # 出库 10：库存 110，预留 20
        "RELEASE e4 o1 5\n"    # 释放 5：库存 110，预留 15
        "RESERVE e5 o2 50\n"   # 可用 110-15=95 -> 预留 65
        "RELEASE e6 o1 15\n"   # 释放 15：预留 50，o1 归零
    )
    status, tail = split_status(out, 6)
    assert status == [
        "OK 100 30",
        "OK 120 30",
        "OK 110 20",
        "OK 110 15",
        "OK 110 65",
        "OK 110 50",
    ]
    # o1 已归零不应出现在末尾，只剩 o2
    assert tail == ["o2 50"]


def test_ship_actually_decreases_on_hand():
    """SHIP 必须同时扣 on_hand 和该订单的预留量。"""
    status, tail = split_status(
        run_ledger(
            "40 2\n"
            "RESERVE a o1 15\n"
            "SHIP b o1 15\n"
        ),
        2,
    )
    assert status == ["OK 40 15", "OK 25 0"]
    assert tail == ["OPEN 0"]


# ---------------------------------------------------------------------------
# 2. 幂等性：同一 event_id 第二次必须是 DUPLICATE 且状态不变
# ---------------------------------------------------------------------------

def test_duplicate_reserve_does_not_double_book():
    """重复 RESERVE 只回 DUPLICATE，不会把预留量加两遍。"""
    out = run_ledger(
        "50 3\n"
        "RESERVE e1 o1 20\n"   # 第一次成功
        "RESERVE e1 o1 20\n"   # 同 id -> DUPLICATE
        "RESERVE e2 o1 40\n"   # 可用仅 30，若上一条重复生效这里会够，故必失败
    )
    status, tail = split_status(out, 3)
    assert status == [
        "OK 50 20",
        "DUPLICATE 50 20",
        "REJECTED 50 20",
    ]
    assert tail == ["o1 20"]


def test_duplicate_ship_does_not_ship_twice():
    """重复 SHIP 不能把货扣两次。"""
    status, tail = split_status(
        run_ledger(
            "50 3\n"
            "RESERVE e1 o1 20\n"
            "SHIP e2 o1 10\n"   # 库存 40，预留 10
            "SHIP e2 o1 10\n"   # DUPLICATE，库存仍为 40
        ),
        3,
    )
    assert status == ["OK 50 20", "OK 40 10", "DUPLICATE 40 10"]
    assert tail == ["o1 10"]


def test_duplicate_of_rejected_event_is_duplicate():
    """被拒的 event_id 也算已处理，再发同 id 得到 DUPLICATE 而非再次判定。"""
    status, tail = split_status(
        run_ledger(
            "50 2\n"
            "RESERVE e1 o1 60\n"   # 库存不足 -> REJECTED，但 e1 被消费
            "RESERVE e1 o1 10\n"   # 同 id -> DUPLICATE
        ),
        2,
    )
    assert status == ["REJECTED 50 0", "DUPLICATE 50 0"]
    assert tail == ["OPEN 0"]


def test_duplicate_after_malformed_command():
    """格式错误也占用 event_id，后续同 id 合法指令只能 DUPLICATE。"""
    status, tail = split_status(
        run_ledger(
            "50 2\n"
            "RESERVE e1 o1\n"      # 缺参数 -> REJECTED
            "RESERVE e1 o1 10\n"   # 同 id -> DUPLICATE
        ),
        2,
    )
    assert status == ["REJECTED 50 0", "DUPLICATE 50 0"]
    assert tail == ["OPEN 0"]


# ---------------------------------------------------------------------------
# 3. 非法输入：qty 非正整数 / 格式错误 -> REJECTED 且状态不变
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_qty", ["0", "-5", "abc", "1.5", "+5"])
def test_invalid_qty_rejected_and_state_untouched(bad_qty):
    """qty 为 0、负数、小数、非数字时必须 REJECTED，且不影响后续库存。"""
    out = run_ledger(
        "100 2\n"
        "RESERVE e1 o1 {}\n"
        "RESERVE e2 o1 10\n"   # 探针：若非法指令改了状态，这里的数字就会错
        .format(bad_qty)
    )
    status, tail = split_status(out, 2)
    assert status == ["REJECTED 100 0", "OK 100 10"]
    assert tail == ["o1 10"]


@pytest.mark.parametrize(
    "bad_line",
    [
        "RESERVE e1 o1",          # 缺少 qty
        "RESTOCK e1",             # 缺少 qty
        "RESERVE e1 o1 10 extra", # 多一个字段
        "SHIP e1 o1",             # 缺少 qty
        "RELEASE e1 o1 5 6",      # 多一个字段
        "BOGUS e1 o1 5",          # 未知指令
        "reserve e1 o1 5",        # 指令名大小写不符
        "RESERVE",                # 连 event_id 都没有
        "",                       # 空行
    ],
)
def test_malformed_line_rejected_and_state_untouched(bad_line):
    """格式错误一律 REJECTED，且 on_hand 与预留量保持不变。"""
    out = run_ledger(
        "100 2\n"
        "{}\n"
        "RESTOCK e9 10\n"   # 探针：正常补货后应为 110 / 0
        .format(bad_line)
    )
    status, tail = split_status(out, 2)
    assert status == ["REJECTED 100 0", "OK 110 0"]
    assert tail == ["OPEN 0"]


# ---------------------------------------------------------------------------
# 4. 边界拦截：库存不足 / 释放或发货超过该订单预留量
# ---------------------------------------------------------------------------

def test_reserve_rejected_when_stock_insufficient():
    """可用库存不足时 RESERVE 必须 REJECTED，且不产生任何预留。"""
    status, tail = split_status(
        run_ledger(
            "10 2\n"
            "RESERVE e1 o1 11\n"   # 差 1
            "RESERVE e2 o2 10\n"   # 刚好够
        ),
        2,
    )
    assert status == ["REJECTED 10 0", "OK 10 10"]
    assert tail == ["o2 10"]


def test_available_stock_accounts_for_existing_reservations():
    """可用量 = on_hand - 全部订单预留量之和，而不是看单个订单。"""
    status, tail = split_status(
        run_ledger(
            "10 3\n"
            "RESERVE a o1 6\n"    # 可用 10 -> 成功
            "RESERVE b o2 5\n"    # 可用 4 -> 失败
            "RESERVE c o2 4\n"    # 可用 4 -> 成功
        ),
        3,
    )
    assert status == ["OK 10 6", "REJECTED 10 6", "OK 10 10"]
    assert tail == ["o1 6", "o2 4"]


def test_release_more_than_reserved_is_rejected():
    """释放量超过该订单当前预留量时 REJECTED，状态不变。"""
    status, tail = split_status(
        run_ledger(
            "20 3\n"
            "RESERVE a o1 5\n"
            "RELEASE b o1 6\n"   # 超过 5 -> 拒绝
            "RELEASE c o1 5\n"   # 刚好释放完
        ),
        3,
    )
    assert status == ["OK 20 5", "REJECTED 20 5", "OK 20 0"]
    assert tail == ["OPEN 0"]


def test_release_unknown_order_is_rejected():
    """对没有预留记录的订单做 RELEASE，预留量视为 0，任何正数都超限。"""
    status, tail = split_status(run_ledger("20 1\nRELEASE a ghost 1\n"), 1)
    assert status == ["REJECTED 20 0"]
    assert tail == ["OPEN 0"]


def test_ship_more_than_reserved_is_rejected():
    """发货量超过该订单预留量时 REJECTED，且 on_hand 不能被扣。"""
    status, tail = split_status(
        run_ledger(
            "20 3\n"
            "RESERVE a o1 5\n"
            "SHIP b o1 6\n"   # 超过 5 -> 拒绝，库存保持 20
            "SHIP c o1 5\n"   # 刚好发完
        ),
        3,
    )
    assert status == ["OK 20 5", "REJECTED 20 5", "OK 15 0"]
    assert tail == ["OPEN 0"]


def test_ship_unknown_order_is_rejected():
    """对没有预留的订单发货必须拒绝，不能凭空扣库存。"""
    status, tail = split_status(run_ledger("20 1\nSHIP a ghost 1\n"), 1)
    assert status == ["REJECTED 20 0"]
    assert tail == ["OPEN 0"]


# ---------------------------------------------------------------------------
# 5. 末尾输出格式：未结订单字母序、无未结订单时 OPEN 0
# ---------------------------------------------------------------------------

def test_no_open_orders_prints_open_zero():
    """全部发货完、没有未结订单时，末尾必须输出一行 OPEN 0。"""
    status, tail = split_status(
        run_ledger(
            "10 2\n"
            "RESERVE a o1 10\n"
            "SHIP b o1 10\n"
        ),
        2,
    )
    assert status == ["OK 10 10", "OK 0 0"]
    assert tail == ["OPEN 0"]


def test_zero_commands_prints_open_zero():
    """N=0、一条指令都没有时，也要输出 OPEN 0。"""
    assert run_ledger("10 0\n") == ["OPEN 0"]


def test_open_orders_sorted_alphabetically():
    """未结订单按 order_id 字母序输出，与创建顺序无关。"""
    out = run_ledger(
        "30 3\n"
        "RESERVE e1 zeta 10\n"
        "RESERVE e2 alpha 5\n"
        "RESERVE e3 mike 7\n"
    )
    _, tail = split_status(out, 3)
    assert tail == ["alpha 5", "mike 7", "zeta 10"]


def test_open_zero_not_printed_when_orders_remain():
    """有未结订单时不能画蛇添足输出 OPEN 0。"""
    out = run_ledger("10 1\nRESERVE e1 o1 5\n")
    assert out == ["OK 10 5", "o1 5"]
    assert "OPEN 0" not in out


def test_final_block_only_lists_positive_reservations():
    """预留量归零的订单不出现在末尾清单里。"""
    out = run_ledger(
        "30 4\n"
        "RESERVE a o1 10\n"
        "RESERVE b o2 10\n"
        "RELEASE c o1 10\n"
        "SHIP d o2 10\n"
    )
    _, tail = split_status(out, 4)
    assert tail == ["OPEN 0"]


# ---------------------------------------------------------------------------
# 6. 综合 / 边界补充
# ---------------------------------------------------------------------------

def test_matches_documented_example():
    """之前手工验证过的 10 6 例子，作为端到端回归。"""
    out = run_ledger(
        "10 6\n"
        "RESERVE e1 A 4\n"
        "RESERVE e2 B 7\n"
        "SHIP e3 A 2\n"
        "RELEASE e4 B 3\n"
        "RESTOCK e5 5\n"
        "RESERVE e1 A 1\n"
    )
    assert out == [
        "OK 10 4",
        "REJECTED 10 4",
        "OK 8 2",
        "REJECTED 8 2",
        "OK 13 2",
        "DUPLICATE 13 2",
        "A 2",
    ]


def test_extra_whitespace_and_tabs_are_tolerated():
    """字段之间多空格或 Tab 仍应正常解析。"""
    status, tail = split_status(
        run_ledger(
            "10 2\n"
            "RESERVE   e1\t\to1\t5\n"
            "RESTOCK e2\t3\n"
        ),
        2,
    )
    assert status == ["OK 10 5", "OK 13 5"]
    assert tail == ["o1 5"]


def test_every_status_line_has_three_fields():
    """所有指令结果行都必须是 “状态 on_hand 总预留量” 三段式。"""
    out = run_ledger(
        "5 5\n"
        "RESERVE a o1 3\n"
        "RESERVE b o2 3\n"
        "BOGUS c\n"
        "SHIP d o1 3\n"
        "RESTOCK e 2\n"
    )
    status_lines, _ = split_status(out, 5)
    for line in status_lines:
        parts = line.split()
        assert len(parts) == 3, line
        assert parts[0] in {"OK", "REJECTED", "DUPLICATE"}
        assert parts[1].isdigit() and parts[2].isdigit()
