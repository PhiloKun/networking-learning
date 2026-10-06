#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FDM / 同步 TDM / 统计时分复用的信道分配模拟与利用率对比。

运行: python3 multiplexing_demo.py [用户数]
"""
import sys
import random
import unicodedata

sys.dont_write_bytecode = True

random.seed(42)
SEP = "=" * 78
SUB = "-" * 78


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def simulate(demand: list[list[int]], capacity: int) -> dict:
    """demand[frame][user] = 该用户该帧需要的信道单元数（0/1/2）。"""
    frames = len(demand)
    users = len(demand[0])
    total_capacity = capacity * frames

    fdm_served = 0
    tdm_served = 0
    stat_served = 0
    stat_dropped = 0
    fdm_dropped = 0
    stat_detail = []
    for row in demand:
        # FDM / 同步 TDM：每用户每帧固定 1 个单元
        for d in row:
            s = min(d, 1)
            fdm_served += s
            tdm_served += s
            fdm_dropped += max(0, d - 1)
        # 统计 TDM：容量池共享，按需分配
        need = sum(row)
        got = min(need, capacity)
        stat_served += got
        stat_dropped += need - got
        stat_detail.append((need, got))
    return {
        "frames": frames,
        "users": users,
        "capacity": total_capacity,
        "fdm_served": fdm_served,
        "tdm_served": tdm_served,
        "stat_served": stat_served,
        "fdm_dropped": fdm_dropped,
        "stat_dropped": stat_dropped,
        "stat_detail": stat_detail,
    }


def print_matrix(demand: list[list[int]]) -> None:
    users = len(demand[0])
    head = pad("帧号", 8)
    for u in range(users):
        head += pad(f"U{u + 1}", 8, True)
    head += pad("需求合计", 12, True)
    print(head)
    print(SUB)
    for i, row in enumerate(demand):
        line = pad(str(i + 1), 8)
        for d in row:
            line += pad(str(d), 8, True)
        line += pad(str(sum(row)), 12, True)
        print(line)
    print(SUB)


def main() -> None:
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    frames = 12
    capacity = N

    print(SEP)
    print("信道复用方式对比 · FDM / 同步 TDM / 统计时分复用")
    print(SEP)
    print(f"用户数 N = {N}    帧数 = {frames}    每帧可用信道单元 = {capacity}")
    print("每个信道单元代表「一条等效 64 kbit/s 子信道」")
    print()

    print(SUB)
    print("【一】三种复用方式的资源分配规则")
    print(SUB)
    print(pad("方式", 16) + pad("切分维度", 12) + pad("分配策略", 28) + "空闲资源能否被他人用")
    print(SUB)
    rows = [
        ("FDM", "频率", "每用户独占一个频段", "不能，浪费在频段上"),
        ("同步 TDM", "时间", "每用户独占固定时隙", "不能，浪费在时隙上"),
        ("统计 TDM", "时间", "时隙按需动态分配", "能，空闲时隙给有需求的用户"),
    ]
    for name, dim, pol, reuse in rows:
        print(pad(name, 16) + pad(dim, 12) + pad(pol, 28) + reuse)
    print(SUB)
    print()

    print(SUB)
    print("【二】场景 A：恒定需求（每用户每帧恰好需要 1 个单元）")
    print(SUB)
    demand_a = [[1] * N for _ in range(frames)]
    ra = simulate(demand_a, capacity)
    for label, key in [("FDM", "fdm_served"), ("同步 TDM", "tdm_served"), ("统计 TDM", "stat_served")]:
        print(pad(label, 12) + pad(f"利用率 = {ra[key]}/{ra['capacity']}"
                                   f" = {ra[key] / ra['capacity'] * 100:.1f}%", 40))
    print(">>> 需求恒定且正好填满时，三种方式都能达到 100%，区别体现不出来。")
    print()

    print(SUB)
    print("【三】场景 B：突发需求（随机 0/1/2 个单元，seed=42）")
    print(SUB)
    weights = [0.3, 0.4, 0.3]
    demand_b = [[random.choices([0, 1, 2], weights=weights)[0] for _ in range(N)]
                for _ in range(frames)]
    print_matrix(demand_b)
    rb = simulate(demand_b, capacity)
    print()
    print(pad("方式", 14) + pad("实际服务单元数", 16, True) + pad("利用率", 12, True)
          + pad("丢弃/未满足", 14, True))
    print(SUB)
    print(pad("FDM", 14) + pad(str(rb["fdm_served"]), 16, True)
          + pad(f"{rb['fdm_served'] / rb['capacity'] * 100:.1f}%", 12, True)
          + pad(str(rb["fdm_dropped"]), 14, True))
    print(pad("同步 TDM", 14) + pad(str(rb["tdm_served"]), 16, True)
          + pad(f"{rb['tdm_served'] / rb['capacity'] * 100:.1f}%", 12, True)
          + pad(str(rb["fdm_dropped"]), 14, True))
    print(pad("统计 TDM", 14) + pad(str(rb["stat_served"]), 16, True)
          + pad(f"{rb['stat_served'] / rb['capacity'] * 100:.1f}%", 12, True)
          + pad(str(rb["stat_dropped"]), 14, True))
    print(SUB)
    print("逐帧看统计 TDM 如何把空闲容量借出去（需求合计 / 实际服务）：")
    for i, (need, got) in enumerate(rb["stat_detail"]):
        bar = "#" * got
        flag = "  <- 需求超出容量，部分被丢弃" if need > capacity else ""
        print(pad(f"  帧{i + 1:>2}", 8) + pad(f"需求{need} 服务{got}", 18) + bar + flag)
    print()
    gain = (rb["stat_served"] - rb["fdm_served"]) / rb["capacity"] * 100
    print(f">>> 突发场景下，统计 TDM 利用率 {rb['stat_served'] / rb['capacity'] * 100:.1f}%，"
          f"比 FDM/同步 TDM 的 {rb['fdm_served'] / rb['capacity'] * 100:.1f}% 高 {gain:.1f} 个百分点。")
    print("    原因是它能把「某用户空闲的时隙」借给「另一用户突发的需求」。")
    print()

    print(SUB)
    print("【四】场景 C：过载（每用户每帧都需要 2 个单元）")
    print(SUB)
    demand_c = [[2] * N for _ in range(frames)]
    rc = simulate(demand_c, capacity)
    print(f"总需求 = {2 * N * frames} 单元，总容量 = {rc['capacity']} 单元")
    print(pad("方式", 14) + pad("服务", 12, True) + pad("丢弃", 12, True) + pad("利用率", 12, True))
    print(SUB)
    print(pad("FDM", 14) + pad(str(rc["fdm_served"]), 12, True)
          + pad(str(rc["fdm_dropped"]), 12, True)
          + pad(f"{rc['fdm_served'] / rc['capacity'] * 100:.1f}%", 12, True))
    print(pad("同步 TDM", 14) + pad(str(rc["tdm_served"]), 12, True)
          + pad(str(rc["fdm_dropped"]), 12, True)
          + pad(f"{rc['tdm_served'] / rc['capacity'] * 100:.1f}%", 12, True))
    print(pad("统计 TDM", 14) + pad(str(rc["stat_served"]), 12, True)
          + pad(str(rc["stat_dropped"]), 12, True)
          + pad(f"{rc['stat_served'] / rc['capacity'] * 100:.1f}%", 12, True))
    print(SUB)
    print(">>> 统计 TDM 不是「无中生有」：当总需求超过总容量时，照样丢包。")
    print("    它只是把「平均利用率」做高，不能突破信道总容量。")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print("1. 恒定需求下 FDM / 同步 TDM / 统计 TDM 利用率相同，都接近 100%。")
    print(f"2. 突发需求下统计 TDM 利用率 {rb['stat_served'] / rb['capacity'] * 100:.1f}%，"
          f"显著高于固定分配的 {rb['fdm_served'] / rb['capacity'] * 100:.1f}%。")
    print("3. 统计 TDM 的代价是需要缓冲与地址标识（每个时隙要带用户标签），实现更复杂。")
    print("4. 现代分组交换本质就是统计时分复用：链路被所有会话共享，按需占用。")
    print()


if __name__ == "__main__":
    main()
