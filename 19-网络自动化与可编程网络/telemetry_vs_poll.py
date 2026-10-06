#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNMP 轮询 vs 流式遥测：按设备规模算带宽、时延、采集周期，并给出选型结论。

运行: python3 telemetry_vs_poll.py
"""
import sys

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

N_DEV = 5000            # 设备台数
N_OID = 200             # 每台设备采集的指标数
WINDOW = 300            # 统一观察窗口（秒）

SNMP_REQ = 100          # 单次 GetRequest 报文（含 community 与 OID）
SNMP_RESP = 120         # 单个 OID 的 GetResponse 载荷
SNMP_BULK_REQ = 120     # GetBulk 请求
SNMP_BULK_RESP = 130    # GetBulk 中单个 OID 条目
BULK_REPS = 25          # max-repetitions

TELEMETRY_UPDATE = 400  # 单条遥测更新报文（protobuf 负载 + gRPC 封装）
CHANGE_RATIO = 0.10     # 每次上报内发生变化的指标比例


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"


def human_rate(bps: float) -> str:
    if bps < 1000:
        return f"{bps:.1f} bit/s"
    if bps < 1_000_000:
        return f"{bps / 1000:.2f} kbit/s"
    if bps < 1_000_000_000:
        return f"{bps / 1e6:.2f} Mbit/s"
    return f"{bps / 1e9:.2f} Gbit/s"


def snmp_per_oid_bytes() -> float:
    """一次完整轮询全网的字节数（逐 OID GetRequest）。"""
    return N_OID * (SNMP_REQ + SNMP_RESP) * N_DEV


def snmp_bulk_bytes() -> float:
    """一次完整轮询全网的字节数（GetBulk）。"""
    reqs = -(-N_OID // BULK_REPS)                     # 向上取整 = 8
    return reqs * (SNMP_BULK_REQ + BULK_REPS * SNMP_BULK_RESP) * N_DEV


def telemetry_bytes(change_ratio: float) -> float:
    """一次遥测上报全网的字节数。"""
    return N_OID * change_ratio * TELEMETRY_UPDATE * N_DEV


def bw(total_bytes: float, interval: float) -> float:
    """把一次上报的字节数换算成带宽（bit/s）。"""
    return total_bytes * 8 / interval


def main() -> None:
    print(SEP)
    print("SNMP 轮询 vs 流式遥测：规模、带宽与时延对照")
    print(SEP)
    print(f"采集规模：{N_DEV} 台设备 × {N_OID} 个指标；统一观察窗口 = {WINDOW} 秒")

    poll_bytes = snmp_per_oid_bytes()
    bulk_bytes = snmp_bulk_bytes()
    tele_chg = telemetry_bytes(CHANGE_RATIO)
    tele_full = telemetry_bytes(1.0)

    print()
    print(SUB)
    print("【一】「一次采集」的报文量（全网合计）")
    print(SUB)
    print(f"{'方式':<30}{'单机字节':>12}{'全网字节':>14}{'说明'}")
    print(SUB)
    rows = [
        ("SNMP 逐 OID", poll_bytes / N_DEV, poll_bytes, f"{N_OID} 次请求 + {N_OID} 次响应"),
        ("SNMP GetBulk", bulk_bytes / N_DEV, bulk_bytes,
         f"每包 {BULK_REPS} 个 OID，共 {(-(-N_OID // BULK_REPS))} 包"),
        ("遥测(仅变化 10%)", tele_chg / N_DEV, tele_chg,
         f"{N_OID * CHANGE_RATIO:.0f} 条变化上报"),
        ("遥测(全量)", tele_full / N_DEV, tele_full, f"{N_OID} 条上报"),
    ]
    for name, per_dev, total, note in rows:
        print(f"{name:<30}{per_dev:>12.0f}{human_bytes(total):>14}   {note}")
    print(SUB)
    print("推导示例（SNMP 逐 OID）：")
    print(f"  {N_OID} × ({SNMP_REQ} + {SNMP_RESP}) × {N_DEV} = {poll_bytes:.0f} B "
          f"= {human_bytes(poll_bytes)}")

    print()
    print(SUB)
    print("【二】相同滞后下的带宽对比（都以 300 秒为一次采集周期）")
    print(SUB)
    print(f"{'方式':<30}{'带宽':>14}{'采集滞后':>10}{'相对基线'}")
    print(SUB)
    baseline = bw(poll_bytes, WINDOW)
    rows2 = [
        ("SNMP 逐 OID", bw(poll_bytes, WINDOW), WINDOW),
        ("SNMP GetBulk", bw(bulk_bytes, WINDOW), WINDOW),
        ("遥测(仅变化 10%)", bw(tele_chg, WINDOW), WINDOW),
        ("遥测(全量)", bw(tele_full, WINDOW), WINDOW),
    ]
    for name, rate, stale in rows2:
        ratio = rate / baseline * 100
        print(f"{name:<30}{human_rate(rate):>14}{stale:>10}{ratio:>9.1f}%")
    print(SUB)
    print(">>> 结论：同样 300 秒滞后下，遥测只推变化量，带宽最低（约为逐 OID 轮询的 18%）。")

    print()
    print(SUB)
    print("【三】遥测的价值：用可控带宽换低滞后")
    print(SUB)
    print(f"{'上报周期(s)':<14}{'滞后(s)':<10}{'遥测(10%变化)带宽':<24}{'若 SNMP 达到同滞后所需带宽'}")
    print(SUB)
    for interval in (300, 60, 30, 10, 5):
        tele_rate = bw(tele_chg, interval)
        snmp_rate = bw(poll_bytes, interval)
        print(f"{interval:<14}{interval:<10}{human_rate(tele_rate):<24}{human_rate(snmp_rate)}")
    print(SUB)
    print(">>> 推导：把 SNMP 轮询周期压到 10 秒，带宽 = "
          f"{human_bytes(poll_bytes)} × 8 / 10 = {human_rate(bw(poll_bytes, 10))}")
    print(f">>> 同样 10 秒刷新，遥测只需 {human_rate(bw(tele_chg, 10))}，"
          f"差距 {bw(poll_bytes, 10) / bw(tele_chg, 10):.1f} 倍")

    print()
    print(SUB)
    print("【四】设备侧开销与规模上限")
    print(SUB)
    print(f"  SNMP：轮询由网管发起、设备被动应答，每次要序列化 {N_OID} 个 OID；")
    print("        周期越短，设备的 CPU 与 SNMP 进程压力越大，周期压到秒级会先压垮设备。")
    print("  遥测：建立长期 gRPC 订阅，设备在指标变化时推一次；")
    print("        采样频率由设备侧控制，网管只负责接收，没有「拉取风暴」。")
    print("  约束：遥测需要设备支持 gNMI/gRPC，老设备只能退回 SNMP。")

    print()
    print(">>> 选型结论：")
    print("    1) 大规模 + 秒级实时性要求 -> 流式遥测（gNMI/gRPC），只订阅关键指标。")
    print("    2) 中小规模 + 兼容老设备 -> SNMP，且必须用 GetBulk + 合理周期。")
    print("    3) 现实最常见是混合：核心/出口设备走遥测，边缘与老设备走 SNMP 轮询。")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. {N_DEV} 台 × {N_OID} 指标、300 秒周期下，逐 OID 轮询带宽约 "
          f"{human_rate(bw(poll_bytes, WINDOW))}，GetBulk 约 {human_rate(bw(bulk_bytes, WINDOW))}。")
    print(f"2. 同样 300 秒滞后，遥测(仅变化)带宽约 {human_rate(bw(tele_chg, WINDOW))}，"
          f"是逐 OID 轮询的 {bw(tele_chg, WINDOW) / bw(poll_bytes, WINDOW) * 100:.0f}%。")
    print("3. 若把 SNMP 压到 10 秒周期，带宽飙到 "
          f"{human_rate(bw(poll_bytes, 10))}，而遥测 10 秒只需 {human_rate(bw(tele_chg, 10))}。")
    print("4. 选型关键不是「哪个带宽低」，而是实时性与设备能力的匹配。")
    print()


if __name__ == "__main__":
    main()
