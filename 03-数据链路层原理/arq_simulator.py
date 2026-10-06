#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""停等 / 后退 N 帧 GBN / 选择重传 SR 三种 ARQ 协议的性能模拟。

运行: python3 arq_simulator.py [丢包率，默认 0.1] [窗口大小，默认 4]
"""
import sys
import random
import unicodedata

sys.dont_write_bytecode = True

random.seed(42)
SEP = "=" * 82
SUB = "-" * 82
N_FRAMES = 100
MAX_ROUNDS = 200000
RTT_SLOTS = 4      # 往返传播 + 确认时间，折算成「4 个帧的发送时间」


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def stop_and_wait(n: int, p: float) -> tuple[int, int, int]:
    """每帧发出后等一个 RTT 的确认，丢失就重传，直到成功。"""
    transmissions = 0
    rounds = 0
    for _ in range(n):
        while True:
            rounds += 1
            transmissions += 1
            if random.random() >= p:
                break
    return transmissions, transmissions - n, rounds


def go_back_n(n: int, w: int, p: float) -> tuple[int, int, int]:
    """累积确认：某帧丢失后，从该帧起整个窗口全部重传。"""
    transmissions = 0
    base = 0
    rounds = 0
    while base < n and rounds < MAX_ROUNDS:
        rounds += 1
        end = min(base + w, n)
        ok = []
        for _ in range(base, end):
            transmissions += 1
            ok.append(random.random() >= p)
        adv = 0
        while adv < len(ok) and ok[adv]:
            adv += 1
        if adv == 0:
            continue          # 窗口首帧就丢了，整窗重传
        base += adv
    return transmissions, transmissions - n, rounds


def selective_repeat(n: int, w: int, p: float) -> tuple[int, int, int]:
    """只重传真正丢失的帧，接收端缓存乱序帧。"""
    transmissions = 0
    acked = [False] * n
    base = 0
    rounds = 0
    while base < n and rounds < MAX_ROUNDS:
        rounds += 1
        end = min(base + w, n)
        for i in range(base, end):
            if not acked[i]:
                transmissions += 1
                if random.random() >= p:
                    acked[i] = True
        while base < n and acked[base]:
            base += 1
    return transmissions, transmissions - n, rounds


def utilization(n: int, tx: int, rounds: int) -> float:
    """信道利用率 = 有效帧数 / 占用的总时间（以帧发送时间为单位）。

    总时间 = 实际发送帧数（每帧占 1 个时间单位）+ 轮次数 x RTT_SLOTS
    （每轮结束都要等一个往返传播与确认）。
    """
    total_time = tx + rounds * RTT_SLOTS
    return n / total_time * 100


def main() -> None:
    p = float(sys.argv[1]) if len(sys.argv) > 1 else 0.1
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    print(SEP)
    print("ARQ 可靠传输协议模拟 · 停等 / 后退 N 帧 / 选择重传")
    print(SEP)
    print(f"待传帧数 N = {N_FRAMES}    单帧丢包率 p = {p:.2f}    窗口大小 W = {w}")
    print(f"往返时间 RTT = {RTT_SLOTS} 个帧的发送时间（传播 + 确认）")
    print("随机种子 random.seed(42)，结果可复现")
    print()

    print(SUB)
    print("【一】三种协议的机制差异")
    print(SUB)
    print(pad("协议", 16) + pad("发送窗口", 10) + pad("接收窗口", 10) + pad("重传范围", 20) + "确认方式")
    print(SUB)
    rows = [
        ("停等", "1", "1", "只重传当前帧", "逐帧确认"),
        ("后退 N 帧 GBN", f"{w}", "1", "从丢失帧起整窗重传", "累积确认"),
        ("选择重传 SR", f"{w}", f"{w}", "只重传丢失帧", "逐帧确认"),
    ]
    for a, b, c, d, e in rows:
        print(pad(a, 16) + pad(b, 10) + pad(c, 10) + pad(d, 20) + e)
    print(SUB)
    print()

    r1 = stop_and_wait(N_FRAMES, p)
    r2 = go_back_n(N_FRAMES, w, p)
    r3 = selective_repeat(N_FRAMES, w, p)

    print(SUB)
    print(f"【二】模拟结果（N = {N_FRAMES} 帧，丢包率 {p:.2f}，W = {w}）")
    print(SUB)
    print(pad("协议", 16) + pad("总发送帧数", 14, True) + pad("重传次数", 12, True)
          + pad("轮次数", 10, True) + pad("信道利用率", 14, True))
    print(SUB)
    data = [("停等", r1), ("后退 N 帧 GBN", r2), ("选择重传 SR", r3)]
    utils = {}
    for name, (tx, rt, rd) in data:
        u = utilization(N_FRAMES, tx, rd)
        utils[name] = u
        print(pad(name, 16) + pad(str(tx), 14, True) + pad(str(rt), 12, True)
              + pad(str(rd), 10, True) + pad(f"{u:.2f}%", 14, True))
    print(SUB)
    print(f">>> 信道利用率 = 有效帧数 / 总占用时间 = {N_FRAMES} / (发送帧数 + 轮次数 x {RTT_SLOTS})")
    print(">>> 停等每发 1 帧就等一个 RTT，链路大量时间空转，利用率最低。")
    print(f">>> GBN 能连续发 W={w} 帧，但丢 1 帧要重传整窗；SR 只补丢失帧，利用率最高。")
    print(f">>> 利用率对比：停等 {utils['停等']:.1f}% < "
          f"GBN {utils['后退 N 帧 GBN']:.1f}% < SR {utils['选择重传 SR']:.1f}%。")
    print()

    print(SUB)
    print(f"【三】窗口大小对 GBN / SR 的影响（丢包率 {p:.2f}）")
    print(SUB)
    print(pad("窗口 W", 10) + pad("GBN 总发送", 14, True) + pad("GBN 利用率", 14, True)
          + pad("SR 总发送", 14, True) + pad("SR 利用率", 14, True))
    print(SUB)
    for ww in [1, 2, 4, 8, 16]:
        random.seed(42)
        g = go_back_n(N_FRAMES, ww, p)
        random.seed(42)
        s = selective_repeat(N_FRAMES, ww, p)
        print(pad(str(ww), 10) + pad(str(g[0]), 14, True)
              + pad(f"{utilization(N_FRAMES, g[0], g[2]):.2f}%", 14, True)
              + pad(str(s[0]), 14, True)
              + pad(f"{utilization(N_FRAMES, s[0], s[2]):.2f}%", 14, True))
    print(SUB)
    print(">>> 窗口越大，GBN 因一次丢包牵连重传的帧越多，利用率反而可能下降；")
    print("    SR 的重传量不随窗口放大，利用率随窗口增大稳步提升，但需要接收端缓存乱序帧。")
    print()

    print(SUB)
    print("【四】序号位宽 n 与窗口上限的约束（防止序号歧义）")
    print(SUB)
    print(pad("序号位宽 n", 12) + pad("序号空间 2^n", 14, True)
          + pad("GBN 上限 2^n-1", 16, True) + pad("SR 上限 2^(n-1)", 16, True))
    print(SUB)
    for n in [2, 3, 4, 5, 8]:
        print(pad(str(n), 12) + pad(str(2 ** n), 14, True)
              + pad(str(2 ** n - 1), 16, True) + pad(str(2 ** (n - 1)), 16, True))
    print(SUB)
    print(">>> GBN 要求 W <= 2^n - 1：接收窗口为 1，W 过大时新老序号会重叠导致歧义。")
    print(">>> SR 要求 W <= 2^(n-1)：发送与接收窗口各占一半序号空间，避免新旧帧混淆。")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. 在 p={p:.2f}、W={w} 下，总发送帧数：停等 {r1[0]}、GBN {r2[0]}、SR {r3[0]}。")
    print(f"2. 计入 RTT 等待后，信道利用率：停等 {utils['停等']:.1f}%、"
          f"GBN {utils['后退 N 帧 GBN']:.1f}%、SR {utils['选择重传 SR']:.1f}%。")
    print("3. 停等实现最简单但链路利用率低；GBN 实现较简单、时延容忍好，但丢包代价大；"
          "SR 效率最高，代价是接收端需要缓存与更复杂的逻辑。")
    print("4. 窗口不能随便取：序号位宽决定 GBN 的 W<=2^n-1、SR 的 W<=2^(n-1)。")
    print()


if __name__ == "__main__":
    main()
