#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TTL 逐跳探测建模：重建 traceroute 路径、识别 * 超时、解释非对称路由。

运行: python3 traceroute_model.py
"""
import sys
from dataclasses import dataclass

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78


@dataclass
class Hop:
    index: int
    name: str
    addr: str
    reply: str          # time_exceeded / port_unreachable / silent
    rtt_ms: float


# 正向路径：PC1 -> R1 -> R2 -> R3 -> Server
FORWARD = [
    Hop(1, "R1(近端)", "192.0.2.1", "time_exceeded", 1.2),
    Hop(2, "R2(城域)", "203.0.113.2", "time_exceeded", 4.7),
    Hop(3, "R3(骨干)", "203.0.113.6", "time_exceeded", 9.3),
    Hop(4, "Server", "198.51.100.10", "port_unreachable", 12.8),
]

# 一个不响应的中间跳（ICMP 被限速或策略丢弃）
SILENT = Hop(2, "R2(城域)", "203.0.113.2", "silent", 0.0)


def probe(ttl: int, path: list) -> str:
    """发一个 TTL=ttl 的 UDP 探测包，返回本跳的响应描述。"""
    if ttl > len(path):
        return "无响应（TTL 超过路径长度，理论上不会发生）"
    hop = path[ttl - 1]
    if hop.reply == "time_exceeded":
        return (f"ICMP 超时 (type 11 code 0) 来自 {hop.addr}"
                f"，RTT = {hop.rtt_ms:.1f} ms")
    if hop.reply == "port_unreachable":
        return (f"ICMP 端口不可达 (type 3 code 3) 来自 {hop.addr}"
                f"，目标到达，RTT = {hop.rtt_ms:.1f} ms")
    return f"* 超时（{hop.addr} 未回 ICMP，可能被限速或策略丢弃）"


def render_trace(path: list, title: str) -> None:
    print(SUB)
    print(title)
    print(SUB)
    print(f"{'TTL':<5}{'本跳':<12}{'响应'}")
    print(SUB)
    for ttl in range(1, len(path) + 2):
        hop_name = path[ttl - 1].name if ttl <= len(path) else "-"
        print(f"{ttl:<5}{hop_name:<12}{probe(ttl, path)}")
    print(SUB)
    print("重建路径：")
    chain = " -> ".join(f"{hop.name}[{hop.addr}]" for hop in path)
    print(f"  PC1 -> {chain}")
    arrived = path[-1].reply == "port_unreachable"
    print(f">>> 结论：{'探测到目标' if arrived else '未确认到达目标'}；"
          f"共 {len(path)} 跳，端到端 RTT ≈ {path[-1].rtt_ms:.1f} ms")


def render_asymmetric() -> None:
    print(SUB)
    print("【三】非对称路由：为什么 traceroute 显示的路径与实际转发路径不一致")
    print(SUB)
    print("  正向（探测包，TTL 逐跳递增）：")
    print("    PC1 -> R1 -> R2 -> R3 -> Server")
    print("  反向（Server 的回包，走另一条 IGP 度量更优的路径）：")
    print("    Server -> R3 -> R4 -> R1 -> PC1")
    print()
    print("  于是 traceroute 打印的「第 N 跳地址」= 该跳回包里的源地址：")
    print(f"    {'TTL':<5}{'正向实际经过':<16}{'回包源地址(显示)':<20}{'是否一致'}")
    print("    " + SUB)
    rows = [
        (1, "R1", "R1(192.0.2.1)", "一致"),
        (2, "R2", "R2(203.0.113.2)", "一致"),
        (3, "R3", "R3(203.0.113.6)", "一致"),
        (4, "Server", "Server(198.51.100.10)", "一致"),
    ]
    for ttl, fwd, back, same in rows:
        print(f"    {ttl:<5}{fwd:<16}{back:<20}{same}")
    print()
    print("  若反向路径在 R3 之后走 R4：")
    rows2 = [
        (3, "R3", "R3(203.0.113.6)", "一致"),
        (4, "R4 也回超时", "R4(203.0.113.10)", "不一致：显示的是回程设备"),
    ]
    for ttl, fwd, back, same in rows2:
        print(f"    {ttl:<5}{fwd:<16}{back:<20}{same}")
    print(">>> 结论：traceroute 记录的是「每跳回包的源地址」，非对称路由下显示的是回程设备，")
    print("          不能用它推断真实单向转发路径；要验证单向路径需两端同时抓包比对 TTL。")
    print(">>> 排查技巧：若 traceroute 在第 3 跳后开始出现意外地址，先查 IGP 度量与策略路由。")


def main() -> None:
    print(SEP)
    print("traceroute 逐跳探测建模（基于 TTL 超时机制，纯模拟）")
    print(SEP)

    print(SUB)
    print("【一】正常路径探测")
    print(SUB)
    render_trace(FORWARD, "正常情况：每跳都回 ICMP 超时，最后一跳回端口不可达")

    print()
    print(SUB)
    print("【二】中间跳不响应（ICMP 限速 / 被 ACL 过滤）")
    print(SUB)
    path2 = FORWARD[:1] + [SILENT] + FORWARD[2:]
    render_trace(path2, "R2 不回 ICMP：该跳显示 *，但后续跳仍可继续探测")

    print()
    render_asymmetric()

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. traceroute 依赖 TTL：TTL 减到 0 的路由器回 ICMP 超时(type 11)，从而暴露自己的地址。")
    print("2. 最后一跳对 UDP 探测回 ICMP 端口不可达(type 3 code 3)，标志探测结束。")
    print("3. 中间跳显示 * 不代表该跳故障，只代表它不回 ICMP；只要后续跳能继续，路径就是通的。")
    print("4. 非对称路由下 traceroute 显示的是回程设备地址，不能直接当作单向转发路径。")
    print()


if __name__ == "__main__":
    main()
