#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构造 R1<->R2 互为下一跳的路由环路，观察 TTL 递减到 0 与 ICMP 超时；对比 null0 防环。

运行: python3 loop_and_ttl.py
"""
import sys

sys.dont_write_bytecode = True

DST = "198.51.100.5"          # 目标：PC2（198.51.100.0/24 内）
TTL_INIT = 64                 # 主机默认初始 TTL（Linux 为 64）
HOPS_CAP = 300                # 安全上限，防止死循环（>255 即可覆盖最大 TTL）

# 错误配置：R1 与 R2 互相把去往 198.51.100.0/24 的下一跳指向对方
ROUTES_LOOP = {
    "R1": {"203.0.113.1": "R1 G0/0", "198.51.100.0/24": ("203.0.113.2", "R2", "静态 → R2")},
    "R2": {"203.0.113.2": "R2 G0/0", "198.51.100.0/24": ("203.0.113.1", "R1", "静态 → R1（错误）")},
}

# 修复配置：R2 上把指回 R1 的错误路由改成指向 null0 的防环路由
ROUTES_NULL0 = {
    "R1": {"203.0.113.1": "R1 G0/0", "198.51.100.0/24": ("203.0.113.2", "R2", "静态 → R2")},
    "R2": {"203.0.113.2": "R2 G0/0", "198.51.100.0/24": ("null0", "-", "静态 → null0（防环）")},
}


def simulate(routes: dict, ttl_init: int, quiet: bool = False) -> dict:
    """逐跳模拟：每台路由器先 TTL 减 1，减到 0 丢弃并回 ICMP 超时。"""
    cur = "R1"                 # PC1 把包交给网关 R1
    ttl = ttl_init
    trace = []
    for _ in range(HOPS_CAP + 1):
        ttl -= 1
        trace.append((cur, ttl))
        if ttl == 0:
            return {"trace": trace, "result": "time_exceeded", "where": cur,
                    "latency_ms": len(trace) * 0.5}
        nh, nxt, why = routes[cur]["198.51.100.0/24"]
        if nxt == "-":         # null0：立即丢弃
            return {"trace": trace, "result": "unreachable", "where": cur,
                    "latency_ms": len(trace) * 0.5, "note": why}
        cur = nxt
    return {"trace": trace, "result": "cap", "where": cur, "latency_ms": 0.0}


def print_trace(title: str, res: dict) -> None:
    tr = res["trace"]
    print(f"{title}")
    print(f"  共经历 {len(tr)} 跳（每跳 TTL −1）：")
    show = list(tr) if len(tr) <= 16 else tr[:8] + [("...", -1)] + tr[-8:]
    for who, ttl in show:
        if who == "...":
            print(f"    ...（中间省略 {len(tr) - 16} 跳，均为 R1/R2 交替）...")
        else:
            print(f"    第 {tr.index((who, ttl)) + 1:>3} 跳：{who} 收到并递减，TTL 剩余 {ttl}")
    if res["result"] == "time_exceeded":
        print(f"  >>> 结果：{res['where']} 收到 TTL=1，递减为 0 → 丢弃报文，")
        print(f"            回 ICMP Time Exceeded（Type 11, Code 0）给源地址，报文未到达 {DST}")
    elif res["result"] == "unreachable":
        print(f"  >>> 结果：{res['where']} 命中 null0 路由 → 立即丢弃，")
        print(f"            回 ICMP Destination Unreachable（Type 3, Code 1），只用了 {len(tr)} 跳")
    print(f"  往返时延估算：{res['latency_ms']:.1f} ms（按 0.5ms/跳 粗算，仅用于对比）")
    print()


def self_check() -> None:
    r1 = simulate(ROUTES_LOOP, TTL_INIT)
    assert r1["result"] == "time_exceeded"
    assert len(r1["trace"]) == TTL_INIT, len(r1["trace"])       # 64 跳后归零
    assert r1["trace"][0] == ("R1", 63)
    assert r1["trace"][-1][1] == 0
    # R1/R2 严格交替
    for i, (who, _t) in enumerate(r1["trace"]):
        assert who == ("R1" if i % 2 == 0 else "R2"), (i, who)
    r2 = simulate(ROUTES_NULL0, TTL_INIT)
    assert r2["result"] == "unreachable" and len(r2["trace"]) == 2
    # TTL 初值越大，环路消耗的跳数越多
    r3 = simulate(ROUTES_LOOP, 255)
    assert len(r3["trace"]) == 255


def main() -> int:
    self_check()
    print("=" * 92)
    print("路由环路与 TTL 演示（教学模拟，未发起任何真实流量）")
    print("=" * 92)
    print("拓扑：PC1(192.0.2.10) ── R1 ══ 203.0.113.0/30 ══ R2      目标 PC2(198.51.100.5)")
    print("错误配置：")
    print("  R1: ip route 198.51.100.0 255.255.255.0 203.0.113.2   (指向 R2)")
    print("  R2: ip route 198.51.100.0 255.255.255.0 203.0.113.1   (又指回 R1 ← 成环)")
    print("-" * 92)
    print("R1 路由表：198.51.100.0/24 → 203.0.113.2 (R2)")
    print("R2 路由表：198.51.100.0/24 → 203.0.113.1 (R1)")
    print(f"PC1 发出的报文初始 TTL = {TTL_INIT}")
    print()
    print("=" * 92)
    print("场景 A：环路未修 —— TTL 逐跳递减到 0")
    print("=" * 92)
    print_trace("报文在 R1 与 R2 之间来回转发：", simulate(ROUTES_LOOP, TTL_INIT))
    print("=" * 92)
    print("场景 B：在 R2 上把错误路由改成指向 null0 的防环路由")
    print("=" * 92)
    print("  R2: ip route 198.51.100.0 255.255.255.0 null0")
    print_trace("报文行为：", simulate(ROUTES_NULL0, TTL_INIT))
    print("=" * 92)
    print("对比")
    print("=" * 92)
    a = simulate(ROUTES_LOOP, TTL_INIT)
    b = simulate(ROUTES_NULL0, TTL_INIT)
    print(f"  环路场景  ：{len(a['trace'])} 跳，{a['latency_ms']:.1f} ms，报文被 TTL 耗尽丢弃，"
          f"回 ICMP Type 11")
    print(f"  null0 场景：{len(b['trace'])} 跳，{b['latency_ms']:.1f} ms，报文立即被丢弃，"
          f"回 ICMP Type 3")
    print(f"  >>> 结论：同样收不到响应，环路吃掉了 {len(a['trace'])} 跳的转发资源与 "
          f"{(len(a['trace']) - len(b['trace'])) * 0.5:.1f} ms 的时延。")
    print()
    print("traceroute 上会看到什么：")
    print("  1  R1 (203.0.113.1)   1 ms")
    print("  2  R2 (203.0.113.2)   2 ms")
    print("  3  R1 (203.0.113.1)   2 ms   ← 同一地址反复出现，是环路的典型特征")
    print("  4  R2 (203.0.113.2)   3 ms")
    print("  ... 持续到第 30 跳仍不收敛 → 判定为环路")
    print()
    print("=" * 92)
    print("防环手段（按优先级）")
    print("=" * 92)
    print("  1. 修正下一跳：让 R2 指向真正的下游（正解，最彻底）。")
    print("  2. null0 防环路由：在汇总路由的始发设备上配 `ip route <汇总> null0`，")
    print("     让命中汇总但没有明细的流量被立即丢弃，而不是被默认/更短前缀路由送回上游。")
    print("  3. 动态路由协议自带防环：OSPF 靠 SPF 计算无环拓扑，BGP 靠 AS_PATH 拒绝含本 AS 的路由。")
    print("  4. 静态路由场景可配 BFD/接口联动，故障时快速撤销路由，减少环路窗口。")
    print("  5. 排障时先用 `traceroute` 看地址是否重复，再用 `show ip route <目的>` 找互相指向。")
    print()
    print("小结")
    print("  1. TTL 是 IP 层的最后防线：环路不会被永远转发，但会消耗完 TTL 才停。")
    print("  2. 环路的表现是 traceroute 里地址反复出现 + 高时延 + 目的不可达。")
    print("  3. null0 不能修好转发，但能把「绕满 TTL」变成「立即丢弃」，是聚合场景的标准防环手段。")
    print("  4. 真正修环路永远是改对下一跳，null0 只是兜底。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
