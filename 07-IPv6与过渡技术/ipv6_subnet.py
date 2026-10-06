#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPv6 三层编址规划：2001:db8:abcd::/48 → /56（站点）→ /64（网段），输出前缀表与容量。

运行: python3 ipv6_subnet.py
"""
import ipaddress
import sys

sys.dont_write_bytecode = True

SITE_PREFIX = "2001:db8:abcd::/48"

# (站点号 8 位, 站点名, 网段号 8 位, 网段名, VLAN)
PLAN = [
    (0x00, "总部大楼", 0x00, "办公区", 10),
    (0x00, "总部大楼", 0x01, "服务器区", 20),
    (0x00, "总部大楼", 0x02, "网络管理", 30),
    (0x00, "总部大楼", 0x0A, "无线访客", 40),
    (0x01, "研发园区", 0x00, "办公区", 10),
    (0x01, "研发园区", 0x01, "测试环境", 50),
    (0x02, "分支机构A", 0x00, "办公区", 10),
    (0x03, "分支机构B", 0x00, "办公区", 10),
]


def seg64(subsite: int, seg: int) -> str:
    """把 (站点号 8 位, 网段号 8 位) 拼成第 4 组十六进制，得到 /64 前缀。"""
    g = (subsite << 8) | (seg & 0xFF)
    return str(ipaddress.ip_network(f"2001:db8:abcd:{g:x}::/64", strict=False))


def site56(subsite: int) -> str:
    g = subsite << 8
    return str(ipaddress.ip_network(f"2001:db8:abcd:{g:x}::/56", strict=False))


def self_check() -> None:
    base = ipaddress.ip_network(SITE_PREFIX)
    assert base.prefixlen == 48
    # 容量公式：/48→/56 有 2^8 个；每个 /56→/64 有 2^8 个；合计 2^16 个 /64
    n56 = 2 ** (56 - 48)
    n64_per56 = 2 ** (64 - 56)
    n64_total = 2 ** (64 - 48)
    assert n56 == 256 and n64_per56 == 256 and n64_total == 65536
    # 用标准库枚举验证数量（只取前若干个做抽样，避免全量物化）
    subs = base.subnets(new_prefix=56)
    first = next(subs)
    assert str(first) == "2001:db8:abcd::/56"
    assert len(list(first.subnets(new_prefix=64))) == 256
    # 具体前缀校验（注意 RFC 5952：第 4 组为 0 时会与后面的零组一起被压缩成 ::）
    assert seg64(0x00, 0x00) == "2001:db8:abcd::/64"
    assert seg64(0x00, 0x0A) == "2001:db8:abcd:a::/64"
    assert seg64(0x01, 0x01) == "2001:db8:abcd:101::/64"
    assert site56(0x01) == "2001:db8:abcd:100::/56"
    # 每个规划条目都必须落在 /48 内且是合法 /64
    for subsite, _s, seg, _n, _v in PLAN:
        net = ipaddress.ip_network(seg64(subsite, seg))
        assert net.prefixlen == 64 and net.subnet_of(base), net


def main() -> int:
    self_check()
    base = ipaddress.ip_network(SITE_PREFIX)
    print("=" * 88)
    print("IPv6 三层编址规划：站点 /48 → 建筑物 /56 → 网段 /64")
    print("=" * 88)
    print(f"起始前缀：{base}   （RFC 3849 文档专用 2001:db8::/32 内）")
    print()
    print("层级划分与位数分配")
    print("-" * 88)
    print("  ┌────────────────────────── 128 bit ──────────────────────────┐")
    print("  │ 全局路由前缀 48 bit │ 站点 8 bit │ 网段 8 bit │ 接口标识 64 bit │")
    print("  │ 2001:0db8:abcd      │ 49~56      │ 57~64      │ 65~128          │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print()
    print("容量计算")
    print("-" * 88)
    print(f"  /48 → /56：2^(56−48) = 2^8 = {2 ** 8} 个站点（或建筑物）")
    print(f"  /56 → /64：2^(64−56) = 2^8 = {2 ** 8} 个网段（每个站点内）")
    print(f"  /48 → /64：2^(64−48) = 2^16 = {2 ** 16} 个 /64 网段")
    print(f"  单个 /64 可用地址：2^64 = {2 ** 64} 个（约 1.8×10^19）")
    print(f"  整块 /48 的地址总量：2^80 = {2 ** 80} 个")
    print()
    print("网段规划表")
    print("-" * 88)
    print(f"{'站点':<10}{'站点前缀(/56)':<26}{'用途':<12}{'VLAN':<6}{'/64 网段'}")
    print("-" * 88)
    seen_site = set()
    for subsite, sname, seg, segname, vlan in PLAN:
        sitecell = sname if subsite not in seen_site else ""
        seen_site.add(subsite)
        pre = site56(subsite) if sitecell else ""
        print(f"{sitecell:<10}{pre:<26}{segname:<12}{vlan:<6}{seg64(subsite, seg)}")
    print("-" * 88)
    print()
    print("剩余可用空间")
    print("-" * 88)
    used_sites = sorted({s for s, *_ in PLAN})
    print(f"  已用站点号：{', '.join(f'0x{s:02x}' for s in used_sites)}")
    print(f"  站点空间余量：256 − {len(used_sites)} = {256 - len(used_sites)} 个 /56 未分配")
    used64 = len(PLAN)
    print(f"  /64 空间余量：65536 − {used64} = {65536 - used64} 个 /64 未分配")
    print("  >>> 结论：一个 /48 足够支撑「256 个站点 × 每站点 256 个网段」，扩容空间极其充裕。")
    print()
    print("为什么网段固定用 /64？")
    print("-" * 88)
    print("  1. SLAAC（无状态地址自动配置）在 RFC 4291 中规定接口标识必须是 64 位，")
    print("     地址被切成前 64 位做前缀、后 64 位做接口标识，所以子网前缀只能是 /64。")
    print("  2. 若把网段划成 /80 或 /96，SLAAC 无法工作，必须改用 DHCPv6 且很多终端会直接失败。")
    print("  3. /64 带来的地址浪费不重要——数量级足够大到不需要节省，可读性和标准化更重要。")
    print()
    print(">>> 结论：/48 分站点、/56 分级、/64 分网段，是运营商与企业最常见的三层 IPv6 编址模型。")
    print()
    print("小结")
    print("  1. /48 只做「站点级」分配，/56 做建筑物级，/64 才是终端所在网段的唯一合法长度。")
    print("  2. 每个 /48 有 2^16 = 65536 个 /64，规划时把它当「够用且必须保持整齐」的资源。")
    print("  3. 编址保持层级对齐（站点号在固定位段），才能让路由在汇聚层用一条前缀聚合。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
