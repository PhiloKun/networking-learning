#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OSPF Cost 计算（参考带宽 100Mbps / 可调）与 Dijkstra SPF 最短路径树演示。

运行: python3 ospf_cost_spf.py
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


# 接口带宽 → Cost = 参考带宽 / 接口带宽，结果向下取整，最小为 1
INTERFACES = [
    ("10 Mbps 以太网", 10),
    ("100 Mbps 快速以太网", 100),
    ("1 Gbps 千兆以太网", 1000),
    ("2.5 Gbps", 2500),
    ("10 Gbps 万兆以太网", 10000),
    ("40 Gbps", 40000),
    ("100 Gbps", 100000),
]

# 骨干链路拓扑（地址取自 203.0.113.0/24，链路两端各占一个 /30）
# (节点A, 节点B, 链路Cost, 链路带宽描述)
LINKS = [
    ("R1", "R2", 10, "10 Mbps"),
    ("R1", "R3", 30, "3 Mbps(教学取值)"),
    ("R2", "R3", 5, "20 Mbps"),
    ("R2", "R4", 20, "5 Mbps"),
    ("R3", "R4", 5, "20 Mbps"),
]
NODES = ["R1", "R2", "R3", "R4"]
LOOPBACK = {"R1": "203.0.113.1", "R2": "203.0.113.2",
            "R3": "203.0.113.3", "R4": "203.0.113.4"}


def cost_of(ref_mbps, bw_mbps):
    """Cost = 参考带宽 / 接口带宽，向下取整，下限 1。"""
    c = ref_mbps // bw_mbps
    return max(c, 1)


def print_cost_table():
    print("=" * 78)
    print("一、Cost 计算公式：Cost = 参考带宽 / 接口带宽（向下取整，最小 1）")
    print("-" * 78)
    print(pad("接口类型", 26) + pad("接口带宽(Mbps)", 16)
          + pad("参考=100M", 12) + pad("参考=10G", 12))
    for name, bw in INTERFACES:
        c100 = cost_of(100, bw)
        c10g = cost_of(10000, bw)
        print(pad(name, 26) + pad(str(bw), 16) + pad(str(c100), 12) + pad(str(c10g), 12))
    print("-" * 78)
    print(">>> 结论：默认参考带宽 100Mbps 时，100M/1G/10G 接口的 Cost 全是 1，")
    print("    链路带宽差异被完全抹平 —— 这是现网最常见的一类「选路不符合预期」根因。")
    print("    把参考带宽改成 10Gbps 后，1G=10、10G=1、100G=1，层次才重新拉开。")
    print()
    print("代入示例：10G 接口在参考 100M 下 Cost = 100 // 10000 = 0 → 因下限取 1；")
    print("          10G 接口在参考 10G 下  Cost = 10000 // 10000 = 1；")
    print("          1G 接口在参考 10G 下   Cost = 10000 // 1000 = 10。")
    print("          100G 接口在参考 10G 下 Cost = 10000 // 100000 = 0 → 取 1，故 10G 与")
    print("          100G 在 10G 参考带宽下仍同为 1，要区分需把参考带宽调到 100G。")
    print()


def adjacency():
    adj = {n: [] for n in NODES}
    for a, b, c, bw in LINKS:
        adj[a].append((b, c))
        adj[b].append((a, c))
    for n in adj:
        adj[n].sort()
    return adj


def dijkstra(root, adj, verbose=False):
    """标准 Dijkstra：返回 dist / prev，并（可选）打印每轮候选集。"""
    dist = {n: float("inf") for n in NODES}
    prev = {n: None for n in NODES}
    dist[root] = 0
    visited = set()
    round_no = 0
    if verbose:
        print(f"以 {root} 为根运行 SPF（Dijkstra），每轮从候选集中取最小距离节点固化：")
        print(pad("轮", 6) + pad("固化节点", 12) + "候选集(节点:距离)")
    while len(visited) < len(NODES):
        # 1) 在所有未固化节点中选距离最小者
        cand = [(dist[n], n) for n in NODES if n not in visited]
        cand.sort()
        d, u = cand[0]
        if d == float("inf"):
            break
        visited.add(u)
        round_no += 1
        # 2) 松弛 u 的所有邻居
        for v, w in adj[u]:
            if v in visited:
                continue
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                prev[v] = u
        if verbose:
            rest = sorted((n, dist[n]) for n in NODES
                          if n not in visited and dist[n] != float("inf"))
            rest_txt = " ".join(f"{n}:{int(dv)}" for n, dv in rest) or "（空）"
            print(pad(str(round_no), 6) + pad(u, 12) + rest_txt)
    return dist, prev


