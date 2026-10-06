#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最长前缀匹配查表：给一张含重叠前缀的路由表，输入目的 IP，逐条比较并解释命中原因。

运行: python3 route_lookup.py            # 跑内置用例集
     python3 route_lookup.py 192.0.2.130
"""
import ipaddress
import sys

sys.dont_write_bytecode = True

# (目的网络, 下一跳, 出接口, 管理距离AD, 度量值, 来源)
ROUTES = [
    ("0.0.0.0/0",         "203.0.113.1", "G0/0", 1,   0,   "静态默认路由"),
    ("10.0.0.0/8",        "203.0.113.7", "G0/0", 1,   0,   "静态"),
    ("192.0.2.0/24",      "direct",      "G0/1", 0,   0,   "直连"),
    ("192.0.2.0/25",      "203.0.113.2", "G0/0", 1,   0,   "静态"),
    ("192.0.2.128/25",    "203.0.113.3", "G0/0", 1,   0,   "静态"),
    ("192.0.2.64/26",     "203.0.113.4", "G0/0", 1,   0,   "静态"),
    ("192.0.2.64/26",     "203.0.113.5", "G0/0", 110, 20,  "OSPF"),
    ("198.51.100.0/24",   "203.0.113.6", "G0/0", 1,   0,   "静态"),
    ("198.51.100.0/24",   "203.0.113.8", "G0/0", 1,   0,   "静态（等价路由）"),
    ("203.0.113.0/24",    "direct",      "G0/0", 0,   0,   "直连"),
]

# 用例：(目的 IP, 期望胜出前缀, 期望下一跳)
CASES = [
    ("192.0.2.130", "192.0.2.128/25", "203.0.113.3"),
    ("192.0.2.70",  "192.0.2.64/26",  "203.0.113.4"),
    ("192.0.2.10",  "192.0.2.0/25",   "203.0.113.2"),
    ("192.0.2.200", "192.0.2.128/25", "203.0.113.3"),
    ("198.51.100.5", "198.51.100.0/24", "203.0.113.6"),
    ("10.1.2.3",    "10.0.0.0/8",     "203.0.113.7"),
    ("203.0.113.9", "203.0.113.0/24", "direct"),
    ("198.18.0.1",  "0.0.0.0/0",      "203.0.113.1"),
]


def matches(dst: ipaddress.IPv4Address) -> list:
    """返回所有匹配该目的地址的路由（含解析出的掩码与前缀长度）。"""
    out = []
    for net_s, nh, iface, ad, metric, src in ROUTES:
        net = ipaddress.ip_network(net_s)
        if dst in net:
            out.append({
                "net": net, "prefix": net.prefixlen, "nexthop": nh,
                "iface": iface, "ad": ad, "metric": metric, "src": src,
            })
    return out


def lookup(dst_s: str) -> dict:
    """实现最长前缀匹配：① 前缀最长者胜 ② 同长度比 AD 小 ③ 再比度量小。"""
    dst = ipaddress.ip_address(dst_s)
    cands = matches(dst)
    cands.sort(key=lambda r: (-r["prefix"], r["ad"], r["metric"]))
    return {"dst": dst, "candidates": cands,
            "winner": cands[0] if cands else None,
            "equal_cost": [r for r in cands
                           if cands and (r["prefix"], r["ad"], r["metric"])
                           == (cands[0]["prefix"], cands[0]["ad"], cands[0]["metric"])]}


def explain(dst_s: str) -> None:
    res = lookup(dst_s)
    dst, cands, winner = res["dst"], res["candidates"], res["winner"]
    print(f"目的地址：{dst}   （二进制 {'.'.join(format(b, '08b') for b in dst.packed)}）")
    if not winner:
        print("  无任何匹配路由 → 丢弃并回 ICMP 网络不可达")
        return
    print(f"  匹配到的候选路由共 {len(cands)} 条（按「前缀长→AD→度量」排序后逐条说明）：")
    for i, r in enumerate(cands):
        why = ">>> 胜出（最长前缀优先）" if i == 0 else "淘汰："
        if i > 0:
            if r["prefix"] < winner["prefix"]:
                why += f"前缀 /{r['prefix']} 短于胜出的 /{winner['prefix']}"
            elif r["ad"] > winner["ad"]:
                why += f"前缀相同但 AD {r['ad']} 大于 {winner['ad']}"
            else:
                why += f"前缀与 AD 相同但度量 {r['metric']} 大于 {winner['metric']}"
        print(f"    [{'命中' if i == 0 else '落选'}] /{r['prefix']:<2} "
              f"{str(r['net']):<18} 下一跳={r['nexthop']:<14} AD={r['ad']:<4}"
              f"度量={r['metric']:<3} 来源={r['src']}  {why}")
    nh = winner["nexthop"]
    if nh == "direct":
        print(f"  >>> 命中：{winner['net']} 是直连路由，")
        print(f"      直接 ARP 目的地址后二层转发（出接口 {winner['iface']}）")
    else:
        print(f"  >>> 命中：最长前缀 {winner['net']}，下一跳 {nh}，出接口 {winner['iface']}")
    if len(res["equal_cost"]) > 1:
        hops = "、".join(r["nexthop"] for r in res["equal_cost"])
        print(f"  >>> 等价路由：{len(res['equal_cost'])} 条同前缀/同 AD/同度量 → {hops}")
        print(f"      路由器按五元组哈希在成员间分担流量（单条会话仍走同一条）")


def self_check() -> None:
    for dst, expect_net, expect_nh in CASES:
        w = lookup(dst)["winner"]
        assert w is not None, dst
        assert str(w["net"]) == expect_net, f"{dst} 期望 {expect_net} 实得 {w['net']}"
        assert w["nexthop"] == expect_nh, f"{dst} 期望 {expect_nh} 实得 {w['nexthop']}"
    # 同前缀长度比 AD：192.0.2.70 同时命中静态(AD1)与 OSPF(AD110) 的 /26
    cands = matches(ipaddress.ip_address("192.0.2.70"))
    same_prefix = [c for c in cands if c["prefix"] == 26]
    assert len(same_prefix) == 2
    assert min(same_prefix, key=lambda c: c["ad"])["nexthop"] == "203.0.113.4"
    # 等价路由：198.51.100.0/24 有两条同 AD 同度量
    assert len(lookup("198.51.100.5")["equal_cost"]) == 2


def main() -> int:
    self_check()
    print("=" * 96)
    print("最长前缀匹配（Longest Prefix Match）查表演示")
    print("=" * 96)
    print("路由表（含重叠前缀，用于演示匹配优先级）：")
    print("-" * 96)
    print(f"{'目的网络':<20}{'下一跳':<16}{'接口':<8}{'AD':>4}{'度量':>6}  来源")
    print("-" * 96)
    for net_s, nh, iface, ad, metric, src in ROUTES:
        print(f"{net_s:<20}{nh:<16}{iface:<8}{ad:>4}{metric:>6}  {src}")
    print("-" * 96)
    print()
    for dst, expect_net, _nh in CASES:
        print("=" * 96)
        explain(dst)
        print(f"  （内置断言：期望命中 {expect_net}）")
        print()

    print("=" * 96)
    print("匹配优先级三步（RFC 无规定，各厂商一致实现）")
    print("=" * 96)
    print("  第 1 步：最长前缀优先 —— 前缀越长越具体，与 AD、度量无关。")
    print("  第 2 步：前缀长度相同时比管理距离（AD）—— 数字越小越可信。")
    print("           直连 0 < 静态 1 < eBGP 20 < EIGRP 90 < OSPF 110 < RIP 120 < iBGP 200")
    print("  第 3 步：前缀与 AD 都相同时比度量（Metric）—— 各协议自己定义。")
    print("           若三项全同 → 等价路由，按哈希做负载分担。")
    print()
    print(">>> 结论：192.0.2.130 命中的是 /25 而不是 /24，说明「具体优先」压过「直连优先」。")
    print(">>> 结论：192.0.2.70 有两条 /26，AD 1 的静态挤掉了 AD 110 的 OSPF。")
    print(">>> 结论：198.51.100.5 两条路由三项全同 → 等价路由，可做负载分担。")
    print()
    print("小结")
    print("  1. 查表顺序固定：最长前缀 → 最小 AD → 最小度量 → 哈希分担。")
    print("  2. 直连路由不一定赢：只要存在更长前缀的静态/动态路由，就会盖过直连。")
    print("  3. AD 只在「同前缀长度」时才参与比较，它的作用是跨协议选可信来源。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
