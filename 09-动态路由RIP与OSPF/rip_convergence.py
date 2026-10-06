#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RIP 距离矢量收敛演示：无防环 / 水平分割 / 毒性逆转 对「计数到无穷」的影响。

运行: python3 rip_convergence.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    """按终端显示宽度计长：东亚全角字符算 2 列。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    """左对齐补齐到 n 个显示列宽。"""
    return s + " " * max(0, n - w(s))


INF = 16          # RIP 中 16 跳 = 不可达
MAX_ROUNDS = 26   # 硬上限，保证脚本必然退出

# 拓扑：R1 - R2 - R3 - R4 一条链，目的网段 192.0.2.0/24 直连在 R3
NEIGHBORS = {
    "R1": ["R2"],
    "R2": ["R1", "R3"],
    "R3": ["R2", "R4"],
    "R4": ["R3"],
}
NODES = ["R1", "R2", "R3", "R4"]
DIRECT = "R3"        # 直连目的网段的路由器

# 故障前的收敛态：(度量, 下一跳)
INITIAL = {
    "R1": (2, "R2"),
    "R2": (1, "R3"),
    "R3": (0, "直连"),
    "R4": (1, "R3"),
}

MODES = [
    ("none", "无防环（裸距离矢量）"),
    ("split", "水平分割 Split Horizon"),
    ("poison", "毒性逆转 + 触发更新"),
]


def advertise(src, dst, state, mode):
    """src 向邻居 dst 通告时，本节点持有的 (度量, 下一跳) 如何呈现。"""
    metric, nxt = state[src]
    if nxt == dst:                      # 这条路由正是从 dst 学来的
        if mode == "split":
            return None                 # 水平分割：干脆不说
        if mode == "poison":
            return INF                  # 毒性逆转：明确告诉它「不可达」
    return metric


def step(state, mode):
    """同步一轮：所有节点先按旧状态通告，再各自重算到目的网段的最优路由。"""
    new = {}
    for v in NODES:
        if v == DIRECT:                 # 直连链路失效
            new[v] = (INF, "-")
            continue
        best = (INF, "-")
        for n in NEIGHBORS[v]:
            adv = advertise(n, v, state, mode)
            if adv is None:
                continue
            cand = adv + 1
            if cand >= INF:             # 度量到 16 即视为不可达，不装表
                continue
            if cand < best[0]:
                best = (cand, n)
        new[v] = best
    return new


def simulate(mode):
    """返回 (每轮状态列表, 收敛轮次)。状态列表[0] 为故障前，[1] 为故障后。"""
    state = dict(INITIAL)
    history = [dict(state)]
    state = step(state, mode)           # 故障发生的瞬间：R3 直连失效
    history.append(dict(state))
    converged_at = None
    for r in range(1, MAX_ROUNDS + 1):
        prev = state
        state = step(prev, mode)
        history.append(dict(state))
        if state == prev:               # 连续两轮无变化 = 收敛
            converged_at = r
            break
    return history, converged_at


def render(name, history, converged_at):
    print("=" * 78)
    print(f"场景：{name}")
    print("-" * 78)
    header = pad("阶段", 10) + "".join(pad(v + "(经)", 16) for v in NODES)
    print(header)
    labels = ["故障前", "故障后"] + [f"第 {i} 轮" for i in range(1, len(history) - 1)]
    for idx, st in enumerate(history):
        row = pad(labels[idx], 10)
        for v in NODES:
            m, nxt = st[v]
            m_txt = "不可达" if m >= INF else str(m)
            row += pad(f"{m_txt}({nxt})", 16)
        print(row)
    # 计算从「故障后」到全部不可达的轮数，并记录出现过的最大有限度量
    tail = [s for s in history[2:]]
    all_inf = None
    for i, s in enumerate(tail, start=1):
        if all(s[v][0] >= INF for v in NODES):
            all_inf = i
            break
    max_metric = 0
    for s in history[2:]:
        for v in NODES:
            m = s[v][0]
            if m < INF:
                max_metric = max(max_metric, m)
    print("-" * 78)
    if converged_at is None:
        print(f">>> 结论：{MAX_ROUNDS} 轮内仍未收敛（度量持续增长，典型的计数到无穷）")
    else:
        print(f">>> 结论：全部节点达成「不可达」用时 {all_inf} 轮；"
              f"过程中出现的最大有限度量为 {max_metric}")
    return all_inf or MAX_ROUNDS, max_metric


def main():
    print()
    print("RIP 距离矢量收敛演示 · 拓扑 R1 - R2 - R3 - R4，目的网段 192.0.2.0/24 直连 R3")
    print("链路开销均为 1，RIP 中度量 16 表示不可达；故障 = R3 到 192.0.2.0/24 的直连链路断开")
    print()
    results = {}
    for mode, name in MODES:
        history, converged_at = simulate(mode)
        results[name] = render(name, history, converged_at)
        print()

    print("=" * 78)
    print("三种机制对比")
    print("-" * 78)
    print(pad("机制", 28) + pad("收敛轮次", 12) + pad("最大有限度量", 16) + "计数到无穷")
    for mode, name in MODES:
        rounds, max_metric = results[name]
        countup = "是" if max_metric >= 5 else "否"
        print(pad(name, 28) + pad(str(rounds), 12) + pad(str(max_metric), 16) + countup)
    print("-" * 78)
    print("说明：水平分割能挡住「从哪学来就原路说回去」的 2 节点环路；")
    print("      但在长链上坏消息仍会一格格扩散，故工程上还要配合触发更新与抑制计时器。")
    print()
    print("小结：")
    print("1. 裸距离矢量在链路失效后，R1/R2 会互相引用对方的过期路由，度量 2→3→…→15 一路涨到 16。")
    print("   本场景从故障到整网不可达用了 15 轮，整个过程就是「计数到无穷」。")
    print("2. 水平分割让节点不再把从某邻居学来的路由原路说回去，本场景 2 轮即收敛，最大度量只有 2。")
    print("3. 毒性逆转把「不可达(16)」显式通告回来源邻居，本场景同样 2 轮收敛；两者效果等价，")
    print("   但毒性逆转不依赖对端「察觉沉默」，配合触发更新后在大网中更可靠。")
    print()


if __name__ == "__main__":
    main()
