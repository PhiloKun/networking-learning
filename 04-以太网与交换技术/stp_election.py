#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STP 根桥 / 根端口 / 指定端口选举全过程模拟（5 台交换机环状拓扑）。"""
import sys
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 80
SUB = "-" * 80

# (交换机名, 桥优先级, MAC) —— BID = 优先级 + MAC，数值越小越优
SWITCHES = [
    ("SW1", 32768, "02:00:00:00:00:01"),
    ("SW2", 32768, "02:00:00:00:00:02"),
    ("SW3", 32768, "02:00:00:00:00:03"),
    ("SW4", 32768, "02:00:00:00:00:04"),
    ("SW5", 32768, "02:00:00:00:00:05"),
]
# 环状拓扑：SW1-SW2-SW3-SW4-SW5-SW1，均为 1 Gbps 链路
LINKS = [
    ("SW1", "SW2", 4),
    ("SW2", "SW3", 4),
    ("SW3", "SW4", 4),
    ("SW4", "SW5", 4),
    ("SW5", "SW1", 4),
]


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def bid(sw: str) -> tuple[int, str]:
    for name, prio, mac in SWITCHES:
        if name == sw:
            return prio, mac
    raise KeyError(sw)


def neighbors(sw: str) -> list[tuple[str, int]]:
    out = []
    for a, b, c in LINKS:
        if a == sw:
            out.append((b, c))
        elif b == sw:
            out.append((a, c))
    return out


