#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Overlay 封装开销与 MTU/MSS 规划：VXLAN/GRE/IPsec 逐项算，给出内层建议值。

运行: python3 overlay_mtu.py
"""
import sys
from dataclasses import dataclass

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

PHYS_MTU = 1500
OUTER_ETH = 14
OUTER_IPV4 = 20
OUTER_IPV6 = 40
UDP = 8
VXLAN = 8
GENEVE = 8
GRE_BASE = 4
GRE_KEY = 4
INNER_ETH = 14
TCP = 20


@dataclass
class Encap:
    name: str
    fixed: int          # 除填充外的固定开销
    padded: bool        # 是否需要 16 字节对齐（IPsec）
    note: str

    def overhead(self, inner_mtu: int) -> int:
        if not self.padded:
            return self.fixed
        pad = (-(inner_mtu + 2)) % 16           # 加密区对齐到 16 字节
        return self.fixed + pad


def max_inner_mtu(enc: Encap) -> int:
    """在物理 MTU 约束下求内层可承载的最大 IP 报文长度。"""
    if not enc.padded:
        return PHYS_MTU - enc.fixed
    # IPsec：20+8+16+P+pad+2+12 <= 1500 且 (P+2+pad) % 16 == 0
    best = 0
    for p in range(PHYS_MTU, 0, -1):
        pad = (-(p + 2)) % 16
        if enc.fixed + pad + p <= PHYS_MTU:
            best = p
            break
    return best


def encap_list() -> list:
    return [
        Encap("无封装(纯以太网)", 0, False, "基线，内层 MTU = 1500"),
        Encap("802.1Q VLAN 标签", 4, False, "标签插入以太网头，占用 4 字节"),
        Encap("GRE 隧道", OUTER_IPV4 + GRE_BASE, False, "外层 IP 20 + GRE 基本头 4"),
        Encap("GRE + GRE Key(TNI)", OUTER_IPV4 + GRE_BASE + GRE_KEY, False,
              "多 4 字节 Key（NVGRE 的 TNI 就在此）"),
        Encap("IPsec 隧道模式 ESP", OUTER_IPV4 + 8 + 16 + 2 + 12, True,
              "IP 20 + ESP头 8 + IV 16 + 尾 2 + ICV 12，另加 16B 对齐填充"),
        Encap("VXLAN", OUTER_ETH + OUTER_IPV4 + UDP + VXLAN, False,
              "外以太网 14 + IP 20 + UDP 8 + VXLAN 8"),
        Encap("GENEVE", OUTER_ETH + OUTER_IPV4 + UDP + GENEVE, False,
              "外以太网 14 + IP 20 + UDP 8 + GENEVE 8"),
        Encap("VXLAN + IPsec", OUTER_ETH + OUTER_IPV4 + UDP + VXLAN +
              OUTER_IPV4 + 8 + 16 + 2 + 12, True,
              "先 VXLAN 再整段放进 IPsec 隧道，开销叠加"),
    ]


def main() -> None:
    print(SEP)
    print("Overlay 封装开销与 MTU / MSS 规划（物理 MTU 固定为 1500）")
    print(SEP)
    print("计算口径：物理 MTU 1500 = 外层以太网可承载的 IP 报文上限；")
    print("          内层 MTU = 1500 - 外层封装开销；内层 MSS = 内层 MTU - 内层 IP 头 - TCP 头。")

    print()
    print(SUB)
    print("【一】各封装的内层可用 MTU 与 MSS")
    print(SUB)
    print(f"{'封装方式':<20}{'固定开销':>8}{'对齐后开销':>10}{'内层MTU':>9}"
          f"{'MSS(v4)':>9}{'MSS(v6)':>9}")
    print(SUB)
    rows = []
    for enc in encap_list():
        inner = max_inner_mtu(enc)
        ov = enc.overhead(inner)
        mss4 = inner - OUTER_IPV4 - TCP
        mss6 = inner - OUTER_IPV6 - TCP
        rows.append((enc, inner, ov, mss4, mss6))
        print(f"{enc.name:<20}{enc.fixed:>8}{ov:>10}{inner:>9}{mss4:>9}{mss6:>9}")
    print(SUB)
    print("说明：IPsec 的「对齐后开销」包含把加密区补齐到 16 字节整数倍的填充。")

    print()
    print(SUB)
    print("【二】重点推导：VXLAN")
    print(SUB)
    print(f"  外层以太网头      = {OUTER_ETH} B")
    print(f"  外层 IPv4 头      = {OUTER_IPV4} B")
    print(f"  外层 UDP 头       = {UDP} B（目的端口 4789）")
    print(f"  VXLAN 头          = {VXLAN} B（含 24 位 VNI）")
    overhead = OUTER_ETH + OUTER_IPV4 + UDP + VXLAN
    print(f"  合计固定开销      = {OUTER_ETH} + {OUTER_IPV4} + {UDP} + {VXLAN} = {overhead} B")
    print(f"  内层 IP MTU       = {PHYS_MTU} - {overhead} = {PHYS_MTU - overhead} B")
    print(f"  内层 TCP MSS(v4)  = {PHYS_MTU - overhead} - 20 - 20 = {PHYS_MTU - overhead - 40} B")
    print(">>> 结论：VXLAN 环境下内层主机 MTU 应设 1450、MSS 应设 1410，")
    print("          否则内层 1500 字节的报文封装后变 1550，在 underlay 上超 MTU。")

    print()
    print(SUB)
    print("【三】不做规划的后果（以 VXLAN 为例）")
    print(SUB)
    inner_pkt = 1500
    outer_pkt = inner_pkt + overhead
    print(f"  内层主机按默认 MTU 1500 发送：内层 IP 报文 = {inner_pkt} B")
    print(f"  加上 VXLAN 封装后外层 IP 报文 = {inner_pkt} + {overhead} = {outer_pkt} B")
    print(f"  外层链路 MTU = {PHYS_MTU} B，超长 {outer_pkt - PHYS_MTU} B")
    print()
    print("  当外层 IP 头 DF=1（内核默认对 TCP 设 DF）：")
    print("    中间设备不能分片 -> 丢弃 -> 回 ICMP type 3 code 4")
    print("    若 ICMP 被防火墙拦截 -> 发送方收不到通知 -> 大包持续重传 -> MTU 黑洞")
    print("    用户现象：ping 通、SSH 能登、传大文件卡死。")
    print("  当外层 IP 头 DF=0：")
    print("    外层分片 -> 重组开销增大、丢一片整包作废 -> 吞吐下降、抖动上升。")

    print()
    print(SUB)
    print("【四】三种规划方案对比")
    print(SUB)
    print(f"{'方案':<26}{'做法':<30}{'代价'}")
    print(SUB)
    plans = [
        ("方案 A：调小内层 MTU", "内层主机 MTU 1450 / MSS 1410", "需逐台改，虚机镜像需统一"),
        ("方案 B：MSS 钳制", "虚拟网关 ip tcp adjust-mss 1410", "只对 TCP 有效，UDP/ICMP 不覆盖"),
        ("方案 C：Underlay 用巨帧", "物理与隧道链路 MTU 设 9000", "需全网设备一致，一处没改就断"),
    ]
    for a, b, c in plans:
        print(f"{a:<26}{b:<30}{c}")

    print()
    print(SUB)
    print("【五】各封装的 MSS 推荐值（可直接抄进配置）")
    print(SUB)
    print(f"{'封装方式':<20}{'建议内层MTU':>12}{'建议MSS(v4)':>12}{'建议MSS(v6)':>12}")
    print(SUB)
    for enc, inner, _ov, mss4, mss6 in rows:
        print(f"{enc.name:<20}{inner:>12}{mss4:>12}{mss6:>12}")
    print(SUB)
    print(">>> 结论：配置 MSS 钳制时取值 = 内层 MTU - 40（IPv4）/ - 60（IPv6），")
    print("          并向下取整到 8 的整数倍以兼顾各类分片场景。")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. VXLAN 固定开销 {overhead} B，物理 MTU 1500 下内层 MTU 只能到 "
          f"{PHYS_MTU - overhead}、MSS 到 {PHYS_MTU - overhead - 40}。")
    print("2. GRE 开销 24 B、IPsec 隧道模式开销约 50~73 B（含填充），叠加后更大。")
    print("3. 不规划的直接后果是 MTU 黑洞（大包卡死）或外层分片（吞吐与抖动恶化）。")
    print("4. 工程上优先「Underlay 巨帧 + MSS 钳制」组合，减少对内层主机的侵入。")
    print()


if __name__ == "__main__":
    main()
