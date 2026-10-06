#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四种传输介质的传播速度、串行化时延与 1000km 光纤 RTT 分析。

运行: python3 medium_delay.py [帧长字节数]
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

# (介质, 标称速度 m/s, 折射率/减速说明)
MEDIA = [
    ("双绞线 UTP Cat6", 2.00e8, "NVP 约 0.67c"),
    ("同轴电缆 RG-6",   2.20e8, "NVP 约 0.73c"),
    ("单模光纤",        2.00e8, "群速度约 0.67c"),
    ("无线（自由空间）", 3.00e8, "即真空光速 c"),
]

RATES = [("1 Gbit/s", 1e9), ("10 Gbit/s", 10e9), ("100 Gbit/s", 100e9)]


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def fmt_sec(s: float) -> str:
    if s >= 1:
        return f"{s:.4f} s"
    if s >= 1e-3:
        return f"{s * 1e3:.4f} ms"
    if s >= 1e-6:
        return f"{s * 1e6:.4f} us"
    return f"{s * 1e9:.2f} ns"


def main() -> None:
    frame_bytes = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    L = frame_bytes * 8
    dist_km = 1000.0
    dist_m = dist_km * 1000

    print(SEP)
    print("传输介质传播速度 与 时延分解")
    print(SEP)
    print(f"帧长 L = {frame_bytes} 字节 = {L} bit    参考距离 = {dist_km:.0f} km")
    print()
    print("公式： 传播时延 = 距离 / 介质速度      串行化(发送)时延 = 帧长 / 带宽")
    print()

    print(SUB)
    print("【一】四种介质的传播速度与 1000km 传播时延")
    print(SUB)
    print(pad("介质", 20) + pad("速度 m/s", 14, True) + pad("占光速比", 12, True)
          + pad("1000km 传播时延", 20, True) + "  说明")
    print(SUB)
    fiber_prop = None
    for name, v, note in MEDIA:
        prop = dist_m / v
        if name == "单模光纤":
            fiber_prop = prop
        print(pad(name, 20) + pad(f"{v:.2e}", 14, True) + pad(f"{v / 3e8:.2f} c", 12, True)
              + pad(fmt_sec(prop), 20, True) + "  " + note)
    print(SUB)
    print(f">>> 光纤中光速约 2x10^8 m/s，1000 km 单程传播时延固定为 {fmt_sec(fiber_prop)}。")
    print("    这个数只与距离和介质有关，与带宽无关。")
    print()

    print(SUB)
    print("【二】串行化（发送）时延随带宽变化：同一帧在不同速率下")
    print(SUB)
    print(pad("速率", 14) + pad(f"{frame_bytes}B 帧串行化时延", 24, True))
    print(SUB)
    tx_map = {}
    for label, rate in RATES:
        tx = L / rate
        tx_map[label] = tx
        print(pad(label, 14) + pad(fmt_sec(tx), 24, True))
    print(SUB)
    print(">>> 带宽提高 100 倍（1G -> 100G），串行化时延从 "
          f"{fmt_sec(tx_map['1 Gbit/s'])} 降到 {fmt_sec(tx_map['100 Gbit/s'])}。")
    print("    这部分是「带宽能买到」的时延。")
    print()

    print(SUB)
    print("【三】1000km 光纤的 RTT 分解（1 Gbit/s 链路，1500B 帧）")
    print(SUB)
    tx = tx_map["1 Gbit/s"]
    rtt_prop = 2 * dist_m / 2.0e8
    # 一次「请求-响应」：A 发帧 + 传播 + B 处理 + B 发帧 + 传播
    proc = 50e-6
    rtt_full = 2 * tx + 2 * proc + rtt_prop
    print(pad("分项", 30) + pad("数值", 16, True) + pad("占比", 10, True))
    print(SUB)
    items = [
        ("A 端串行化（发送请求帧）", tx),
        ("请求帧传播（A->B）", dist_m / 2.0e8),
        ("B 端处理", proc),
        ("B 端串行化（发送响应帧）", tx),
        ("响应帧传播（B->A）", dist_m / 2.0e8),
    ]
    for label, val in items:
        print(pad(label, 30) + pad(fmt_sec(val), 16, True)
              + pad(f"{val / rtt_full * 100:.2f}%", 10, True))
    print(SUB)
    print(pad("纯传播 RTT（仅上下行传播）", 30) + pad(fmt_sec(rtt_prop), 16, True)
          + pad(f"{rtt_prop / rtt_full * 100:.2f}%", 10, True))
    print(pad("完整往返总时间", 30) + pad(fmt_sec(rtt_full), 16, True) + pad("100.00%", 10, True))
    print(SUB)
    print(f">>> 完整往返 {fmt_sec(rtt_full)} 中，有 {fmt_sec(rtt_prop)} "
          f"（{rtt_prop / rtt_full * 100:.1f}%）是传播时延。")
    print()

    print(SUB)
    print("【四】带宽升到 100 Gbit/s 后，哪部分降不下来？")
    print(SUB)
    tx100 = tx_map["100 Gbit/s"]
    rtt_100g = 2 * tx100 + 2 * proc + rtt_prop
    print(f"串行化时延： {fmt_sec(tx)} -> {fmt_sec(tx100)}（缩短 "
          f"{fmt_sec(tx - tx100)}）")
    print(f"完整往返：   {fmt_sec(rtt_full)} -> {fmt_sec(rtt_100g)}（缩短 "
          f"{fmt_sec(rtt_full - rtt_100g)}）")
    print(f">>> 降不下去的那 {fmt_sec(rtt_prop + 2 * proc)} = 传播 "
          f"{fmt_sec(rtt_prop)} + 两端处理 {fmt_sec(2 * proc)}，"
          f"其中传播部分钉死在光速上。")
    print()

    print(SUB)
    print("【五】距离对传播时延的影响（光纤，v=2x10^8 m/s）")
    print(SUB)
    print(pad("距离", 12) + pad("单程传播时延", 18, True) + pad("纯传播 RTT", 18, True)
          + "  典型场景")
    print(SUB)
    for km, scene in [(1, "机房内"), (10, "园区"), (100, "同城"), (1000, "跨省"), (10000, "跨国")]:
        p = km * 1000 / 2.0e8
        print(pad(f"{km} km", 12) + pad(fmt_sec(p), 18, True) + pad(fmt_sec(2 * p), 18, True)
              + "  " + scene)
    print(SUB)
    print(">>> 距离每增加 1000 km，纯传播 RTT 增加约 10 ms，这是跨地域访问延迟的物理下限。")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print("1. 光纤中光速约 2x10^8 m/s（0.67c），1000 km 单程传播时延固定为 5 ms。")
    print(f"2. 1500B 帧在 1 Gbit/s 上串行化需 {fmt_sec(tx)}，在 100 Gbit/s 上仅 "
          f"{fmt_sec(tx100)}。")
    print(f"3. 1000km 光纤往返总时间 {fmt_sec(rtt_full)}，其中约 "
          f"{rtt_prop / rtt_full * 100:.0f}% 是传播时延，带宽再高也降不下去。")
    print("4. 结论：优化远距离时延只能靠「减少距离」（就近部署 / CDN / 边缘节点），而非扩容带宽。")
    print()


if __name__ == "__main__":
    main()
