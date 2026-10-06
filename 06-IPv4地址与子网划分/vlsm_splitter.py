#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VLSM 变长子网划分：按需求降序从 192.0.2.0/24 切分，输出划分表与利用率。

运行: python3 vlsm_splitter.py
     python3 vlsm_splitter.py 198.51.100.0/24 120,60,30,12,2
"""
import ipaddress
import sys

sys.dont_write_bytecode = True

BASE = "192.0.2.0/24"
# 默认需求：部门名 + 需要的「可用主机数」
DEMANDS = [
    ("研发部", 100),
    ("市场部", 50),
    ("财务部", 20),
    ("互联链路(点对点)", 2),
]


def prefix_for_hosts(need: int) -> int:
    """求满足 need 个可用主机所需的最短前缀：找最小主机位 h 使 2^h − 2 ≥ need。"""
    bits = 0
    while (2 ** bits) - 2 < need:
        bits += 1
    return 32 - bits


def allocate(base: ipaddress.IPv4Network, demands) -> tuple:
    """按需求降序做 VLSM 顺序分配，返回 (分配结果列表, 剩余空闲网络列表)。"""
    ordered = sorted(demands, key=lambda d: d[1], reverse=True)
    free = [base]
    allocated = []
    for name, need in ordered:
        p = prefix_for_hosts(need)
        size = 2 ** (32 - p)
        # 找第一个能装下的空闲块
        idx = next((i for i, blk in enumerate(free) if blk.num_addresses >= size), None)
        if idx is None:
            allocated.append((name, need, None, "空间不足，分配失败"))
            continue
        blk = free.pop(idx)
        sub = ipaddress.ip_network((int(blk.network_address), p))
        allocated.append((name, need, sub, ""))
        # 剩余部分按 2 的幂对齐切回空闲列表
        rest = int(blk.broadcast_address) - int(sub.broadcast_address)
        if rest > 0:
            nxt = ipaddress.ip_address(int(sub.broadcast_address) + 1)
            free.extend(_split_rest(nxt, rest))
        free = sorted(free, key=lambda n: int(n.network_address))
    return allocated, free


def _split_rest(start: ipaddress.IPv4Address, total: int) -> list:
    """把 [start, start+total-1] 切成分散的空闲 CIDR 块（每块起始地址按 2 的幂对齐）。"""
    out = []
    cur = int(start)
    remaining = total
    while remaining > 0:
        size = 1
        while size * 2 <= remaining and cur % (size * 2) == 0:
            size *= 2
        prefix = 33 - size.bit_length()          # log2(size) = bit_length−1
        out.append(ipaddress.ip_network((ipaddress.ip_address(cur), prefix)))
        cur += size
        remaining -= size
    return out


def self_check(base: ipaddress.IPv4Network, allocated) -> None:
    """自校验：每个子网容量足够、互不重叠、全部落在 base 内。"""
    nets = [a[2] for a in allocated if a[2] is not None]
    total = 0
    for name, need, sub, err in allocated:
        assert sub is not None, f"{name} 未分配"
        assert sub.subnet_of(base), f"{name} {sub} 不在 {base} 内"
        usable = sub.num_addresses - 2 if sub.prefixlen < 31 else sub.num_addresses
        assert usable >= need, f"{name} 容量 {usable} < 需求 {need}"
        total += sub.num_addresses
    # 两两不重叠
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            assert not nets[i].overlaps(nets[j]), f"{nets[i]} 与 {nets[j]} 重叠"
    assert total <= base.num_addresses
    # 已知默认用例的精确结果
    if str(base) == "192.0.2.0/24":
        got = {a[0]: str(a[2]) for a in allocated if a[2]}
        assert got["研发部"] == "192.0.2.0/25", got
        assert got["市场部"] == "192.0.2.128/26", got
        assert got["财务部"] == "192.0.2.192/27", got
        assert got["互联链路(点对点)"] == "192.0.2.224/30", got


def main() -> int:
    if len(sys.argv) >= 3:
        base = ipaddress.ip_network(sys.argv[1], strict=False)
        demands = [(f"部门{i+1}", int(x)) for i, x in enumerate(sys.argv[2].split(","))]
    else:
        base = ipaddress.ip_network(BASE)
        demands = DEMANDS

    allocated, free = allocate(base, demands)
    self_check(base, allocated)

    print("=" * 84)
    print("VLSM 变长子网划分（按需求降序分配，先大后小才能避免碎片）")
    print("=" * 84)
    print(f"地址池：{base}   可用地址 {base.num_addresses} 个")
    print()
    print("分配顺序（降序）：" + " > ".join(f"{n}({d})" for n, d in
                                        sorted(demands, key=lambda x: x[1], reverse=True)))
    print("-" * 84)
    print(f"{'部门':<18}{'需求':>5}{'前缀':>7}{'网络地址':>18}{'可用范围':>28}{'容量':>7}")
    print("-" * 84)
    used = 0
    for name, need, sub, err in allocated:
        if sub is None:
            print(f"{name:<18}{need:>5}{'--':>7}{err}")
            continue
        usable = sub.num_addresses - 2 if sub.prefixlen < 31 else sub.num_addresses
        if sub.prefixlen >= 31:
            rng = f"{sub.network_address} ~ {sub.broadcast_address}"
        else:
            rng = f"{list(sub.hosts())[0]} ~ {list(sub.hosts())[-1]}"
        used += sub.num_addresses
        print(f"{name:<18}{need:>5}{'/' + str(sub.prefixlen):>7}{str(sub.network_address):>18}"
              f"{rng:>28}{usable:>7}")
    print("-" * 84)
    req = sum(d for _, d in demands)
    print(f"申请主机总数 = {req}")
    print(f"已分配地址块 = {used} / {base.num_addresses}"
          f"（按地址块利用率 {used / base.num_addresses * 100:.1f}%）")
    print(f"按需利用率   = {req} / {used} = {req / used * 100:.1f}%"
          f"（VLSM 把浪费压到每块 ≤ 2 个 + 对齐余量）")
    print(f"剩余空闲块   = {len(free)} 个，共 {sum(n.num_addresses for n in free)} 个地址")
    for n in free:
        print(f"  - {n}  （{n.num_addresses} 个地址，可留给未来扩容）")
    print("-" * 84)
    print("前缀推导（每个部门要多少位主机）：")
    for name, need in sorted(demands, key=lambda x: x[1], reverse=True):
        p = prefix_for_hosts(need)
        h = 32 - p
        print(f"  {name:<18} 需 {need:>3} 个可用主机 → 2^h − 2 ≥ {need} → h = {h} → "
              f"块大小 {2 ** h} → /{p}")
    print(">>> 结论：VLSM 必须「需求降序」分配，否则小需求先占低位会造成大块被切碎而无法分配。")
    print(">>> 结论：每块至少浪费 2 个地址（网络号 + 广播），点对点链路用 /30 正好只浪费 2 个。")
    print()
    print("小结")
    print("  1. 子网尺寸只由「需要的可用主机数」决定：2^h − 2 ≥ 需求，h 向上取整。")
    print("  2. 分配顺序按需求从大到小，保证大块不被小需求切割，这是 VLSM 的核心纪律。")
    print("  3. 剩余空间按 2 的幂对齐保留，便于将来按需扩容而不打乱既有地址。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