def path_to(prev, root, dst):
    if dst == root:
        return [root]
    chain = [dst]
    cur = dst
    while prev[cur] is not None:
        cur = prev[cur]
        chain.append(cur)
    chain.reverse()
    if chain[0] != root:
        return None
    return chain


def main():
    print()
    print("OSPF Cost 与 SPF 计算演示 · 参考带宽默认 100 Mbps")
    print()
    print_cost_table()
    adj = adjacency()

    print("=" * 78)
    print("二、骨干拓扑与链路 Cost")
    print("-" * 78)
    print("        R1")
    print("       /  \\")
    print("   c10/    \\c30")
    print("     /      \\")
    print("    R2--c5--R3")
    print("     \\      /")
    print("  c20 \\    / c5")
    print("       \\  /")
    print("        R4")
    print("-" * 78)
    print(pad("链路", 12) + pad("本端地址", 20) + pad("对端地址", 20)
          + pad("Cost", 8) + "带宽")
    for a, b, c, bw in LINKS:
        print(pad(a + "-" + b, 12) + pad(LOOPBACK[a] + " (环回)", 20)
              + pad(LOOPBACK[b] + " (环回)", 20) + pad(str(c), 8) + bw)
    print("-" * 78)
    print("说明：链路地址取自 203.0.113.0/24，两端各占一个 /30；上表用环回地址代表各路由器。")
    print()

    print("=" * 78)
    print("三、以 R1 为根的 SPF 逐步计算")
    print("-" * 78)
    dist_r1, prev_r1 = dijkstra("R1", adj, verbose=True)
    print("-" * 78)
    print(pad("目的节点", 12) + pad("最短Cost", 12) + pad("路径", 28) + "下一跳")
    for n in NODES:
        if n == "R1":
            continue
        p = path_to(prev_r1, "R1", n)
        print(pad(n, 12) + pad(str(int(dist_r1[n])), 12)
              + pad("->".join(p), 28) + p[1])
    print("-" * 78)
    print(">>> 结论：R4 的最优路径是 R1->R2->R3->R4（Cost 10+5+5=20），")
    print("    而不是直连式的 R1->R2->R4（Cost 10+20=30），SPF 只认总开销。")
    print()

    print("=" * 78)
    print("四、各路由器的 OSPF 路由表（本区域内的节点路由）")
    print("-" * 78)
    for root in NODES:
        dist, prev = dijkstra(root, adj)
        print(f"[{root}]  Router-ID = {LOOPBACK[root]}，LSDB 中已有 5 条 Router-LSA")
        print(pad("  目的", 18) + pad("Cost", 8) + pad("下一跳", 10) + "出接口(示意)")
        for n in NODES:
            if n == root:
                continue
            p = path_to(prev, root, n)
            print(pad("  " + LOOPBACK[n] + "/32", 18) + pad(str(int(dist[n])), 8)
                  + pad(p[1], 10) + f"Eth0/{NODES.index(p[1]) + 1}")
        print()

    print("=" * 78)
    print("五、参考带宽调整（自适应带宽宽度）")
    print("-" * 78)
    print("Cisco:  router ospf 1 → auto-cost reference-bandwidth 10000  (单位 Mbps)")
    print("华为  : ospf 1        → bandwidth-reference 10000            (单位 Mbps)")
    print("-" * 78)
    print(pad("链路", 12) + pad("带宽", 14) + pad("默认Cost(100M)", 18) + "调整后Cost(10G)")
    for a, b, c, bw in LINKS:
        bw_nominal = {"R1-R2": 10, "R1-R3": 3, "R2-R3": 20, "R2-R4": 5, "R3-R4": 20}[a + "-" + b]
        print(pad(a + "-" + b, 12) + pad(str(bw_nominal) + " Mbps", 14)
              + pad(str(cost_of(100, bw_nominal)), 18) + str(cost_of(10000, bw_nominal)))
    print("-" * 78)
    print(">>> 结论：参考带宽必须全网统一。只在一台设备上改，会导致两端算出的 Cost 不一致，")
    print("    出现「去程走 A、回程走 B」的非对称路由，SPF 结果也无法互相对齐。")
    print()
    print("小结：")
    print("1. Cost = 参考带宽 / 接口带宽（向下取整，最小 1）；默认参考带宽 100 Mbps。")
    print("2. 默认值下 ≥100M 的接口 Cost 都是 1，带宽差异被抹平；上生产前务必统一改参考带宽。")
    print("3. SPF 是全局的 Dijkstra，逐轮固化最小距离节点，最终得到以自己为根、无环的最短路径树。")
    print()


if __name__ == "__main__":
    main()
