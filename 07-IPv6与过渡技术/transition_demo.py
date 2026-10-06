#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPv6 过渡技术对比：双栈 / 6to4 / ISATAP / NAT64 / DS-Lite 的封装结构与开销。

运行: python3 transition_demo.py
"""
import sys

sys.dont_write_bytecode = True

# (技术, 封装或转换方式, 外层协议号/端口, 额外字节, 能否穿 NAT, 需要什么, 适用场景, 主要局限)
TECH = [
    ("双栈 Dual Stack", "不做封装，同一设备同时跑 IPv4 与 IPv6 协议栈",
     "无", 0, "不涉及", "主机/路由器双栈", "新建网络、终端与业务都就绪时",
     "不解决 IPv4 地址枯竭，只是并行运行；需双份 ACL/QoS 维护"),
    ("手工隧道 GRE/IP6IP", "IPv6 包整体装进 IPv4 包（GRE 或 IP-in-IP）",
     "GRE=47 / IP-in-IP=41", 24, "不能（IPv4 隧道）", "两端固定公网 IPv4",
     "点对点稳定互联、实验环境", "需两端固定地址，N 条隧道 N² 复杂度，无法穿越 NAT"),
    ("6to4", "IPv6 包装进 IPv4，隧道地址由公网 IPv4 自动生成 2002::/16",
     "41", 20, "不能（需公网 IPv4）", "有公网 IPv4 的边界 + 中继 192.88.99.1",
     "早期快速接入 IPv6 互联网", "依赖中继可靠性差，NAT 后不可用，已被业界弃用"),
    ("ISATAP", "站点内自动隧道，把 IPv4 当二层，接口标识 ::5EFE:a.b.c.d",
     "41", 20, "不能（需 IPv4 可达）", "站内 IPv4 路由可达",
     "企业内网从 IPv4 渐进引入 IPv6", "只适合站内；需 DNS 配合；无法跨 NAT"),
    ("Teredo", "IPv6 装进 IPv4，再套 UDP，穿透 NAT",
     "UDP/3544", 28, "能（UDP 穿透）", "Teredo 客户端 + 中继 + 服务器",
     "NAT 后的主机访问 IPv6", "中继瓶颈、时延大、早期 Windows 常被策略关闭"),
    ("NAT64 + DNS64", "做头部翻译而非封装，IPv6 头换成 IPv4 头，前缀 64:ff9b::/96",
     "无（翻译）", 0, "不涉及", "NAT64 网关 + DNS64 解析器",
     "IPv6-only 网络访问 IPv4 互联网", "有状态、需 DNS64 配合、无法承载内嵌 IPv4 地址的协议"),
    ("DS-Lite", "IPv4 包整体装进 IPv6 包（软线 Softwire）",
     "IPv4-in-IPv6=4", 40, "不涉及", "B4（CPE）+ AFTR（运营商网关）",
     "运营商用 IPv6 承载 IPv4 接入（IPv4 地址集中复用）", "AFTR 是集中点；NAT 在运营商侧，排障链路变长"),
    ("464XLAT", "终端 CLAT 做无状态翻译 + 网络 PLAT 做有状态翻译",
     "无（两次翻译）", 0, "不涉及", "终端支持 CLAT + 运营商 PLAT",
     "IPv6-only 的移动网络访问 IPv4", "需终端支持；应用若硬编码 IPv4 地址仍会失败"),
]

# 隧道封装的字节拆解：(名称, 外层IP, 外层传输/UDP, 隧道头, 内层IP头, 说明)
OVH = [
    ("双栈（无封装）", 0, 0, 0, 40, "原样转发，IPv6 头 40 字节就是全部开销"),
    ("6to4 / ISATAP（IPv6-in-IPv4）", 20, 0, 0, 40, "外层 IPv4 20 字节，协议号 41，内层 IPv6"),
    ("GRE over IPv4（IPv6-in-GRE）", 20, 0, 4, 40, "GRE 基础头 4 字节（不含 Key/Seq），内层 IPv6"),
    ("Teredo（IPv6-in-UDP-in-IPv4）", 20, 8, 0, 40, "IPv4 20 + UDP 8，目的端口 3544，内层 IPv6"),
    ("DS-Lite（IPv4-in-IPv6）", 40, 0, 0, 20, "外层 IPv6 40 字节，协议号 4，内层是 IPv4"),
    ("IPsec 隧道（IPv6 in ESP）", 20, 0, 24, 40, "ESP 头 SPI+序号 8 + IV 16（AES-CBC 示例），ICV 另计 16"),
]


def main() -> int:
    print("=" * 108)
    print("IPv6 过渡技术对比（双栈 / 隧道 / 翻译，教学模拟，不发起任何真实隧道）")
    print("=" * 108)
    headers = ("技术", "外层协议号/端口", "额外字节", "穿 NAT", "适用场景")
    print(f"{headers[0]:<20}{headers[1]:<20}{headers[2]:>8}  {headers[3]:<10}{headers[4]}")
    print("-" * 108)
    for name, _enc, outer, ovh, nat, _need, scene, _limit in TECH:
        print(f"{name:<20}{outer:<20}{ovh:>8}  {nat:<10}{scene}")
    print("-" * 108)
    print()
    print("封装结构逐项拆解（字节）")
    print("-" * 108)
    print(f"{'方式':<34}{'外层IP':>8}{'UDP':>6}{'隧道头':>8}{'合计开销':>10}  {'说明'}")
    print("-" * 108)
    for name, ip, udp, tun, _ilen, note in OVH:
        total = ip + udp + tun
        print(f"{name:<34}{ip:>8}{udp:>6}{tun:>8}{total:>10}  {note}")
    print("-" * 108)
    print()
    print("封装开销对 MTU 的连锁影响（物理链路 MTU 1500 字节，TCP MSS = 内层 MTU − 内层 IP 头 − TCP 头）")
    print("-" * 108)
    base = 1500
    for name, ip, udp, tun, ilen, _note in OVH:
        if ip == 0:
            continue
        inner_mtu = base - ip - udp - tun
        mss = inner_mtu - ilen - 20
        print(f"  {name:<34} 内层可用 MTU = {base} − {ip + udp + tun} = {inner_mtu}"
              f"  → TCP MSS 建议 {mss}（内层 IP 头 {ilen}）")
    print("-" * 108)
    print("  >>> 结论：只要做了隧道，内层 MTU 必然变小；必须同步下调内层接口 MTU 或做 MSS 钳制，")
    print("            否则表现为「ping 通、小包通、大包卡死」的 MTU 黑洞（详见第 18 章）。")
    print()
    print("技术选型决策（按现状挑一条）")
    print("-" * 108)
    print("  1. 终端与业务都支持 IPv6、且网络设备支持 → 直接双栈，最简单也最稳。")
    print("  2. 只有两端有公网 IPv4、想点对点跑 IPv6 → 手工隧道（GRE/IP6IP），稳定可控。")
    print("  3. 企业内网要先让部分主机尝到 IPv6 → ISATAP，但只限站内、需 DNS 配合。")
    print("  4. 终端是 IPv6-only，却要访问 IPv4 互联网 → NAT64 + DNS64（配 464XLAT 更完整）。")
    print("  5. 运营商侧要用 IPv6 承载海量 IPv4 用户接入 → DS-Lite，把 NAT 集中到 AFTR。")
    print("  6. 6to4/Teredo 属于历史方案，新项目不应再选；老环境应尽快迁移到双栈或 NAT64。")
    print()
    print(">>> 结论：过渡技术的本质只有三类——并行（双栈）、封装（隧道）、翻译（NAT64/464XLAT）。")
    print(">>> 结论：封装不改变地址语义但增加开销，翻译改变地址语义但需要协议可被翻译。")
    print()
    print("小结")
    print("  1. 双栈是终局方案，隧道与翻译都是过渡手段，选型要看「谁有公网地址、谁能改」。")
    print("  2. IPv6-in-IPv4 用协议号 41，IPv4-in-IPv6 用协议号 4，Teredo 额外套 UDP/3544。")
    print("  3. 任何封装都会吃掉 MTU，部署隧道必须同步做 MTU/MSS 规划，否则出现大包黑洞。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
