#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TCP 超时重传时间 RTO 估算：Jacobson/Karels 公式（α=1/8、β=1/4）与 Karn 算法演示。

运行: python3 tcp_rto.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

ALPHA = 1 / 8      # SRTT 的平滑系数
BETA = 1 / 4       # RTTVAR 的平滑系数
G_MS = 1.0         # 时钟粒度（毫秒）
RTO_MIN_MS = 1000.0    # RFC 6298 建议的最小 RTO
RTO_MAX_MS = 60000.0   # RFC 6298 要求的上限至少为 60 秒

SAMPLES = [1500.0, 2000.0, 1200.0, 4000.0, 1600.0, 1800.0]   # 单位毫秒


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


def main():
    print()
    print("TCP RTO 估算演示 · Jacobson/Karels 算法（RFC 6298），α = 1/8，β = 1/4")
    print()

    print("=" * 92)
    print("一、两个平滑量：SRTT（平滑往返时间）与 RTTVAR（往返时间偏差）")
    print("-" * 92)
    print("首次测量 R（无历史值时）：")
    print("  SRTT   = R")
    print("  RTTVAR = R / 2")
    print("  RTO    = SRTT + max(G, 4 × RTTVAR)")
    print()
    print("后续每次测量 R（注意：先用「旧的 SRTT」算 RTTVAR，再更新 SRTT）：")
    print("  RTTVAR = (1 − β) × RTTVAR + β × |SRTT − R|      ← β = 1/4")
    print("  SRTT   = (1 − α) × SRTT   + α × R                ← α = 1/8")
    print("  RTO    = SRTT + max(G, 4 × RTTVAR)")
    print()

    print("=" * 92)
    print("二、逐样本计算（RTT 单位：毫秒，G = 1 毫秒）")
    print("-" * 92)
    srtt = None
    rttvar = None
    rows = []
    for i, r in enumerate(SAMPLES, start=1):
        if srtt is None:
            srtt = r
            rttvar = r / 2
            detail = f"SRTT={r:.2f}，RTTVAR={r:.2f}/2={rttvar:.2f}"
        else:
            old_srtt, old_var = srtt, rttvar
            dev = abs(old_srtt - r)
            rttvar = (1 - BETA) * old_var + BETA * dev
            srtt = (1 - ALPHA) * old_srtt + ALPHA * r
            detail = (f"RTTVAR=0.75×{old_var:.2f}+0.25×|{old_srtt:.2f}−{r:.0f}|"
                      f"={rttvar:.2f}；SRTT=0.875×{old_srtt:.2f}+0.125×{r:.0f}={srtt:.2f}")
        rto = srtt + max(G_MS, 4 * rttvar)
        eff = min(max(rto, RTO_MIN_MS), RTO_MAX_MS)
        rows.append((i, r, srtt, rttvar, rto, eff, detail))
    for i, r, s, v, rto, eff, detail in rows:
        print(pad(f"样本 {i}", 10) + f"R = {r:7.0f} ms")
        print(pad("", 10) + detail)
        print(pad("", 10) + f"RTO = {s:.2f} + max(1, 4×{v:.2f})"
              f" = {s:.2f} + {max(G_MS, 4 * v):.2f} = {rto:.2f} ms"
              + (f"；经上下限裁剪后生效值 = {eff:.0f} ms"
                 if abs(eff - rto) > 0.5 else "（未触发裁剪）"))
        print()
    print("-" * 92)
    print(pad("样本", 8) + pad("R(ms)", 10) + pad("SRTT(ms)", 12) + pad("RTTVAR(ms)", 12)
          + pad("RTO 公式值", 14) + "生效值")
    for i, r, s, v, rto, eff, _ in rows:
        print(pad(str(i), 8) + pad(f"{r:.0f}", 10) + pad(f"{s:.2f}", 12)
              + pad(f"{v:.2f}", 12) + pad(f"{rto:.2f}", 14) + f"{eff:.0f}")
    print("-" * 92)
    print(">>> 结论：第 4 个样本 RTT 突增到 4000ms 后，RTTVAR 从 687 跳到 1075，")
    print("    RTO 立刻升到约 6129ms；随后 RTT 恢复平稳，RTO 只会缓慢下降 ——")
    print("    这是 Jacobson/Karels 的设计意图：对恶化的响应要快，对改善的响应要慢。")
    print()

    print("=" * 92)
    print("三、α 与 β 的取值推导")
    print("-" * 92)
    print("α = 1/8 的含义：SRTT 相当于最近测量值的指数加权移动平均，")
    print("  权重衰减为 (1−1/8)=7/8，意味着一份新样本的影响会稀释为 7/8 倍地残留，")
    print("  约 8 个样本后旧数据影响降到 1/e 量级 —— 兼顾平滑与响应速度。")
    print("β = 1/4 的含义：RTTVAR 对应的是「偏差的平滑值」，取 4 倍后作为安全裕度。")
    print("  4 × RTTVAR 相当于给出约 4 个标准差量级的余量，覆盖绝大多数抖动。")
    print()
    print("代入验证（样本 2）：")
    print("  RTTVAR = (1 − 1/4) × 750.00 + (1/4) × |1500.00 − 2000|")
    print("         = 0.75 × 750.00 + 0.25 × 500.00")
    print("         = 562.50 + 125.00 = 687.50")
    print("  SRTT   = (1 − 1/8) × 1500.00 + (1/8) × 2000")
    print("         = 0.875 × 1500 + 0.125 × 2000 = 1312.50 + 250.00 = 1562.50")
    print("  RTO    = 1562.50 + 4 × 687.50 = 1562.50 + 2750.00 = 4312.50 ms")
    print()

    print("=" * 92)
    print("四、最小/最大 RTO 限制")
    print("-" * 92)
    print(pad("项", 20) + pad("RFC 6298", 22) + pad("Linux 实现", 22) + "作用")
    print(pad("最小 RTO", 20) + pad("1 秒（SHOULD）", 22) + pad("200ms", 22)
          + "避免 RTO 过小导致无谓重传")
    print(pad("最大 RTO", 20) + pad("至少 60 秒", 22) + pad("120 秒", 22)
          + "避免链路全断时长时间不发重传")
    print(pad("时钟粒度 G", 20) + pad("1 毫秒或更大", 22) + pad("1 毫秒", 22)
          + "RTO 下限不能低于 G")
    print("-" * 92)
    low = 60.0
    srtt_low = low
    rttvar_low = low / 2
    rto_low = srtt_low + max(G_MS, 4 * rttvar_low)
    print(f"下限演示：若某样本 R = {low:.0f} ms，则 SRTT = {srtt_low:.0f}，"
          f"RTTVAR = {rttvar_low:.0f}，RTO = {rto_low:.0f} ms")
    print(f"  但 RFC 6298 要求 RTO 最小取 {RTO_MIN_MS:.0f} ms，故实际生效值为 "
          f"{max(rto_low, RTO_MIN_MS):.0f} ms。")
    print(">>> 结论：同一机房内的 RTT 常只有零点几毫秒，公式会算出很小的 RTO，")
    print("    但实现会按最小值兜底 —— 这就是「本机 ping 0.1ms 却不影响 TCP 正常重传」的原因。")
    print()

    print("=" * 92)
    print("五、Karn 算法：重传过的段不能用来采样 RTT")
    print("-" * 92)
    print("场景：段 A 发送后超时，被重传；随后收到一个 ACK。")
    print("-" * 92)
    timeline = [
        ("T = 0 ms", "发送段 A（原发），启动重传计时器", "—"),
        ("T = 4500 ms", "RTO 到点，重传段 A 并重置计时器", "—"),
        ("T = 4600 ms", "收到 acknowledgment，ack 号只能确认「A 已收到」",
         "无法判断它确认的是原发还是重传"),
        ("错误做法", "按「重传时刻」计算 RTT = 4600 − 4500 = 100 ms",
         "偏小 → SRTT 被拉低，RTO 变小，后续误重传增多"),
        ("错误做法", "按「原发时刻」计算 RTT = 4600 − 0 = 4600 ms",
         "偏大 → SRTT 被抬高，RTO 变大，丢包恢复变慢"),
        ("Karn 算法", "对重传过的段完全不采样，SRTT/RTTVAR 保持不变",
         "避免用歧义样本污染估计"),
    ]
    print(pad("时刻", 16) + pad("事件", 46) + "RTT 采样结论")
    for a, b, c in timeline:
        print(pad(a, 16) + pad(b, 46) + c)
    print("-" * 92)
    print("Karn 算法的配套规则：")
    print("  1) 只要某段被重传过，就不再根据它的 ACK 采样 RTT。")
    print("  2) 每次重传时把 RTO 做指数退避：RTO = min(2 × RTO, 上限)，")
    print("     典型退避序列为 1s → 2s → 4s → 8s …（对应 TCP 的 SYN 重传节奏）。")
    print("  3) RFC 1323 的 Timestamps 选项可以让「重传后仍能采样」：")
    print("     因为每个 ACK 都带回被确认段的 TSval，能精确算出它对应的发送时刻，")
    print("     从而消除歧义 —— 这是现代 Linux 默认开启时间戳的原因之一。")
    print()
    print("小结：")
    print("1. RTO = SRTT + max(G, 4 × RTTVAR)；首次测量时 SRTT = R、RTTVAR = R/2。")
    print("2. 更新顺序很关键：先用旧 SRTT 算 RTTVAR，再更新 SRTT，α = 1/8、β = 1/4。")
    print("3. RTO 对 RTT 恶化反应快、对改善反应慢；实现还会用 1 秒下限与 60 秒上限兜底。")
    print("4. Karn 算法规定重传过的段不采样 RTT，避免歧义样本污染估计；")
    print("   配合时间戳选项可以在重传后继续精确采样。")
    print()


if __name__ == "__main__":
    main()
