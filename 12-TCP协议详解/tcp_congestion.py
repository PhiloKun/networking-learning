#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TCP Reno 拥塞控制模拟：慢启动 → 拥塞避免 → 快重传快恢复 → 超时重置，含 cwnd 字符画曲线。

运行: python3 tcp_congestion.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

TOTAL_ROUNDS = 30
INIT_SSTHRESH = 16          # 单位：MSS
INIT_CWND = 1


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


def simulate():
    """返回 [(轮次, 阶段, cwnd, ssthresh, 事件)]，事件驱动、固定轮数，必然终止。"""
    cwnd = INIT_CWND
    ssthresh = INIT_SSTHRESH
    trace = []
    # 预设事件：某些轮次触发丢包
    dup_ack_round = 13          # 第 13 轮发生 3 个重复 ACK
    timeout_round = 22          # 第 22 轮发生超时
    for r in range(1, TOTAL_ROUNDS + 1):
        phase = "慢启动" if cwnd < ssthresh else "拥塞避免"
        event = ""
        # 先记录本轮开始时的窗口
        trace.append((r, phase, cwnd, ssthresh, event))
        # 计算下一轮窗口
        if r == dup_ack_round:
            old = cwnd
            ssthresh = max(old // 2, 2)
            cwnd = ssthresh + 3         # 快恢复：认为还有 3 个包在网中
            trace[-1] = (r, phase, old, ssthresh,
                         f"3 个重复 ACK → 快重传；ssthresh={old}//2={ssthresh}，"
                         f"cwnd={ssthresh}+3={cwnd}（快恢复）")
            continue
        if r == dup_ack_round + 1:
            trace[-1] = (r, "快恢复", cwnd, ssthresh,
                         f"新 ACK 到达 → 退出快恢复，cwnd 从 {cwnd} 收敛到 ssthresh={ssthresh}")
            cwnd = ssthresh              # 收到新 ACK，退出快恢复
            continue
        if r == timeout_round:
            old = cwnd
            ssthresh = max(old // 2, 2)
            cwnd = 1
            trace[-1] = (r, phase, old, ssthresh,
                         f"超时 → ssthresh={old}//2={ssthresh}，cwnd 重置为 1，回到慢启动")
            continue
        # 正常推进
        if cwnd < ssthresh:
            cwnd = cwnd * 2              # 慢启动：每个 RTT 翻倍
        else:
            cwnd = cwnd + 1              # 拥塞避免：每个 RTT +1
    return trace


def main():
    print()
    print("TCP Reno 拥塞控制模拟 · cwnd 单位 = MSS，初始 ssthresh = 16，初始 cwnd = 1")
    print("事件安排：第 13 轮出现 3 个重复 ACK，第 22 轮发生超时重传")
    print()

    trace = simulate()

    print("=" * 88)
    print("一、逐轮状态表")
    print("-" * 88)
    print(pad("轮次", 6) + pad("阶段", 12) + pad("cwnd(MSS)", 12)
          + pad("ssthresh", 10) + "事件")
    for r, phase, cwnd, ssthresh, event in trace:
        print(pad(str(r), 6) + pad(phase, 12) + pad(str(cwnd), 12)
              + pad(str(ssthresh), 10) + event)
    print("-" * 88)

    print()
    print("=" * 88)
    print("二、cwnd 字符画曲线（每格 = 1 MSS）")
    print("-" * 88)
    for r, phase, cwnd, ssthresh, event in trace:
        bar = "*" * min(cwnd, 40)
        mark = "  <== 事件" if event else ""
        print(pad("R" + str(r), 5) + pad(str(cwnd).rjust(3), 5) + bar + mark)
    print("-" * 88)
    print("读图要点：")
    print("  · 前 5 轮的阶梯上升（1→2→4→8→16）是指数增长的慢启动。")
    print("  · 之后每轮 +1 的斜坡是线性增长的拥塞避免。")
    print("  · 第 13 轮被削掉一半再 +3，是快重传 + 快恢复。")
    print("  · 第 22 轮直接砸回 1，是超时重传的惩罚。")
    print()

    print("=" * 88)
    print("三、四个阶段的规则明细")
    print("-" * 88)
    rules = [
        ("慢启动 Slow Start",
         "cwnd 从 1 开始，每收到 1 个 ACK 加 1 MSS，效果是每个 RTT 翻倍（指数增长）",
         "直到 cwnd >= ssthresh，切换到拥塞避免"),
        ("拥塞避免 Congestion Avoidance",
         "每个 RTT 只加 1 MSS（线性增长，AIMD 中的加法增大 AI）",
         "直到检测到丢包"),
        ("快重传 Fast Retransmit",
         "收到 3 个重复 ACK 就立即重传丢失段，不等 RTO 超时",
         "ssthresh = cwnd // 2，cwnd = ssthresh + 3（快恢复）"),
        ("超时重传 Timeout",
         "RTO 到点仍未收到 ACK，判定网络严重拥塞",
         "ssthresh = cwnd // 2，cwnd = 1，重新慢启动（乘法减小 MD）"),
    ]
    print(pad("阶段", 32) + "触发与规则")
    for a, b, c in rules:
        print(pad(a, 32) + b)
        print(pad("", 32) + "去向：" + c)
    print("-" * 88)

    print()
    print("=" * 88)
    print("四、AIMD 与 ssthresh 的数值推演")
    print("-" * 88)
    dup = next(e for e in trace if "重复 ACK" in e[4])
    tmo = next(e for e in trace if "超时" in e[4])
    print("AIMD = Additive Increase / Multiplicative Decrease（加法增大、乘法减小）：")
    print("  · 加法增大：拥塞避免阶段 cwnd 每 RTT +1，是缓慢试探。")
    print("  · 乘法减小：一旦丢包，ssthresh 减半（×0.5），是快速退让。")
    print()
    print("本模拟中的两次调整（数值直接取自上面的逐轮表）：")
    print(f"  第 {dup[0]} 轮 3 个重复 ACK：cwnd={dup[2]} → ssthresh = {dup[2]} // 2 = {dup[3]}")
    print(f"      快恢复期间 cwnd 临时取 {dup[3]} + 3 = {dup[3] + 3}，收到新 ACK 后回落到 {dup[3]}")
    print(f"  第 {tmo[0]} 轮 超时：cwnd={tmo[2]} → ssthresh = {tmo[2]} // 2 = {tmo[3]}，cwnd = 1（彻底重置）")
    print("  ssthresh 的下限是 2 MSS：RFC 5681 规定 ssthresh = max(飞行中数据/2, 2×SMSS)，")
    print("  避免窗口被压到 1 后永远无法进入拥塞避免。")
    print()
    print(">>> 结论：快重传把「等超时」的几十毫秒到几秒的等待，缩短为一个 RTT；")
    print("    快恢复让 cwnd 不必回到 1，因此两者合称「快速恢复」，是现代 TCP 的默认行为。")
    print()

    print("=" * 88)
    print("五、几种拥塞控制算法对比")
    print("-" * 88)
    algos = [
        ("Tahoe", "任意丢包", "cwnd=1，重新慢启动", "最老，丢包即崩"),
        ("Reno", "3 个重复 ACK 或超时", "快恢复（cwnd=ssh+3）/ 超时归 1", "经典，双重策略"),
        ("NewReno", "同 Reno，但改进快恢复", "一个 RTT 内多丢包时只减半一次", "部分改进丢失"),
        ("CUBIC", "丢包（窗口函数驱动）", "用三次函数恢复，不依赖 RTT", "Linux 默认，高带宽友好"),
        ("BBR", "带宽与 RTT 建模", "不按丢包退让，按瓶颈带宽调整", "Google 出品，抗随机丢包"),
    ]
    print(pad("算法", 16) + pad("丢包判断依据", 30) + pad("丢包后的动作", 32) + "特点")
    for a, b, c, d in algos:
        print(pad(a, 16) + pad(b, 30) + pad(c, 32) + d)
    print("-" * 88)
    print(">>> 结论：Reno 把「丢包」当作唯一拥塞信号，在随机丢包的高质量链路上会误判；")
    print("    CUBIC 用与 RTT 无关的窗口函数在高带宽长时延链路上更激进；")
    print("    BBR 直接估计带宽与最小 RTT，不把丢包当拥塞信号，适合有随机丢包的骨干链路。")
    print()
    print("小结：")
    print("1. 慢启动指数增长到 ssthresh，之后拥塞避免线性增长，这是 AIMD 的两半。")
    print("2. 3 个重复 ACK 触发快重传 + 快恢复：ssthresh=cwnd/2，cwnd=ssthresh+3，不必回到 1。")
    print("3. 超时是更严重的信号：ssthresh=cwnd/2，cwnd=1，回到慢启动，恢复代价远高于快恢复。")
    print()


if __name__ == "__main__":
    main()
