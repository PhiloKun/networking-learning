#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""奈氏准则与香农定理：给定带宽、信噪比、电平数，算极限速率并找瓶颈。

运行: python3 shannon_nyquist.py [带宽Hz] [信噪比dB] [电平数V]
"""
import sys
import math
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 74
SUB = "-" * 74


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def db_to_ratio(db: float) -> float:
    return 10 ** (db / 10.0)


def nyquist(bandwidth: float, levels: int) -> float:
    """无噪声信道极限：C = 2 * H * log2(V)。"""
    return 2 * bandwidth * math.log2(levels)


def shannon(bandwidth: float, snr_ratio: float) -> float:
    """有噪声信道极限：C = H * log2(1 + S/N)。"""
    return bandwidth * math.log2(1 + snr_ratio)


def bps(v: float) -> str:
    if v >= 1e9:
        return f"{v / 1e9:.3f} Gbit/s"
    if v >= 1e6:
        return f"{v / 1e6:.3f} Mbit/s"
    if v >= 1e3:
        return f"{v / 1e3:.3f} kbit/s"
    return f"{v:.1f} bit/s"


def main() -> None:
    H = float(sys.argv[1]) if len(sys.argv) > 1 else 3000.0
    snr_db = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    V = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    snr = db_to_ratio(snr_db)
    c_nyq = nyquist(H, V)
    c_sha = shannon(H, snr)
    bottleneck = min(c_nyq, c_sha)

    print(SEP)
    print("奈氏准则 与 香农定理 · 信道极限速率")
    print(SEP)
    print(f"带宽 H = {H:.0f} Hz    信噪比 S/N = {snr_db:.1f} dB = {snr:.2f}（线性）")
    print(f"电平数 V = {V}（每码元 log2(V) = {math.log2(V):.3f} bit）")
    print()
    print("公式")
    print(SUB)
    print("  奈氏准则（无噪声）： C = 2 * H * log2(V)      [单位 bit/s]")
    print("  香农定理（有噪声）： C = H * log2(1 + S/N)    [单位 bit/s]")
    print("  信噪比换算：         S/N = 10^(SNR_dB / 10)")
    print(SUB)
    print()

    print(SUB)
    print("【一】代入计算")
    print(SUB)
    print("奈氏：C = 2 x H x log2(V)")
    print(f"      = 2 x {H:.0f} x log2({V})")
    print(f"      = 2 x {H:.0f} x {math.log2(V):.3f}")
    print(f"      = {c_nyq:.1f} bit/s = {bps(c_nyq)}")
    print()
    print("信噪比换算：S/N = 10^(30/10)" if abs(snr_db - 30) < 1e-9
          else f"信噪比换算：S/N = 10^({snr_db:.1f}/10)")
    print(f"           = {snr:.3f}")
    print("香农：C = H x log2(1 + S/N)")
    print(f"      = {H:.0f} x log2(1 + {snr:.3f})")
    print(f"      = {H:.0f} x {math.log2(1 + snr):.3f}")
    print(f"      = {c_sha:.1f} bit/s = {bps(c_sha)}")
    print(SUB)
    print(f">>> 奈氏极限 = {bps(c_nyq)}    香农极限 = {bps(c_sha)}")
    if c_nyq < c_sha:
        print(f">>> 瓶颈是【奈氏准则】：电平数 V={V} 太少，码元携带的信息量不足，")
        print(f"    此时信道噪声还不是限制因素，应增大 V（调制阶数）。")
    elif c_sha < c_nyq:
        print(f">>> 瓶颈是【香农定理】：噪声决定了上限，继续增大 V 也突破不了 {bps(c_sha)}。")
    else:
        print(">>> 两者相等，此时 V 的取值刚好匹配当前信噪比。")
    print()

    print(SUB)
    print("【二】电平数 V 扫描（固定 H 与信噪比）")
    print(SUB)
    print(pad("电平数 V", 12) + pad("bits/码元", 12, True) + pad("奈氏极限", 16, True)
          + pad("香农极限", 16, True) + pad("有效上限=min", 18, True))
    print(SUB)
    for v in [2, 4, 8, 16, 32, 64, 128, 256]:
        nq = nyquist(H, v)
        eff = min(nq, c_sha)
        print(pad(str(v), 12) + pad(f"{math.log2(v):.0f}", 12, True)
              + pad(bps(nq), 16, True) + pad(bps(c_sha), 16, True)
              + pad(bps(eff), 18, True))
    print(SUB)
    # 找出不超过香农极限的最大 V
    v_limit = 2
    while nyquist(H, v_limit * 2) <= c_sha:
        v_limit *= 2
    print(f">>> 在 S/N = {snr:.1f}（{snr_db:.1f} dB）下，V 超过 {v_limit} 后")
    print(f"    奈氏极限就会高于香农极限，继续加电平只是「无用功」——噪声已经封顶。")
    print()

    print(SUB)
    print("【三】信噪比扫描（固定 H，V 取 2 时的可用上限）")
    print(SUB)
    print(pad("信噪比 dB", 12) + pad("S/N 线性", 14, True) + pad("香农极限", 16, True)
          + pad("奈氏(V=2)", 16, True) + pad("有效上限", 16, True))
    print(SUB)
    for db in [0, 10, 20, 30, 40, 50]:
        ratio = db_to_ratio(db)
        sh = shannon(H, ratio)
        nq = nyquist(H, 2)
        print(pad(str(db), 12) + pad(f"{ratio:.1f}", 14, True) + pad(bps(sh), 16, True)
              + pad(bps(nq), 16, True) + pad(bps(min(sh, nq)), 16, True))
    print(SUB)
    print(">>> 香农极限随信噪比近似对数增长：信噪比每提高 3 dB，容量约增加 1 bit/Hz 的一部分。")
    print("    但奈氏极限与信噪比无关，只由带宽与电平数决定。")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. 本算例 H={H:.0f}Hz、SNR={snr_db:.1f}dB、V={V}：奈氏 {bps(c_nyq)}，"
          f"香农 {bps(c_sha)}。")
    print(f"2. 实际可达速率取两者较小值：{bps(bottleneck)}，这条信道就是瓶颈所在。")
    print("3. 奈氏准则管「带宽 + 电平数」，香农定理管「带宽 + 信噪比」，二者缺一不可。")
    print("4. 工程上先看香农给不给得起速率，再用奈氏决定调制阶数与码元速率。")
    print()


if __name__ == "__main__":
    main()
