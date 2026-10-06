#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态 / 默认 / 浮动静态路由生成与主链路故障切换模拟（3 路由 + 2 主机三角拓扑）。

运行: python3 static_route_gen.py
"""
import ipaddress
import sys

sys.dont_write_bytecode = True

# 链路：(链路名, A 端设备, A 端接口, A 端地址, B 端设备, B 端接口, B 端地址)
LINKS = [
    ("L12", "R1", "G0/0", "203.0.113.1/30", "R2", "G0/0", "203.0.113.2/30"),
    ("L23", "R2", "G0/1", "203.0.113.5/30", "R3", "G0/0", "203.0.113.6/30"),
    ("L13", "R1", "G0/2", "203.0.113.9/30", "R3", "G0/2", "203.0.113.10/30"),
]

# 各路由器 LAN：(网段, 网关地址, 出接口, 主机)
LANS = {
    "R1": ("192.0.2.0/24", "192.0.2.1", "G0/1", "PC1(192.0.2.10)"),
    "R3": ("198.51.100.0/24", "198.51.100.1", "G0/1", "PC2(198.51.100.10)"),
}

# 静态路由：(路由器, 目的前缀, 下一跳, AD/Preference, 用途说明)
STATICS = [
    ("R1", "0.0.0.0/0", "203.0.113.2", 1, "主默认路由 → R2"),
    ("R1", "0.0.0.0/0", "203.0.113.10", 10, "浮动默认路由 → R3"),
    ("R1", "198.51.100.0/24", "203.0.113.2", 1, "到 PC2 网段，主 → R2"),
    ("R1", "198.51.100.0/24", "203.0.113.10", 10, "到 PC2 网段，浮动 → R3"),
    ("R1", "203.0.113.4/30", "203.0.113.2", 1, "到 R2-R3 互联段，主 → R2"),
    ("R1", "203.0.113.4/30", "203.0.113.10", 10, "到 R2-R3 互联段，浮动 → R3"),
    ("R2", "192.0.2.0/24", "203.0.113.1", 1, "到 PC1 网段 → R1"),
    ("R2", "198.51.100.0/24", "203.0.113.6", 1, "到 PC2 网段 → R3"),
    ("R3", "192.0.2.0/24", "203.0.113.5", 1, "到 PC1 网段，主 → R2"),
    ("R3", "192.0.2.0/24", "203.0.113.9", 10, "到 PC1 网段，浮动 → R1"),
    ("R3", "203.0.113.0/30", "203.0.113.5", 1, "到 R1-R2 互联段，主 → R2"),
    ("R3", "203.0.113.0/30", "203.0.113.9", 10, "到 R1-R2 互联段，浮动 → R1"),
]

# 下一跳 → 承载它的链路（用于判定「下一跳是否可达」）
NEXTHOP_LINK = {
    "203.0.113.1": "L12", "203.0.113.2": "L12",
    "203.0.113.5": "L23", "203.0.113.6": "L23",
    "203.0.113.9": "L13", "203.0.113.10": "L13",
}


def direct_entries(router: str) -> list:
    """返回 [(网段, 出接口, 承载链路或 None), ...]，None 表示 LAN（永不 down）。"""
    out = []
    if router in LANS:
        net, _ip, iface, _who = LANS[router]
        out.append((net, iface, None))
    for ln, ra, ia, ad, rb, ib, bd in LINKS:
        if ra == router:
            out.append((str(ipaddress.ip_network(ad, strict=False)), ia, ln))
        if rb == router:
            out.append((str(ipaddress.ip_network(bd, strict=False)), ib, ln))
    return out


def direct_nets(router: str) -> dict:
    return {n: i for n, i, _l in direct_entries(router)}


def iface_for_nexthop(router: str, nh: str) -> str:
    for n, iface, _l in direct_entries(router):
        if ipaddress.ip_address(nh) in ipaddress.ip_network(n):
            return iface
    return "-"


def resolve(router: str, dst: str, down: set) -> dict:
    """查表：直连 + 静态（跳过下一跳不可达者），取最长前缀 + 最小 AD。"""
    d = ipaddress.ip_address(dst)
    cands = []
    for net_s, iface, link in direct_entries(router):
        if d not in ipaddress.ip_network(net_s):
            continue
        inactive = bool(link and link in down)
        cands.append({"net": net_s, "nh": "direct", "iface": iface, "ad": 0,
                      "why": "直连" if not inactive else f"直连，但链路 {link} down",
                      "inactive": inactive})
    for r, net_s, nh, ad, note in STATICS:
        if r != router or d not in ipaddress.ip_network(net_s):
            continue
        link = NEXTHOP_LINK.get(nh)
        if link and link in down:
            cands.append({"net": net_s, "nh": nh, "iface": "-", "ad": ad,
                          "why": f"{note}｜下一跳不可达（{link} down）", "inactive": True})
            continue
        cands.append({"net": net_s, "nh": nh, "iface": iface_for_nexthop(router, nh),
                      "ad": ad, "why": note, "inactive": False})
    active = [c for c in cands if not c.get("inactive")]
    active.sort(key=lambda c: (-ipaddress.ip_network(c["net"]).prefixlen, c["ad"]))
    return {"all": cands, "best": active[0] if active else None,
            "backup": active[1] if len(active) > 1 else None}


def cisco_cfg(router: str) -> list:
    out = []
    for r, net_s, nh, ad, _note in STATICS:
        if r != router:
            continue
        net = ipaddress.ip_network(net_s)
        extra = "" if ad == 1 else f" {ad}"
        out.append(f"ip route {net.network_address} {net.netmask} {nh}{extra}")
    return out


def huawei_cfg(router: str) -> list:
    out = []
    for r, net_s, nh, ad, _note in STATICS:
        if r != router:
            continue
        net = ipaddress.ip_network(net_s)
        extra = "" if ad == 1 else f" preference {ad}"
        out.append(f"ip route-static {net.network_address} {net.prefixlen} {nh}{extra}")
    return out


def self_check() -> None:
    b = resolve("R1", "198.51.100.10", set())["best"]
    assert b["nh"] == "203.0.113.2" and b["ad"] == 1, b
    b = resolve("R1", "198.51.100.10", {"L12"})["best"]
    assert b["nh"] == "203.0.113.10" and b["ad"] == 10, b
    # 仅 L12 down 时，R3 的下一跳 203.0.113.5 仍走 L23（up），所以 R3 不切换 → 会单通
    b = resolve("R3", "192.0.2.10", {"L12"})["best"]
    assert b["nh"] == "203.0.113.5" and b["ad"] == 1, b
    # L12 与 L23 同时 down（R2 被隔离）时，R3 才切到浮动静态
    b = resolve("R3", "192.0.2.10", {"L12", "L23"})["best"]
    assert b["nh"] == "203.0.113.9" and b["ad"] == 10, b
    assert resolve("R1", "192.0.2.10", {"L12", "L13"})["best"]["nh"] == "direct"
    # 链路 down 后该直连网段失效，目的地址落到默认路由
    r = resolve("R1", "203.0.113.2", {"L12"})
    assert any(c["nh"] == "direct" and c.get("inactive") for c in r["all"])
    assert r["best"]["nh"] == "203.0.113.10", r["best"]
    assert direct_nets("R1")["203.0.113.0/30"] == "G0/0"
    assert direct_nets("R3")["203.0.113.8/30"] == "G0/2"


def show_fib(router: str, dst: str, down: set) -> None:
    res = resolve(router, dst, down)
    state = "、".join(sorted(down)) if down else "全部链路 up"
    print(f"  {router} 路由表（到 {dst}，链路状态：{state}）")
    for c in res["all"]:
        flag = "失效" if c.get("inactive") else "可用"
        star = " <<< 选中" if res["best"] is c else ""
        net = ipaddress.ip_network(c["net"])
        print(f"    [{flag}] /{net.prefixlen:<2} {c['net']:<18} 下一跳={c['nh']:<14}"
              f" AD={c['ad']:<3} 出接口={c['iface']:<6} {c['why']}{star}")
    if res["best"] is None:
        print("    >>> 无可用路由：报文被丢弃并回 ICMP 网络不可达")
    print()


def main() -> int:
    self_check()
    print("=" * 94)
    print("静态路由生成与浮动静态切换模拟（PC1—R1—R2—R3—PC2，另有 R1—R3 备用直连）")
    print("=" * 94)
    print("拓扑：")
    print("     192.0.2.0/24        203.0.113.0/30        203.0.113.4/30       198.51.100.0/24")
    print("  PC1 ───── R1 ── L12 ── R2 ── L23 ── R3 ───── PC2")
    print("             └──────── L13 (203.0.113.8/30) ────────┘   ← 备用路径")
    print("-" * 94)
    for ln, ra, ia, ad, rb, ib, bd in LINKS:
        print(f"  {ln}: {ra} {ia} {ad:<18} <->  {rb} {ib} {bd}")
    print(f"  LAN: R1 {LANS['R1'][0]} 网关 {LANS['R1'][1]} ({LANS['R1'][3]})")
    print(f"       R3 {LANS['R3'][0]} 网关 {LANS['R3'][1]} ({LANS['R3'][3]})")
    print()
    print("=" * 94)
    print("生成的静态路由配置")
    print("=" * 94)
    for r in ("R1", "R2", "R3"):
        print(f"{r}（Cisco 风格）：")
        for line in cisco_cfg(r):
            print(f"    {line}")
        print(f"{r}（华为风格）：")
        for line in huawei_cfg(r):
            print(f"    {line}")
        print(f"    ! 浮动静态：主路由 AD=1，备份路由 AD=10，AD 小者优先")
        print("-" * 94)
    print("  说明：Cisco 把 AD 写在命令行末尾；华为用 `preference` 关键字，语义完全相同。")
    print()
    print("=" * 94)
    print("场景 1：全部链路 up —— 主路由生效")
    print("=" * 94)
    show_fib("R1", "198.51.100.10", set())
    print("  数据面路径：PC1 → R1 →(L12) R2 →(L23) R3 → PC2")
    print()
    print("=" * 94)
    print("场景 2：仅 L12 故障 down —— R1 切到浮动静态，但 R3 不切 → 单通")
    print("=" * 94)
    show_fib("R1", "198.51.100.10", {"L12"})
    show_fib("R3", "192.0.2.10", {"L12"})
    print("  去程（PC1 → PC2）：PC1 → R1 →(L13) R3 → PC2      ← R1 已切换，能到")
    print("  回程（PC2 → PC1）：PC2 → R3 →(L23) R2 →(L12 断) ✗  ← R3 的下一跳仍可达，没切")
    print("  >>> 这正是「浮动静态只感知直连下一跳」的典型坑：R3 认为 203.0.113.5 还活着，")
    print("      于是继续用主路由把包交给 R2，而 R2 到 PC1 的 L12 已经断了 → 回程被丢。")
    print("  这就是典型的单通（去程通、回程断），用户表现为「能 ping 出去、ping 不回来」。")
    print()
    print("=" * 94)
    print("场景 3：L12 与 L23 同时 down（R2 被隔离）—— 两端都切换，恢复全通")
    print("=" * 94)
    show_fib("R1", "198.51.100.10", {"L12", "L23"})
    show_fib("R3", "192.0.2.10", {"L12", "L23"})
    print("  数据面路径：PC1 → R1 →(L13) R3 → PC2（去程回程都走 L13，全通）")
    print()
    print("=" * 94)
    print("收敛时序（以 R1 为例）")
    print("=" * 94)
    print("  T+0s   : L12 物理 down，接口变为 down/down")
    print("  T+0s   : 下一跳 203.0.113.2 不可达，经 L12 的静态路由被撤销")
    print("  T+0s~  : FIB 重算，浮动静态（AD 10，经 L13）装入，转发恢复")
    print("  恢复后 : L12 重新 up，AD=1 的主路由自动抢占回主路径")
    print("  >>> 结论：纯静态切换由「下一跳可达性」驱动，没有协议计时器，通常在毫秒级完成。")
    print("  >>> 结论：浮动静态只能感知链路/接口故障；远端设备故障时下一跳仍可达，不会切换。")
    print()
    print("小结")
    print("  1. 主路由 AD=1、浮动静态 AD=10，靠「AD 小者优先」实现备份切换。")
    print("  2. 浮动静态靠下一跳可达性触发，无法感知远端设备故障，需 BFD/动态路由补齐。")
    print("  3. 只配单端浮动静态会出现「去程通、回程断」的单通，两端都要配。")
    print("  4. 华为的 preference 与 Cisco 的 AD 是同一概念，命令关键字不同而已。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