def main() -> None:
    print(SEP)
    print("STP 生成树选举模拟 · 5 台交换机环状拓扑")
    print(SEP)
    print("拓扑：SW1 -- SW2 -- SW3 -- SW4 -- SW5 -- SW1（首尾相连成环，全部 1 Gbps）")
    print()
    print(SUB)
    print("【一】桥 ID（BID）与路径开销")
    print(SUB)
    print(pad("交换机", 10) + pad("优先级", 10, True) + pad("MAC 地址", 24) + pad("BID", 26))
    print(SUB)
    for name, prio, mac in SWITCHES:
        print(pad(name, 10) + pad(str(prio), 10, True) + pad(mac, 24)
              + pad(f"{prio} / {mac}", 26))
    print(SUB)
    print("BID 比较规则：先比优先级（小者优），相同再比 MAC（小者优）。")
    print()
    print(pad("链路速率", 12) + pad("IEEE 802.1D 开销", 20, True) + "说明")
    print(SUB)
    for rate, cost in [(10, 100), (100, 19), (1000, 4), (10000, 2)]:
        note = "本拓扑使用" if rate == 1000 else ""
        print(pad(f"{rate} Mbps", 12) + pad(str(cost), 20, True) + note)
    print(SUB)
    print()

    print(SUB)
    print("【二】第 1 轮：选根桥（Root Bridge）")
    print(SUB)
    print("初始时每台交换机都以为自己是根桥，互相发送 BPDU 比较 BID：")
    order = sorted(SWITCHES, key=lambda s: (s[1], s[2]))
    for name, prio, mac in order:
        print(f"  {name}  声明自己是根桥，BID = {prio} / {mac}")
    root = order[0][0]
    print()
    print(f">>> 优先级全部为 32768，比较 MAC，最小的是 {order[0][2]}")
    print(f">>> 根桥 = {root}")
    print()

    # Dijkstra 计算根路径开销
    dist: dict[str, int] = {name: 10 ** 9 for name, _, _ in SWITCHES}
    dist[root] = 0
    visited: set[str] = set()
    while len(visited) < len(SWITCHES):
        cur = min((s for s in dist if s not in visited), key=lambda s: dist[s])
        visited.add(cur)
        for nb, cost in neighbors(cur):
            if dist[cur] + cost < dist[nb]:
                dist[nb] = dist[cur] + cost

    print(SUB)
    print("【三】第 2 轮：各交换机计算根路径开销，选根端口（Root Port）")
    print(SUB)
    print("根路径开销 = 到根桥路径上所有链路开销之和；根端口 = 开销最小的那个端口。")
    print(SUB)
    print(pad("交换机", 10) + pad("根路径开销", 14, True) + pad("根端口（指向）", 22, True)
          + "  计算依据")
    print(SUB)
    root_ports: dict[str, str] = {}
    for name, _, _ in SWITCHES:
        if name == root:
            print(pad(name, 10) + pad("0", 14, True) + pad("—（自己就是根桥）", 22, True)
                  + "  根桥所有端口都是指定端口")
            continue
        best = None
        for nb, cost in neighbors(name):
            total = dist[nb] + cost
            key = (total, bid(nb)[1])
            if best is None or key < best[0]:
                best = (key, nb, total)
        assert best is not None
        _, nb, total = best
        root_ports[name] = nb
        print(pad(name, 10) + pad(str(total), 14, True) + pad(f"-> {nb}", 22, True)
              + f"  经 {nb} 总开销 {total}")
    print(SUB)
    print()

    print(SUB)
    print("【四】第 3 轮：每条链路上选指定端口（Designated Port），另一端阻塞")
    print(SUB)
    print("规则：一条链路两端比较「(根路径开销, 发送方 BID)」，小的一端为指定端口。")
    print(SUB)
    print(pad("链路", 16) + pad("两端 (开销, BID)", 40) + pad("指定端口", 12) + "对端角色")
    print(SUB)
    blocked = []
    for a, b, cost in LINKS:
        ka = (dist[a], bid(a)[1])
        kb = (dist[b], bid(b)[1])
        if ka <= kb:
            des, other = a, b
        else:
            des, other = b, a
        if other in root_ports and root_ports[other] == des:
            other_role = "根端口"
        else:
            other_role = "阻塞（Blocking）"
            blocked.append((other, des))
        print(pad(f"{a} -- {b}", 16)
              + pad(f"{a}({ka[0]},{ka[1][-5:]})  {b}({kb[0]},{kb[1][-5:]})", 40)
              + pad(des, 12) + other_role)
    print(SUB)
    print()

    print(SUB)
    print("【五】收敛结果")
    print(SUB)
    print(pad("交换机", 10) + pad("角色", 14) + pad("端口状态", 42) + "说明")
    print(SUB)
    for name, _, _ in SWITCHES:
        if name == root:
            print(pad(name, 10) + pad("根桥", 14) + pad("全部端口 Forwarding", 42)
                  + "所有端口都是指定端口")
        else:
            rp = root_ports[name]
            blocked_to = [d for s, d in blocked if s == name]
            if blocked_to:
                print(pad(name, 10) + pad("非根桥", 14)
                      + pad(f"根端口->{rp} 转发；到 {blocked_to[0]} 端口阻塞", 42)
                      + "环路被打断")
            else:
                print(pad(name, 10) + pad("非根桥", 14)
                      + pad(f"根端口->{rp} 转发", 42) + "无阻塞端口")
    print(SUB)
    for s, d in blocked:
        print(f">>> 阻塞端口：{s} 连接到 {d} 的端口 —— 若不阻塞，"
              f"该链路与生成树构成环路，会引发广播风暴。")
    print()
    print(pad("定时器", 22) + pad("默认值", 10, True) + "  作用")
    print(SUB)
    for t, v, note in [("Hello Time", "2 s", "根桥周期性发送 BPDU 的间隔"),
                       ("Max Age", "20 s", "BPDU 超时时间，超时认为链路故障"),
                       ("Forward Delay", "15 s", "监听/学习状态各停留时间")]:
        print(pad(t, 22) + pad(v, 10, True) + "  " + note)
    print(SUB)
    print(">>> 传统 STP 收敛时间：约 30~50 s（= 2 x Forward Delay 或 Max Age + ...）。")
    print(">>> RSTP（802.1w）用 P/A 协商与边缘端口把收敛缩短到秒级甚至毫秒级。")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. 根桥 = BID 最小者，本拓扑为 {root}（优先级相同，比较 MAC）。")
    print(f"2. 每台非根桥选 1 个根端口（到根开销最小），每条链路选 1 个指定端口。")
    print(f"3. 既不是根端口也不是指定端口的端口被阻塞，本拓扑阻塞了 {len(blocked)} 个端口。")
    print("4. STP 用阻塞端口把物理环路变成无环的逻辑树，代价是收敛慢；RSTP 是工程首选。")
    print()


if __name__ == "__main__":
    main()
