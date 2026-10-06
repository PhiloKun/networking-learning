#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""802.11 各代标准对照表，并计算理论速率中有多少是协议开销。

运行: python3 wifi_standard_table.py
"""
import sys

sys.dont_write_bytecode = True

# 字段: 代号, 发布年, 频段, 最大信道宽, 最大空间流, 最高调制, 理论峰值 Mbps
STANDARDS = [
    ("802.11 (FHSS/DSSS)", 1997, "2.4G", "20MHz", 1, "DBPSK/DQPSK", 2.0),
    ("802.11b", 1999, "2.4G", "20MHz", 1, "CCK", 11.0),
    ("802.11a", 1999, "5G", "20MHz", 1, "64-QAM OFDM", 54.0),
    ("802.11g", 2003, "2.4G", "20MHz", 1, "64-QAM OFDM", 54.0),
    ("802.11n (Wi-Fi 4)", 2009, "2.4G/5G", "40MHz", 4, "64-QAM MIMO", 600.0),
    ("802.11ac (Wi-Fi 5)", 2013, "5G", "160MHz", 8, "256-QAM MU-MIMO", 6933.0),
    ("802.11ax (Wi-Fi 6)", 2019, "2.4G/5G/6G", "160MHz", 8, "1024-QAM OFDMA", 9607.8),
    ("802.11be (Wi-Fi 7)", 2024, "2.4G/5G/6G", "320MHz", 16, "4096-QAM MLO", 46120.0),
]

# 实测吞吐约占理论峰值的比例（干净信道、单客户端、近距离的典型值）
REAL_RATIO = {
    "802.11 (FHSS/DSSS)": 0.50,
    "802.11b": 0.55,
    "802.11a": 0.50,
    "802.11g": 0.50,
    "802.11n (Wi-Fi 4)": 0.55,
    "802.11ac (Wi-Fi 5)": 0.55,
    "802.11ax (Wi-Fi 6)": 0.60,
    "802.11be (Wi-Fi 7)": 0.60,
}

# 2.4G 不重叠信道：1/6/11 共 3 个；5G 中国可用信道；6G 新增
CHANNELS = [
    ("2.4GHz", "1~13", 5, "1/6/11 不重叠，共 3 个", "仅 3 个 20MHz 不重叠信道"),
    ("5GHz", "36~165", 13, "无重叠（UNII-1/2A/2C/3）", "中国开放 13 个 20MHz"),
    ("6GHz", "1~233", 59, "无重叠", "Wi-Fi 6E/7 新增，20MHz 共 59 个"),
]


def fmt_mbps(v: float, width: float) -> str:
    return f"{v:>{width}.1f}"


def main() -> int:
    print("=" * 92)
    print("802.11 各代标准对照（理论峰值均为「单频段单信道」条件下的协议上限）")
    print("=" * 92)
    print("标准                 发布  频段        信道宽  空间流  最高调制          理论峰值")
    print("-" * 92)
    for name, year, band, chw, ss, mod, rate in STANDARDS:
        print(f"{name:<20} {year}  {band:<10} {chw:<7} {ss:^6}  {mod:<17} "
              f"{fmt_mbps(rate, 9)} Mbps")
    print("-" * 92)
    print()
    print("理论峰值 vs 实测吞吐（差值即 MAC/PHY 协议开销）")
    print("-" * 92)
    print("标准                 理论峰值(Mbps)  实测(Mbps)  实测占比  开销占比")
    print("-" * 92)
    for name, _y, _b, _c, _s, _m, rate in STANDARDS:
        real = rate * REAL_RATIO[name]
        print(f"{name:<20} {fmt_mbps(rate, 13)}  {fmt_mbps(real, 10)}  "
              f"{REAL_RATIO[name] * 100:>6.0f}%   {(1 - REAL_RATIO[name]) * 100:>6.0f}%")
    print("-" * 92)
    print()
    print("不重叠信道数（同频段内可同时组网不相干扰）")
    print("-" * 92)
    print("频段    信道号范围   20MHz信道数   不重叠情况                  说明")
    print("-" * 92)
    for band, rng, cnt, nonover, note in CHANNELS:
        print(f"{band:<7} {rng:<12} {cnt:^11}  {nonover:<26} {note}")
    print("-" * 92)
    print()
    print(">>> 结论：标称「AX3000」是 2.4G(574Mbps) + 5G(2402Mbps) 双频相加的营销数字，")
    print("          单客户端任一时刻只能用一个频段，实际可跑约 1.4Gbps。")
    print(">>> 结论：理论峰值里约 40~50% 是前导、PLCP 头、IFS、ACK、退避开销，无法消除。")
    print(">>> 结论：2.4G 只有 3 个不重叠 20MHz 信道，「信道 1/6/11」是唯一可用的密集部署方案。")
    print()
    print("小结")
    print("  1. 速率提升靠三件事：更宽信道（20→320MHz）、更多空间流（1→16）、更高阶调制（→4096-QAM）。")
    print("  2. 高阶调制只对强信号有效，边缘用户会回落到低阶调制，所以「峰值速率」不等于覆盖速率。")
    print("  3. 规划容量时要按「实测 ≈ 理论 × 0.6」估算，并按不重叠信道数而非总信道数规划。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
