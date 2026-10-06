#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MTU / MSS 推导、IP 分片与 MTU 黑洞演示。

运行: python3 mtu_mss.py
"""
import sys

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

IPV4_HDR = 20
IPV6_HDR = 40
TCP_HDR = 20


def mss_table() -> None:
    print(SUB)
    print("【一】MSS 推导：MSS = MTU - IP 头 - TCP 头")
    print(SUB)
    print(f"{'场景':<22}{'MTU':<8}{'IP头':<7}{'TCP头':<7}{'MSS':<8}{'推导'}")
    print(SUB)
    rows = [
        ("标准以太网 IPv4", 1500, IPV4_HDR, TCP_HDR),
        ("标准以太网 IPv6", 1500, IPV6_HDR, TCP_HDR),
        ("PPPoE 链路 IPv4", 1492, IPV4_HDR, TCP_HDR),
        ("GRE 隧道内层 IPv4", 1476, IPV4_HDR, TCP_HDR),
        ("IPsec 隧道内层 IPv4", 1400, IPV4_HDR, TCP_HDR),
        ("IPv6 最小 MTU 要求", 1280, IPV6_HDR, TCP_HDR),
    ]
    for name, mtu, iph, tcph in rows:
        mss = mtu - iph - tcph
        expr = f"{mtu} - {iph} - {tcph}"
        print(f"{name:<22}{mtu:<8}{iph:<7}{tcph:<7}{mss:<8}{expr} = {mss}")
    print(SUB)
    print(">>> 结论：以太网 MTU=1500 时 IPv4 的 MSS=1460、IPv6 的 MSS=1440，")
    print("          隧道每多一层封装就吃掉一层头部，MSS 必须相应调小")


def fragment(payload_len: int, mtu: int) -> list:
    """把 payload_len 字节的 IP 载荷按 MTU 分片，返回 [(offset单位8B, 载荷, MF)]。"""
    max_data = ((mtu - IPV4_HDR) // 8) * 8      # 分片载荷必须是 8 字节整数倍
    frags = []
    offset = 0
    remain = payload_len
    while remain > max_data:
        frags.append((offset, max_data, True))
        offset += max_data // 8
        remain -= max_data
    frags.append((offset, remain, False))
    return frags


def frag_demo() -> None:
    print()
    print(SUB)
    print("【二】IP 分片：MTU=1500，一个 3000 字节的 IP 载荷如何被切开")
    print(SUB)
    payload = 3000
    mtu = 1500
    max_data = ((mtu - IPV4_HDR) // 8) * 8
    print(f"  单个分片最大载荷 = floor((MTU - IP头) / 8) * 8 = "
          f"floor(({mtu} - {IPV4_HDR}) / 8) * 8 = {max_data} 字节")
    print(f"  （必须按 8 字节对齐，因为片偏移字段以 8 字节为单位计数）")
    print()
    frags = fragment(payload, mtu)
    print(f"{'分片':<7}{'片偏移(单位)':<14}{'载荷(B)':<10}{'帧长(B)':<10}{'MF':<6}{'说明'}")
    print(SUB)
    total_wire = 0
    for i, (off, data, mf) in enumerate(frags, 1):
        wire = IPV4_HDR + data + 14       # +以太网头便于对照
        total_wire += IPV4_HDR + data
        note = "还有后续分片" if mf else "最后一片"
        print(f"{i:<7}{off:<14}{data:<10}{wire:<10}{int(mf):<6}{note}")
    print(SUB)
    print(f"  分片总长度 = {total_wire} 字节，比原始 {IPV4_HDR + payload} 字节多 "
          f"{total_wire - (IPV4_HDR + payload)} 字节（每个分片都重复一个 IP 头）")
    print(f"  验证偏移：{frags[-1][0]} × 8 + {frags[-1][1]} = "
          f"{frags[-1][0] * 8 + frags[-1][1]} = 原始载荷 {payload} 字节 ✓")
    print(">>> 结论：分片以 8 字节为粒度、每片重复 IP 头；分片越多开销越大，且丢一片全包作废")


def blackhole_demo(icmp_allowed: bool) -> None:
    print()
    print(SUB)
    title = "【三】MTU 黑洞：中间链路 MTU 1400，DF=1，且 " + \
            ("ICMP 可正常回送（PMTUD 生效）" if icmp_allowed else "ICMP 被防火墙丢弃（PMTUD 失效）")
    print(title)
    print(SUB)
    print("  拓扑：PC1(MTU 1500) --- R1 --- R2(该链路 MTU 1400) --- Server")
    print()
    steps = [
        ("PC1 发送 TCP SYN，长度 60 字节（< 1400，无需分片）", "R2 正常转发", True),
        ("Server 回 SYN-ACK，60 字节", "R2 正常转发", True),
        ("PC1 完成三次握手，连接建立", "连接 ESTABLISHED", True),
        ("PC1 发送 1500 字节数据段，IP 头 DF=1", "R2 需分片但 DF=1，无法转发", False),
    ]
    for action, result, ok in steps:
        mark = "通过" if ok else "受阻"
        print(f"  动作: {action}")
        print(f"        结果: {result}   [{mark}]")
    print()
    if icmp_allowed:
        print("  R2 向 PC1 回 ICMP type 3 code 4（Fragmentation Needed，DF set），")
        print("  并携带下一跳 MTU = 1400。PC1 触发 PMTUD，把 MSS 降到 1400 - 20 - 20 = 1360。")
        print("  重传后报文长度 = 1360 + 40 = 1400 ≤ 1400，顺利通过。")
        print()
        print(">>> 结论：PMTUD 生效时，黑洞自愈，用户只会感到首次传输略慢。")
    else:
        print("  R2 回送的 ICMP type 3 code 4 被沿途防火墙策略丢弃，PC1 收不到。")
        print("  PC1 不知道要降 MSS，按 RTO 反复重传同样的 1500 字节报文，一直超时。")
        print()
        print("  用户现象：ping（小包）通、SSH 登录成功（小包）、但一传大文件/打开大页面就卡死。")
        print(">>> 结论：这就是典型的 MTU 黑洞——不是链路断，是「大包过不去、小包正常」。")
        print("          排查：在 PC1 ping -M do -s 1472（Linux）或 ping -l 1472 -f（Windows）逐级缩小；")
        print("          缓解：路由器上 ip tcp adjust-mss 1360，或在主机上启用 tcp_mtu_probing=1。")


def main() -> None:
    print(SEP)
    print("MTU / MSS 推导 · IP 分片 · MTU 黑洞演示")
    print(SEP)

    mss_table()
    frag_demo()
    blackhole_demo(icmp_allowed=True)
    blackhole_demo(icmp_allowed=False)

    print()
    print(SUB)
    print("【四】MTU 与 MSS 的关系速查")
    print(SUB)
    print(f"{'术语':<12}{'所在层':<10}{'含义':<34}{'以太网典型值'}")
    print(SUB)
    rows = [
        ("MTU", "L3", "链路层可承载的最大 IP 载荷长度", "1500 字节"),
        ("MSS", "L4", "TCP 报文段中的数据部分最大长度", "1460 字节(IPv4)"),
        ("MRU", "L3", "接收方向的最大可接收单元（PPP 用语）", "等于 MTU"),
        ("PMTUD", "L3", "路径 MTU 发现，靠 ICMP 回送下一跳 MTU", "依赖 ICMP 可用"),
    ]
    for a, b, c, d in rows:
        print(f"{a:<12}{b:<10}{c:<34}{d}")
    print(SUB)
    print(f"关系式：MSS = MTU - IP头({IPV4_HDR}) - TCP头({TCP_HDR}) "
          f"= 1500 - 20 - 20 = 1460")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. MSS = MTU - IP 头 - TCP 头；以太网 IPv4 下为 1460，IPv6 下为 1440。")
    print("2. 分片载荷按 8 字节对齐，每片重复 IP 头，丢一片则整个原分组无法重组。")
    print("3. MTU 黑洞的判据是「小包通、大包卡」，根因是 DF=1 且 PMTUD 所需的 ICMP 被丢。")
    print("4. 缓解手段：中间设备 ip tcp adjust-mss，主机开启 tcp_mtu_probing，或直接调低 MSS。")
    print()


if __name__ == "__main__":
    main()
