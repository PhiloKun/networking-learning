#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 T1~T4 计算 NTP 偏移 θ 与延迟 δ，并演示多源选源（Marzullo 交集思路）。

运行: python3 ntp_offset.py
"""
import sys

sys.dont_write_bytecode = True

# 每个源：(名称, stratum, T1, T2, T3, T4)，时间单位毫秒
SAMPLES = [
    ("ntp1.example.net", 2, 1000.0, 1060.0, 1065.0, 1125.0),
    ("ntp2.example.net", 2, 1000.0, 1080.0, 1085.0, 1165.0),
    ("ntp3.example.net", 3, 1000.0, 1030.0, 1032.0, 1098.0),
    ("ntp4.example.net", 3, 1000.0, 1090.0, 1094.0, 1150.0),
]

STRATUM = {
    0: "原子钟 / GPS 等参考源（未联网的原始时钟）",
    1: "直接与 stratum 0 同步的主服务器",
    2: "与 stratum 1 同步（常见公网 NTP 服务器）",
    3: "与 stratum 2 同步",
    15: "合法的最底层级",
    16: "未同步（不可用，客户端应忽略）",
}


def compute(t1: float, t2: float, t3: float, t4: float) -> tuple[float, float]:
    """返回 (偏移 θ, 往返延迟 δ)。"""
    theta = ((t2 - t1) + (t3 - t4)) / 2.0
    delta = (t4 - t1) - (t3 - t2)
    return theta, delta


def marzullo(intervals: list[tuple[float, float]]) -> tuple[float, float, int]:
    """找被最多区间共同覆盖的连续区间。返回 (lo, hi, 覆盖数)。"""
    pts = sorted({p for iv in intervals for p in iv})
    best_count = 0
    segments: list[list[float]] = []
    for i in range(len(pts) - 1):
        mid = (pts[i] + pts[i + 1]) / 2.0
        c = sum(1 for lo, hi in intervals if lo <= mid <= hi)
        if c > best_count:
            best_count = c
            segments = [[pts[i], pts[i + 1]]]
        elif c == best_count and segments:
            if abs(segments[-1][1] - pts[i]) < 1e-9:      # 与前一段连续则合并
                segments[-1][1] = pts[i + 1]
            else:
                segments.append([pts[i], pts[i + 1]])
    if not segments:
        return 0.0, 0.0, 0
    return segments[0][0], segments[-1][1], best_count


def main() -> None:
    print("=" * 74)
    print("NTP 偏移与延迟计算 + 多源选源（Marzullo 交集）")
    print("=" * 74)

    print("\n[1] 四时间戳定义")
    print("    T1 = 客户端发出请求的本地时间")
    print("    T2 = 服务器收到请求的服务器时间")
    print("    T3 = 服务器发出响应的服务器时间")
    print("    T4 = 客户端收到响应的本地时间")
    print("    公式：偏移 θ = ((T2 - T1) + (T3 - T4)) / 2")
    print("          延迟 δ = (T4 - T1) - (T3 - T2)")
    print("    其中 δ 也叫往返延迟（Round-Trip Delay），θ 为正表示本地时钟慢于服务器")

    print("\n[2] 逐源计算（单位：毫秒）")
    print("    %-18s %-6s %-8s %-8s %-8s %-8s %-10s %s"
          % ("源", "stratum", "T1", "T2", "T3", "T4", "偏移θ", "延迟δ"))
    print("    " + "-" * 82)
    results = []
    for name, stratum, t1, t2, t3, t4 in SAMPLES:
        theta, delta = compute(t1, t2, t3, t4)
        results.append((name, stratum, theta, delta))
        print("    %-18s %-6d %-8.0f %-8.0f %-8.0f %-8.0f %-10.1f %.1f"
              % (name, stratum, t1, t2, t3, t4, theta, delta))

    print("\n[3] 每个源的偏移不确定区间 [θ - δ/2, θ + δ/2]")
    intervals = []
    for name, _s, theta, delta in results:
        lo = theta - delta / 2.0
        hi = theta + delta / 2.0
        intervals.append((lo, hi))
        print("    %-18s θ=%-8.1f δ=%-8.1f -> [%.1f, %.1f]"
              % (name, theta, delta, lo, hi))

    print("\n[4] 延迟筛选：δ 过大的源先剔除（网络抖动大、可信度低）")
    delta_threshold = 150.0
    kept = [(n, s, th, d) for n, s, th, d in results if d <= delta_threshold]
    for name, _s, _th, d in results:
        flag = "保留" if d <= delta_threshold else "剔除"
        print("    %-18s δ=%-8.1f %s（阈值 %.0f ms）" % (name, d, flag, delta_threshold))
    print("    >>> 保留 %d 个源参与选源" % len(kept))

    kept_intervals = []
    for name, _s, theta, delta in kept:
        kept_intervals.append((theta - delta / 2.0, theta + delta / 2.0))
    lo, hi, cover = marzullo(kept_intervals)
    print("\n[5] Marzullo 交集：找被最多源共同覆盖的偏移区间")
    print("    参与区间：%s" % ", ".join("[%.1f, %.1f]" % iv for iv in kept_intervals))
    print("    最大共同覆盖区间 = [%.1f, %.1f]，被 %d 个源覆盖" % (lo, hi, cover))
    mid = (lo + hi) / 2.0
    print("    取区间中点作为共识偏移 = %.1f ms" % mid)

    best = min(kept, key=lambda x: x[3])
    print("\n[6] 最优源选择")
    print("    策略：在交集覆盖的源里，选 δ 最小、stratum 最优者")
    print("    最优源 = %s（stratum=%d，δ=%.1f ms，θ=%.1f ms）"
          % (best[0], best[1], best[3], best[2]))
    print("    校正动作：把本地时钟调整 %.1f ms（θ>0 表示本地慢，需往前拨）" % best[2])
    print("    >>> 单源结果不可信：若只信 ntp4（θ=17ms），会与共识 %.1f ms 偏差 %.1f ms"
          % (mid, 17.0 - mid))

    print("\n[7] Stratum 层级说明")
    print("    %-8s %s" % ("Stratum", "含义"))
    print("    " + "-" * 60)
    for lv in (0, 1, 2, 3, 15, 16):
        print("    %-8d %s" % (lv, STRATUM[lv]))
    print("    >>> 客户端应优先选择 stratum 小、延迟小、抖动小的源，且至少配置 3~4 个源")

    print("\n[8] NTP 与 PTP 的精度对比")
    print("    %-10s %-14s %-16s %s" % ("协议", "典型精度", "传输", "场景"))
    print("    " + "-" * 66)
    ptp = [
        ("NTP", "毫秒~几十毫秒", "UDP 123", "操作系统时间同步"),
        ("PTP", "亚微秒~纳秒", "以太网(硬件打时间戳)", "金融交易、电力、5G 前传"),
    ]
    for a, b, c, d in ptp:
        print("    %-10s %-14s %-16s %s" % (a, b, c, d))
    print("    >>> PTP 精度靠硬件时间戳与专用时钟；NTP 受软件时间戳与网络抖动限制")

    print("\n" + "=" * 74)
    print("小结")
    print("-" * 74)
    print("1. NTP 用 T1~T4 四个时间戳算偏移 θ=((T2-T1)+(T3-T4))/2 与延迟 δ=(T4-T1)-(T3-T2)。")
    print("2. θ 为正说明本地时钟慢于服务器，应把本地时间往前调整 |θ|。")
    print("3. 单源不可信，需多源并剔除 δ 过大的源，再用 Marzullo 交集求共识区间。")
    print("4. Stratum 16 表示未同步必须忽略；对精度要求到微秒级应改用 PTP。")


if __name__ == "__main__":
    main()
