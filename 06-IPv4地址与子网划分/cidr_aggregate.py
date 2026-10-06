#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CIDR 路由聚合：把一组连续网段合并成最少的 CIDR 前缀，并给出条目节省率。

运行: python3 cidr_aggregate.py
"""
import ipaddress
import sys

sys.dont_write_bytecode = True

INPUT = [
    "192.0.2.0/26", "192.0.2.64/26", "192.0.2.128/26", "192.0.2.192/26",
    "198.51.100.0/25", "198.51.100.128/25",
    "203.0.113.0/27", "203.0.113.32/27", "203.0.113.64/26", "203.0.113.128/25",
]


def manual_aggregate(nets) -> tuple:
    """手工聚合算法：反复把「同一父网下的两个兄弟 /(p-1)」合并，直到无法再合并。

    返回 (聚合结果列表, 每一轮的合并轨迹)。
    """
    work = sorted({ipaddress.ip_network(n) for n in nets},
                  key=lambda n: (int(n.network_address), n.prefixlen))
    rounds = []
    changed = True
    while changed:
        changed = False
        out = []
        trace = []
        i = 0
        while i < len(work):
            merged = False
            if i + 1 < len(work):
                a, b = work[i], work[i + 1]
                # 兄弟判定：同前缀长度，且 b.network = a.network + 2^(32-p)
                if a.prefixlen == b.prefixlen and a.prefixlen > 0:
                    step = 1 << (32 - a.prefixlen)
                    if int(b.network_address) == int(a.network_address) + step:
                        parent = a.supernet()
                        out.append(parent)
                        trace.append(f"{a} + {b}  → {parent}")
                        i += 2
                        merged = True
                        changed = True
            if not merged:
                out.append(work[i])
                i += 1
        if trace:
            rounds.append(trace)
        work = sorted(out, key=lambda n: (int(n.network_address), n.prefixlen))
    return work, rounds


def main() -> int:
    nets = [ipaddress.ip_network(n) for n in INPUT]
    mine, rounds = manual_aggregate(nets)
    ref = sorted(ipaddress.collapse_addresses(nets),
                 key=lambda n: int(n.network_address))
    # 自校验：手工算法结果必须与标准库一致
    assert [str(n) for n in mine] == [str(n) for n in ref], (mine, ref)

    print("=" * 78)
    print("CIDR 路由聚合（超网 / Supernetting）演示")
    print("=" * 78)
    print(f"聚合前明细路由 {len(nets)} 条：")
    for n in sorted(nets, key=lambda x: int(x.network_address)):
        print(f"  {str(n):<20} 覆盖 {n.num_addresses:>3} 个地址")
    print("-" * 78)
    print(f"聚合后路由 {len(ref)} 条：")
    for n in ref:
        print(f"  {str(n):<20} 覆盖 {n.num_addresses:>3} 个地址")
    print("-" * 78)
    saved = len(nets) - len(ref)
    print(f"条目节省：{len(nets)} → {len(ref)}，减少 {saved} 条（节省率 {saved / len(nets) * 100:.1f}%）")
    print()
    print("聚合过程（手工算法的合并轨迹，等价于标准库 collapse_addresses）：")
    for k, trace in enumerate(rounds, 1):
        print(f"  第 {k} 轮：")
        for line in trace:
            print(f"    {line}")
    print()
    print("合并条件（必须同时满足，缺一不可）：")
    print("  ① 两个前缀长度相同 p；")
    print("  ② 网络地址相差恰好 2^(32−p)（即同一个 /(p−1) 父网的左右两半）；")
    print("  ③ 合并后前缀 /(p−1)，覆盖地址数为原来的 2 倍。")
    print(">>> 结论：10 条明细路由可聚合成 3 条，核心路由器 FIB 与协议更新开销同步降 70%。")
    print(">>> 结论：聚合只能覆盖「连续且对齐」的地址块；一旦中间有缺口，聚合就会把缺口也宣告出去。")
    print()
    print("聚合的代价（路由黑洞演示）：")
    print("  若 203.0.113.0/24 内部其实只用了一部分、还有未分配的地址，")
    print("  一旦把 203.0.113.0/24 整条宣告出去，发往未使用地址的流量就会打到本网后被丢弃，")
    print("  形成「黑洞」。规避办法：宣告聚合路由时同时配置指向 null0 的防环路由，")
    print("  或只宣告真实在用的明细前缀。")
    print()
    print("小结")
    print("  1. 聚合的本质是「兄弟合并」：同长度、地址差一个块大小，就能并成父网。")
    print("  2. 聚合降低路由表规模与协议收敛开销，但要求地址块连续且按 2 的幂对齐。")
    print("  3. 有缺口时聚合会引入黑洞，必须配合明细路由或 null0 防环来兜底。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
