#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟 802.11 CSMA/CA 竞争：DIFS + 随机退避 + 冲突后竞争窗口翻倍。

运行: python3 csma_ca_sim.py
"""
import random
import sys

sys.dont_write_bytecode = True
random.seed(42)

# ---- 802.11b DSSS 物理参数（单位：微秒 us）----
SLOT_US = 20          # 时隙
SIFS_US = 10          # 短帧间隔
DIFS_US = 50          # DCF 帧间隔
PLCP_US = 192         # 长前导 + PLCP 头（1 Mbps 发送）
ACK_US = 122          # ACK 帧（11 Mbps 发送）
CW_MIN = 31           # 最小竞争窗口（时隙数 = CW_MIN + 1 = 32）
CW_MAX = 1023         # 最大竞争窗口（时隙数 = 1024）
DATA_BYTES = 1500     # 每帧载荷
RATE_MBPS = 11.0      # 802.11b 最高速率
TRIALS = 20           # 每个站数重复实验次数


def data_airtime_us() -> float:
    """一帧数据占空时间 = 前导与头 + 载荷发送时间。"""
    return PLCP_US + DATA_BYTES * 8 / RATE_MBPS


def run_experiment(n_sta: int, packets_per_sta: int) -> dict:
    """n_sta 个站点各发 packets_per_sta 个包，返回统计结果。"""
    cw = [CW_MIN] * n_sta
    pending = [packets_per_sta] * n_sta
    total_us = 0.0
    collisions = 0
    successes = 0
    airtime_data = data_airtime_us()

    while sum(pending) > 0:
        active = [i for i in range(n_sta) if pending[i] > 0]
        backoff = [random.randint(0, cw[i]) for i in active]
        min_bo = min(backoff)
        winners = [active[k] for k in range(len(active)) if backoff[k] == min_bo]

        idle = DIFS_US + min_bo * SLOT_US
        if len(winners) > 1:                       # 冲突：双方都发完整帧
            total_us += idle + airtime_data
            collisions += 1
            for i in winners:
                cw[i] = min(2 * cw[i] + 1, CW_MAX)  # 二进制指数退避
        else:                                       # 成功：SIFS + ACK
            w = winners[0]
            total_us += idle + airtime_data + SIFS_US + ACK_US
            successes += 1
            pending[w] -= 1
            cw[w] = CW_MIN                          # 成功即复位

    payload_bits = n_sta * packets_per_sta * DATA_BYTES * 8
    return {
        "time_us": total_us,
        "collisions": collisions,
        "successes": successes,
        "coll_rate": collisions / max(1, collisions + successes),
        "throughput": payload_bits / (total_us / 1e6) / 1e6,
    }


def main() -> int:
    airtime = data_airtime_us()
    # 单位换算：1 bit/μs = 1 Mbps，故直接相除即为 Mbps
    ideal = DATA_BYTES * 8 / (DIFS_US + airtime + SIFS_US + ACK_US)
    print("=" * 74)
    print("802.11 CSMA/CA 竞争信道模拟（802.11b DSSS，1 个 BSS，所有站互相可听）")
    print("=" * 74)
    print(f"参数: 时隙 {SLOT_US}us | SIFS {SIFS_US}us | DIFS {DIFS_US}us | "
          f"CWmin {CW_MIN} | CWmax {CW_MAX}")
    print(f"帧: 载荷 {DATA_BYTES} 字节 @ {RATE_MBPS}Mbps，占空 "
          f"{airtime:.1f}us（其中前导+PLCP {PLCP_US}us，占 "
          f"{PLCP_US / airtime * 100:.1f}%）")
    print(f"零冲突理论上限（无退避）：{ideal:.2f} Mbps "
          f"= 物理速率的 {ideal / RATE_MBPS * 100:.1f}%")
    print("-" * 74)
    print("站数 | 总时长(ms) | 冲突次数 | 冲突率 | 有效吞吐(Mbps) | 速率效率")
    print("-" * 74)

    for n in (1, 2, 3, 4, 6, 8, 10, 16):
        agg_t = agg_c = agg_s = 0.0
        for _ in range(TRIALS):
            r = run_experiment(n, 10)
            agg_t += r["time_us"]
            agg_c += r["collisions"]
            agg_s += r["successes"]
        t = agg_t / TRIALS
        c = agg_c / TRIALS
        s = agg_s / TRIALS
        coll_rate = c / max(1.0, c + s)
        thr = n * 10 * DATA_BYTES * 8 / (t / 1e6) / 1e6
        print(f"{n:>3}  | {t / 1000:>9.2f} | {c:>7.1f} | "
              f"{coll_rate * 100:>5.1f}% | {thr:>13.2f} | {thr / RATE_MBPS * 100:>7.1f}%")

    print("-" * 74)
    print(">>> 结论：站数从 1 增到 16，冲突率单调上升、有效吞吐不再是物理速率 11Mbps。")
    print(">>> 结论：帧头开销（前导 192us）无法压缩，即便零冲突也只有约 8.2Mbps 可用。")
    print(">>> 结论：冲突后 CW 翻倍（31→63→127→255→511→1023）是吞吐随站数下降的主因。")
    print()
    print("小结")
    print("  1. CSMA/CA 靠 DIFS + 随机退避把「同时想发」的概率压低，但压不到 0。")
    print("  2. 冲突代价是整帧时长被浪费（无 ACK 确认），站数越多雪崩越明显。")
    print("  3. 二进制指数退避把窗口从 31 指数放大到 1023，牺牲时延换吞吐稳定性。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
