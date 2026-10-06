#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPv4 组播地址到 MAC 的映射（低 23 位 + 01:00:5E）与 32:1 重叠、IGMP 版本差异演示。

运行: python3 multicast_mapping.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


def ip_to_int(ip):
    a, b, c, d = (int(x) for x in ip.split("."))
    return (a << 24) | (b << 16) | (c << 8) | d


def int_to_ip(v):
    return ".".join(str((v >> s) & 0xFF) for s in (24, 16, 8, 0))


def bits(v, n=32):
    return format(v, f"0{n}b")


def dotted_bits(v):
    b = bits(v)
    return ".".join(b[i:i + 8] for i in range(0, 32, 8))


DROP_MASK = 0x0F800000      # 被丢弃的高 5 位（28 位组播组号里的高 5 位）
KEEP_MASK = 0x007FFFFF      # 保留的低 23 位


def mac_of(ip):
    """组播 IP → MAC：固定 01:00:5E + 低 23 位。"""
    v = ip_to_int(ip)
    low23 = v & KEEP_MASK
    return (0x01005E000000 | low23), low23


def mac_str(m):
    return ":".join(f"{(m >> s) & 0xFF:02X}" for s in (40, 32, 24, 16, 8, 0))


def collision_partners(ip):
    """所有与 ip 映射到同一 MAC 的合法组播地址（限定在 224.0.0.0/4 内）。"""
    base = ip_to_int(ip) & ~DROP_MASK
    out = []
    for k in range(32):
        cand = base | (k << 23)
        if 0xE0000000 <= cand <= 0xEFFFFFFF:
            out.append(int_to_ip(cand))
    return out


WELL_KNOWN = [
    ("224.0.0.0", "基础地址（保留，不分配给任何组）"),
    ("224.0.0.1", "所有主机与路由器（本网段全主机）"),
    ("224.0.0.2", "所有路由器（本网段全路由器）"),
    ("224.0.0.4", "DVMRP 路由器"),
    ("224.0.0.5", "所有 OSPF 路由器（AllSPFRouters）"),
    ("224.0.0.6", "所有 OSPF DR/BDR（AllDRouters）"),
    ("224.0.0.9", "RIPv2 路由器"),
    ("224.0.0.10", "EIGRP 路由器"),
    ("224.0.0.13", "所有 PIM 路由器"),
    ("224.0.0.18", "VRRP 通告地址"),
    ("224.0.1.1", "NTP（网络时间协议，已被 224.0.1.1 之外的地址取代，仍广泛流传）"),
    ("224.0.1.39/40", "Cisco-RP-Announce / Discover"),
    ("239.0.0.0/8", "私用组播地址段（类似私网 IP，仅限本地域使用）"),
]


