#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容器 IPAM 模拟：按节点分 Pod CIDR 做地址分配/回收，观察耗尽与延迟复用。

运行: python3 cni_ipam.py
"""
import ipaddress
import random
import sys
from dataclasses import dataclass, field

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

NODES = 10
POD_CIDR_PREFIX = 24          # 每个节点一个 /24
OPS = 6000                    # 模拟操作数
CREATE_P = 0.68               # 创建概率（其余为删除）
RELEASE_DELAY = 2000          # 场景 B 的延迟回收窗口（操作数）
LEAK_RATIO = 0.20             # 场景 C 中「删除后不释放」的比例

random.seed(42)


@dataclass
class Node:
    name: str
    cidr: str
    free: list = field(default_factory=list)
    used: dict = field(default_factory=dict)       # ip -> 分配序号
    pending: list = field(default_factory=list)    # [(释放到期操作号, ip)]
    leaked: set = field(default_factory=set)
    peak: int = 0
    failures: int = 0

    @property
    def capacity(self) -> int:
        return len(self.free) + len(self.used) + len(self.pending) + len(self.leaked)


def build_nodes() -> list:
    nodes = []
    for i in range(NODES):
        net = ipaddress.ip_network(f"10.244.{i}.0/{POD_CIDR_PREFIX}")
        hosts = [str(h) for h in net.hosts()]      # 去掉网络号与广播，共 254 个
        nodes.append(Node(f"node-{i:02d}", str(net), free=list(hosts)))
    return nodes


def step_pending(node: Node, op: int) -> None:
    """把到期的待释放地址真正还给空闲池。"""
    remain = []
    for due, ip in node.pending:
        if op >= due:
            node.free.append(ip)
        else:
            remain.append((due, ip))
    node.pending = remain


def allocate(node: Node, op: int) -> str:
    if not node.free:
        node.failures += 1
        return ""
    ip = node.free.pop()
    node.used[ip] = op
    node.peak = max(node.peak, len(node.used))
    return ip


def release(node: Node, ip: str, mode: str, op: int) -> None:
    node.used.pop(ip, None)
    if mode == "immediate":
        node.free.append(ip)
    elif mode == "delayed":
        node.pending.append((op + RELEASE_DELAY, ip))
    elif mode == "leak":
        if random.random() < LEAK_RATIO:
            node.leaked.add(ip)
        else:
            node.free.append(ip)


def simulate(mode: str, label: str) -> dict:
    random.seed(42)
    nodes = build_nodes()
    created = 0
    failed = 0
    deleted = 0
    live = []                                   # [(node_idx, ip)]

    for op in range(OPS):
        for node in nodes:
            step_pending(node, op)
        nidx = random.randrange(NODES)
        node = nodes[nidx]
        action = random.random()
        if action < CREATE_P or not live:       # 新建 Pod
            ip = allocate(node, op)
            if ip:
                live.append((nidx, ip))
                created += 1
            else:
                failed += 1
        else:                                   # 删除一个已存在的 Pod
            k = random.randrange(len(live))
            di, dip = live.pop(k)
            release(nodes[di], dip, mode, op)
            deleted += 1

    total_free = sum(len(n.free) for n in nodes)
    total_pending = sum(len(n.pending) for n in nodes)
    total_used = sum(len(n.used) for n in nodes)
    total_leaked = sum(len(n.leaked) for n in nodes)
    return {
        "label": label,
        "nodes": nodes,
        "created": created,
        "failed": failed,
        "deleted": deleted,
        "free": total_free,
        "pending": total_pending,
        "used": total_used,
        "leaked": total_leaked,
        "capacity": sum(n.capacity for n in nodes),
    }


def render(res: dict) -> None:
    print(SUB)
    print(res["label"])
    print(SUB)
    print(f"  创建成功 = {res['created']}，删除 = {res['deleted']}，分配失败 = {res['failed']}")
    print(f"  当前在用 = {res['used']}，空闲 = {res['free']}，"
          f"待释放 = {res['pending']}，泄漏 = {res['leaked']}")
    print(f"  总容量 = {res['capacity']}（{NODES} 节点 × 254）")
    print()
    print(f"  {'节点':<10}{'CIDR':<18}{'在用':>6}{'空闲':>6}{'待释放':>8}{'泄漏':>6}{'峰值':>6}{'失败':>6}")
    print("  " + SUB)
    for n in res["nodes"]:
        print(f"  {n.name:<10}{n.cidr:<18}{len(n.used):>6}{len(n.free):>6}"
              f"{len(n.pending):>8}{len(n.leaked):>6}{n.peak:>6}{n.failures:>6}")
    print("  " + SUB)
    if res["failed"]:
        print(f"  >>> 结论：出现 {res['failed']} 次分配失败，说明地址池已耗尽或被延迟回收拖垮。")
    else:
        print("  >>> 结论：全程未出现分配失败，地址回收及时、池子够用。")


def main() -> None:
    print(SEP)
    print("容器 IPAM 模拟：Pod CIDR 分配、回收与耗尽")
    print(SEP)
    print(f"规模：{NODES} 个节点，每节点一个 /{POD_CIDR_PREFIX} Pod CIDR"
          f"（{254} 个可用地址）")
    print(f"总地址容量 = {NODES} × 254 = {NODES * 254}")
    print(f"模拟操作数 = {OPS}（{int(CREATE_P * 100)}% 创建 / "
          f"{int((1 - CREATE_P) * 100)}% 删除，随机种子固定为 42）")

    print()
    print(SUB)
    print("【一】地址池结构（以 node-00 为例）")
    print(SUB)
    net = ipaddress.ip_network(f"10.244.0.0/{POD_CIDR_PREFIX}")
    hosts = list(net.hosts())
    print(f"  网段        : {net}")
    print(f"  网络号      : {net.network_address}（不可分配）")
    print(f"  广播地址    : {net.broadcast_address}（不可分配）")
    print(f"  可用地址    : {hosts[0]} ~ {hosts[-1]}，共 {len(hosts)} 个")
    print(f"  典型分配    : 10.244.0.2 常留给网桥/gateway，Pod 从 10.244.0.3 起")
    print("  说明：/24 是常见默认值，也可按节点规模用 /23、/25 等（`--pod-cidr` 配置）")

    print()
    res_a = simulate("immediate", "【二】场景 A：删除后立即回收（正常 CNI 行为）")
    render(res_a)

    print()
    res_b = simulate("delayed", f"【三】场景 B：删除后延迟 {RELEASE_DELAY} 次操作才回收")
    render(res_b)

    print()
    res_c = simulate("leak", f"【四】场景 C：{int(LEAK_RATIO * 100)}% 的删除未释放（地址泄漏）")
    render(res_c)

    print()
    print(SUB)
    print("【五】三种场景对照")
    print(SUB)
    print(f"{'场景':<34}{'分配失败':>10}{'空闲地址':>10}{'泄漏地址':>10}{'判定'}")
    print(SUB)
    verdict = lambda r: "健康" if r["failed"] == 0 else "需扩容/修复"
    for r in (res_a, res_b, res_c):
        print(f"{r['label'][:32]:<34}{r['failed']:>10}{r['free']:>10}"
              f"{r['leaked']:>10}{verdict(r):>12}")

    print()
    print(SUB)
    print("【六】地址耗尽的成因与规避")
    print(SUB)
    causes = [
        ("Pod CIDR 规划过小", "每节点只给 /25 或复用同一 /24", "按节点最大 Pod 数 × 1.5 预留"),
        ("回收延迟", "CNI/kubelet 未及时释放，短时间大量重建", "提高回收频率，扩容 Pod CIDR"),
        ("地址泄漏", "容器异常退出未走正常删除流程", "定期巡检与孤儿地址回收"),
        ("碎片化", "地址零散分布，无法满足大块需求", "统一 CIDR 划分，避免手工零散分配"),
        ("跨节点不共享池", "每节点池独立，忙闲不均", "用集中式 IPAM（如 Calico IPAM 块池）"),
    ]
    print(f"{'成因':<20}{'表现':<34}{'规避'}")
    print(SUB)
    for a, b, c in causes:
        print(f"{a:<20}{b:<34}{c}")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. {NODES} 节点 × /{POD_CIDR_PREFIX} 共可分配 {NODES * 254} 个 Pod 地址，池子有限。")
    print(f"2. 场景 A（立即回收）分配失败 {res_a['failed']} 次；"
          f"场景 B（延迟回收）{res_b['failed']} 次；场景 C（泄漏）{res_c['failed']} 次。")
    print("3. 地址耗尽的根因常是「回收不及时」与「CIDR 规划过小」，不是分配算法问题。")
    print("4. 规避手段：合理预留 + 集中式 IPAM + 定期回收孤儿地址 + 监控池水位。")
    print()


if __name__ == "__main__":
    main()
