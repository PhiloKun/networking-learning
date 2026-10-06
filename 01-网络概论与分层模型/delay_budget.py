#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""链路时延预算：发送 / 传播 / 处理 / 排队四种时延、时延带宽积与 RTT。

运行: python3 delay_budget.py [帧长字节数]
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 80
SUB = "-" * 80

# 链路参数表：（名称, 带宽 bps, 距离 m, 介质速度 m/s, 平均排队积压 bit）
LINKS = [
    ("PC1-SW1", 1_000_000_000, 100,       2.3e8, 0),
    ("SW1-R1 ",   100_000_000, 1_000_000, 2.0e8, 4000),
    ("R1-PC2 ",    10_000_000, 10_000,    2.0e8, 0),
]
NODES = [("SW1", 20e-6), ("R1", 50e-6)]  # 每台设备每包处理时延（秒）


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def fmt_sec(s: float) -> str:
    if s >= 1:
        return f"{s:.3f} s"
    if s >= 1e-3:
        return f"{s * 1e3:.3f} ms"
    return f"{s * 1e6:.3f} us"


def main() -> None:
    frame_bytes = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    L = frame_bytes * 8

    print(SEP)
    print("端到端时延预算 · PC1 经 SW1、R1 到 PC2")
    print(SEP)
    print("拓扑： PC1 -- LinkA -- SW1 -- LinkB -- R1 -- LinkC -- PC2")
    print(f"帧长 L = {frame_bytes} 字节 = {L} bit")
    print()
    print("链路参数表")
    print(SUB)
    print(pad("链路", 12) + pad("带宽 R", 12, True) + pad("距离 d", 12, True)
          + pad("介质速度 v", 14, True) + pad("排队积压", 12, True))
    print(SUB)
    for name, bw, dist, v, q in LINKS:
        print(pad(name, 12) + pad(f"{bw / 1e6:.0f} Mbps", 12, True)
              + pad(f"{dist / 1000:.1f} km", 12, True)
              + pad(f"{v / 1e8:.2f}e8 m/s", 14, True) + pad(f"{q} bit", 12, True))
    print(SUB)
    print()

    total_tx = total_prop = total_queue = 0.0
    bdp_list: list[tuple[str, float]] = []
    print(SUB)
    print("【一】逐链路计算 发送时延 与 传播时延")
    print(SUB)
    print("公式： 发送时延 = L / R        传播时延 = d / v")
    print(SUB)
    print(pad("链路", 12) + pad("发送时延 L/R", 16, True) + pad("传播时延 d/v", 16, True)
          + pad("时延带宽积 R*d/v", 18, True))
    print(SUB)
    for name, bw, dist, v, q in LINKS:
        tx = L / bw
        prop = dist / v
        bdp = bw * prop
        total_tx += tx
        total_prop += prop
        bdp_list.append((name, bdp))
        print(pad(name, 12) + pad(fmt_sec(tx), 16, True) + pad(fmt_sec(prop), 16, True)
              + pad(f"{bdp:.0f} bit", 18, True))
    print(SUB)
    print(f"发送时延合计 = {fmt_sec(total_tx)}   传播时延合计 = {fmt_sec(total_prop)}")
    print()

    print(SUB)
    print("【二】处理时延 与 排队时延（按中间设备逐项算）")
    print(SUB)
    print("公式： 排队时延 = 队列积压比特数 / 链路带宽")
    print(SUB)
    total_proc = 0.0
    print(pad("设备 / 链路", 16) + pad("处理时延", 14, True) + pad("排队时延", 14, True)
          + pad("说明", 30))
    print(SUB)
    total_proc += NODES[0][1]
    print(pad("SW1 处理", 16) + pad(fmt_sec(NODES[0][1]), 14, True) + pad("—", 14, True)
          + pad("交换芯片查表转发", 30))
    linkb = LINKS[1]
    qb = linkb[4] / linkb[1]
    total_queue += qb
    print(pad("LinkB 排队", 16) + pad("—", 14, True) + pad(fmt_sec(qb), 14, True)
          + pad("100M 链路有积压", 30))
    total_proc += NODES[1][1]
    print(pad("R1 处理", 16) + pad(fmt_sec(NODES[1][1]), 14, True) + pad("—", 14, True)
          + pad("路由查表 + 校验", 30))
    print(SUB)
    print(f"处理时延合计 = {fmt_sec(total_proc)}   排队时延合计 = {fmt_sec(total_queue)}")
    print()

    one_way = total_tx + total_prop + total_proc + total_queue
    print(SUB)
    print("【三】单程总时延汇总")
    print(SUB)
    print(f"发送 {fmt_sec(total_tx)} + 传播 {fmt_sec(total_prop)}"
          f" + 处理 {fmt_sec(total_proc)} + 排队 {fmt_sec(total_queue)}")
    print(f">>> 单程总时延 = {fmt_sec(one_way)}")
    print()

    print(SUB)
    print("【四】时延带宽积 BDP 与 RTT")
    print(SUB)
    print("BDP = 带宽 x 传播时延，含义是链路上「在途」的比特数，即管道总容量。")
    print(SUB)
    for name, bdp in bdp_list:
        print(pad(name, 12) + f" BDP = {bdp:>10.0f} bit = {bdp / 8:>8.1f} B"
              f" = {bdp / 8 / 1500:>6.2f} 个 1500B 帧")
    print(SUB)
    rtt_prop = 2 * total_prop
    rtt_total = 2 * one_way
    print(f">>> 纯传播 RTT（2 x 传播时延合计） = {fmt_sec(rtt_prop)}")
    print(f">>> 完整往返总时间（单程总时延 x 2） = {fmt_sec(rtt_total)}")
    print(f">>> 差额 = {fmt_sec(rtt_total - rtt_prop)}，来自发送 / 排队 / 处理，"
          f"带宽能压缩这部分。")
    print()

    print(SUB)
    print("【五】带宽提升 10 倍后（仅 LinkB 变 1 Gbps，其余不变）")
    print(SUB)
    old_b = L / LINKS[1][1]
    new_b = L / 1_000_000_000
    new_total = one_way - old_b + new_b
    print(f"LinkB 发送时延： {fmt_sec(old_b)} -> {fmt_sec(new_b)}（减少 {fmt_sec(old_b - new_b)}）")
    print(f"单程总时延：     {fmt_sec(one_way)} -> {fmt_sec(new_total)}")
    print(f">>> 带宽提升 10 倍，单程时延仅从 {fmt_sec(one_way)} 降到 {fmt_sec(new_total)}，")
    print(f"    因为传播时延 {fmt_sec(total_prop)} 由光速决定，带宽再高也降不下来。")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. 四种时延中，长距离链路上传播时延常是主项：本算例占单程总时延 "
          f"{total_prop / one_way * 100:.1f}%。")
    print(f"2. BDP 最大链路为 LinkB，在途可容纳约 "
          f"{max(b for _, b in bdp_list) / 8 / 1500:.1f} 个 1500B 帧，"
          f"这解释了高带宽长链路为何需要大 TCP 窗口。")
    print(f"3. 完整 RTT {fmt_sec(rtt_total)} 大于纯传播 RTT {fmt_sec(rtt_prop)}，"
          f"差额就是发送 / 处理 / 排队。")
    print("4. 扩容带宽能降时延中的发送与排队部分，但传播时延锁死于物理距离与光速。")
    print()


if __name__ == "__main__":
    main()