def main():
    print()
    print("IPv4 组播地址 → MAC 映射演示 · 规则：固定前缀 01:00:5E + 组播 IP 的低 23 位")
    print()

    print("=" * 96)
    print("一、映射规则与逐位推导（以 224.0.1.1 为例）")
    print("-" * 96)
    ip = "224.0.1.1"
    v = ip_to_int(ip)
    m, low23 = mac_of(ip)
    b23 = bits(low23, 23)
    b24 = "0" + b23
    print(f"组播 IP  {ip:<16} = {dotted_bits(v)}")
    print(f"丢弃高 5 位        =       {bits((v & DROP_MASK) >> 23, 5)}"
          f"（这 5 位在 MAC 里没有对应位置，正是重叠的根源）")
    print(f"保留低 23 位       = 0 {b23[0:7]}.{b23[7:15]}.{b23[15:23]}  (0x{low23:06X})")
    print(f"MAC 前缀  01:00:5E = 00000001.00000000.01011110")
    print(f"拼接后            = 00000001.00000000.01011110."
          f"{b24[0:8]}.{b24[8:16]}.{b24[16:24]}")
    print(f"最终 MAC          = {mac_str(m)}")
    print("-" * 96)
    print(">>> 结论：MAC 地址只有 23 位可用给组播，而 IPv4 组播组号有 28 位，")
    print("    丢掉 5 位后最多 2^5 = 32 个不同的组会映射到同一个 MAC，")
    print("    这就是「32:1 地址重叠」，主机侧必须靠 IP 层再做一次过滤。")
    print()

    print("=" * 96)
    print("二、常用组播地址的映射结果")
    print("-" * 96)
    print(pad("组播 IP", 16) + pad("二进制（低 23 位）", 26) + pad("MAC 地址", 22) + "共享该 MAC 的组数")
    for a, _ in WELL_KNOWN[:10]:
        mm, l23 = mac_of(a)
        n = len(collision_partners(a))
        print(pad(a, 16) + pad(bits(l23, 23), 26) + pad(mac_str(mm), 22) + str(n))
    print("-" * 96)
    print(">>> 结论：224.0.0.5 与 224.0.0.6（OSPF 的两个地址）映射到不同的 MAC，")
    print("    交换机可以分别转发；但 224.0.0.x 各组的 MAC 非常接近，抓包时要靠 IP 区分。")
    print()

    print("=" * 96)
    print("三、地址重叠演示：到底哪两个组会撞到同一个 MAC")
    print("-" * 96)
    a1, a2 = "224.0.1.1", "239.1.1.1"
    m1, _ = mac_of(a1)
    m2, _ = mac_of(a2)
    print(f"{a1:<12} → {mac_str(m1)}")
    print(f"{a2:<12} → {mac_str(m2)}")
    print(f"两者是否相同：{'相同' if m1 == m2 else '不同'}")
    print("-" * 96)
    print("常见误解：认为 224.0.1.1 与 239.1.1.1 会映射到同一个 MAC。这是错的 ——")
    print("  224.0.1.1 低 23 位 = 0x000101 → MAC 01:00:5E:00:01:01")
    print("  239.1.1.1 低 23 位 = 0x010101 → MAC 01:00:5E:01:01:01")
    print("真正会撞的是「低 23 位相同、被丢弃的 5 位不同」的两组，例如：")
    print(f"  224.0.1.1   与  224.128.1.1  → 都映射到 {mac_str(mac_of('224.0.1.1')[0])}")
    print()
    print(f"{a1} 的全部 {len(collision_partners(a1))} 个共享 MAC 的组：")
    partners = collision_partners(a1)
    for i in range(0, len(partners), 4):
        print("    " + "  ".join(pad(p, 18) for p in partners[i:i + 4]))
    print()
    print(f"{a2} 的共享组（同样是 {len(collision_partners(a2))} 个）：")
    partners2 = collision_partners(a2)
    for i in range(0, len(partners2), 4):
        print("    " + "  ".join(pad(p, 18) for p in partners2[i:i + 4]))
    print("  说明：组播地址段 224.0.0.0/4 共 2^28 个地址，恰好被 2^5 整除，")
    print("  因此映射是严格的 32:1 —— 每个组播 MAC 恒定对应 32 个组，没有边界例外。")
    print("  224.0.1.1 与 239.1.1.1 虽然不撞，但各自的 32 个碰撞组里都包含对方所在集合的成员。")
    print()

    print("=" * 96)
    print("四、IGMP v1 / v2 / v3 行为差异")
    print("-" * 96)
    print(pad("对比项", 24) + pad("IGMPv1", 26) + pad("IGMPv2", 26) + "IGMPv3")
    rows = [
        ("RFC", "1112", "2236", "3376"),
        ("加入报文", "0x12 Membership Report", "0x12 Membership Report", "0x22 v3 Report"),
        ("离开机制", "无（靠超时）", "0x16 Leave Group", "0x22（含 CHANGE_TO_INCLUDE）"),
        ("查询类型", "仅通用查询 0x11", "通用 + 特定组查询", "通用 + 组 + 源特定查询"),
        ("源过滤", "不支持", "不支持", "支持 INCLUDE / EXCLUDE"),
        ("报告抑制", "无", "有（同组只一台应答）", "有"),
        ("查询间隔", "60 秒", "60 秒（常用 125 秒）", "125 秒"),
        ("最大响应时间", "10 秒", "10 秒", "10 秒（可细分）"),
        ("典型部署", "已淘汰", "广泛", "SSM / 现代网络"),
    ]
    for r in rows:
        print(pad(r[0], 24) + pad(r[1], 26) + pad(r[2], 26) + r[3])
    print("-" * 96)
    print("IGMP Snooping 的作用：二层交换机默认把组播帧当广播泛洪，")
    print("  开启 Snooping 后，交换机会监听 IGMP 报文，建立「组播 MAC → 端口」转发表，")
    print("  只向有接收者的端口转发，从而把组播流量限制在必要的链路上。")
    print()
    print(">>> 结论：v1 没有离开报文，主机退出后路由器要等到查询超时才知道；")
    print("    v2 用 Leave 报文缩短了离开延迟；v3 增加了源过滤，是 SSM 的基础。")
    print()
    print("小结：")
    print("1. 映射规则是「01:00:5E + 低 23 位」，最多 32 个组共享一个 MAC，主机必须靠 IP 过滤。")
    print("2. 会撞车的是低 23 位相同、被丢弃的 5 位不同的一组地址；")
    print("   224.0.1.1 与 239.1.1.1 的低 23 位不同，并不会撞到同一个 MAC。")
    print("3. IGMP 三代依次补齐了「离开」「源过滤」两项能力；二层靠 IGMP Snooping 抑制泛洪。")
    print()


if __name__ == "__main__":
    main()
