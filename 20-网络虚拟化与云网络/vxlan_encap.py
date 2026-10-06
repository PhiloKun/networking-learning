#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VXLAN 封装全过程：内层帧 -> VXLAN 头 -> UDP 4789 -> 外层 IP -> 外层以太网。

运行: python3 vxlan_encap.py
"""
import ipaddress
import struct
import sys

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

VXLAN_PORT = 4789
VXLAN_HDR = 8           # Flags(1) + Reserved(3) + VNI(3) + Reserved(1)
OUTER_ETH = 14
OUTER_IP = 20
OUTER_UDP = 8
INNER_ETH = 14
INNER_IP = 20
INNER_TCP = 20

VNI_MAX = 0xFFFFFF      # 24 位 = 16,777,215

# VTEP 转发表（BGP EVPN Type-2 学习结果）：内层 MAC -> 远端 VTEP
FDB = {
    "02:00:00:00:00:0B": "203.0.113.2",
    "02:00:00:00:00:0C": "203.0.113.3",
}


def mac_to_bytes(text: str) -> bytes:
    return bytes(int(p, 16) for p in text.split(":"))


def csum16(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) | data[i + 1]
    while total > 0xFFFF:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def build_ipv4(src: str, dst: str, proto: int, payload: bytes, ttl: int = 64) -> bytes:
    total_len = INNER_IP + len(payload)
    hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total_len, 0x1234, 0x4000,
                      ttl, proto, 0,
                      ipaddress.IPv4Address(src).packed,
                      ipaddress.IPv4Address(dst).packed)
    ck = csum16(hdr)
    hdr = hdr[:10] + struct.pack("!H", ck) + hdr[12:]
    return hdr + payload


def build_vxlan(vni: int) -> bytes:
    """VXLAN 头 8 字节：0x08 标志(I 位) + 24 位保留 + 24 位 VNI + 8 位保留。"""
    if not 0 <= vni <= VNI_MAX:
        raise ValueError("VNI 超出 24 位范围")
    value = (0x08 << 56) | (vni << 8)
    return struct.pack("!Q", value)


def decode_vxlan(blob: bytes) -> dict:
    value = struct.unpack("!Q", blob[:8])[0]
    flags = (value >> 56) & 0xFF
    vni = (value >> 8) & 0xFFFFFF
    return {"flags": flags, "i_bit": bool(flags & 0x08), "vni": vni}


def build_inner_frame() -> bytes:
    eth = mac_to_bytes("02:00:00:00:00:0B") + mac_to_bytes("02:00:00:00:00:0A") + \
        struct.pack("!H", 0x0800)
    tcp = struct.pack("!HHIIBBHHH", 51000, 443, 0x0A0B0C0D, 0, 0x50, 0x18, 65535, 0, 0)
    tcp += b"GET / HTTP/1.1\r\nHost: web\r\n\r\n"
    ip = build_ipv4("192.0.2.10", "192.0.2.20", 6, tcp)
    return eth + ip


def main() -> None:
    print(SEP)
    print("VXLAN 封装全过程（MAC-in-UDP，目的端口 4789）")
    print(SEP)
    print(f"VNI 24 位，最大可表示 {VNI_MAX:,} 个二层段（对比 VLAN 只有 4094 个）")
    print(f"转发表（EVPN Type-2 学习）：{', '.join(f'{k}->{v}' for k, v in FDB.items())}")

    vni = 100
    inner = build_inner_frame()

    print()
    print(SUB)
    print("【一】内层原始以太网帧（VTEP 收到的报文）")
    print(SUB)
    inner_payload = len(inner) - INNER_ETH - INNER_IP - INNER_TCP
    print(f"  内层目的 MAC : 02:00:00:00:00:0B")
    print(f"  内层源   MAC : 02:00:00:00:00:0A")
    print(f"  内层 IP      : 192.0.2.10 -> 192.0.2.20 (TCP 51000 -> 443)")
    print(f"  内层帧长度   : {INNER_ETH}(以太网) + {INNER_IP}(IP) + {INNER_TCP}(TCP) "
          f"+ {inner_payload}(载荷) = {len(inner)} 字节")

    print()
    print(SUB)
    print("【二】逐层封装（自内向外）")
    print(SUB)
    vxlan = build_vxlan(vni)
    udp = struct.pack("!HHHH", 40000, VXLAN_PORT, OUTER_UDP + len(vxlan), 0)
    outer_payload = udp + vxlan + inner
    outer_ip = build_ipv4("203.0.113.1", "203.0.113.2", 17, outer_payload)
    outer_eth = mac_to_bytes("02:00:00:00:00:02") + mac_to_bytes("02:00:00:00:00:01") + \
        struct.pack("!H", 0x0800)
    outer_frame = outer_eth + outer_ip

    layers = [
        ("内层以太网帧", len(inner), "VTEP 收到的原始帧，作为整体被封装"),
        ("VXLAN 头", VXLAN_HDR, "Flags(1)+Reserved(3)+VNI(3)+Reserved(1)"),
        ("外层 UDP 头", OUTER_UDP, f"目的端口固定 {VXLAN_PORT}，源端口由内层流哈希生成"),
        ("外层 IPv4 头", OUTER_IP, "源/目的为两端 VTEP 的 IP（underlay 地址）"),
        ("外层以太网头", OUTER_ETH, "underlay 的下一跳 MAC"),
    ]
    print(f"{'层':<16}{'字节':>6}   说明")
    print(SUB)
    running = 0
    for name, size, note in layers:
        running += size
        print(f"{name:<16}{size:>6}   {note}")
    print(SUB)
    total = len(outer_frame)
    overhead = total - len(inner)
    print(f"封装后总长度 = {total} 字节；原始内层帧 = {len(inner)} 字节")
    print(f">>> 结论：VXLAN 固定封装开销 = {OUTER_ETH}+{OUTER_IP}+{OUTER_UDP}+{VXLAN_HDR} "
          f"= {overhead} 字节（不含内层帧本身的头部）")
    print(f">>> VNI = {vni}（0x{vni:06X}），占用 VXLAN 头中第 4~6 字节共 24 位")
    print(f">>> VXLAN 头十六进制: {vxlan.hex(' ')}")

    print()
    print(SUB)
    print("【三】VTEP 解封装：剥掉外层，按内层目的 MAC 查转发表")
    print(SUB)
    print(f"  [1] 收到外层帧，目的 MAC = 02:00:00:00:00:01（本 VTEP），类型 0x0800")
    print(f"  [2] 解析外层 IP：203.0.113.1 -> 203.0.113.2，协议 17(UDP)")
    print(f"  [3] 解析 UDP：目的端口 {VXLAN_PORT} -> 进入 VXLAN 处理流程")
    info = decode_vxlan(vxlan)
    print(f"  [4] 解析 VXLAN：I 位 = {info['i_bit']}，VNI = {info['vni']}")
    inner_dst = ":".join("%02X" % b for b in inner[0:6])
    print(f"  [5] 内侧以太网目的 MAC = {inner_dst}")
    if inner_dst in FDB:
        print(f"  [6] 查转发表命中 -> 远端 VTEP = {FDB[inner_dst]}（本地直达则免封装）")
    else:
        print(f"  [6] 查表未命中 -> 泛洪 / 送 ARP 代答")
    print(f">>> 结论：解封装后交付给内层网络的就是最初那个 {len(inner)} 字节以太网帧，"
          f"内层主机完全感知不到 VXLAN")

    print()
    print(SUB)
    print("【四】隧道对比")
    print(SUB)
    print(f"{'隧道':<12}{'封装协议':<18}{'标识字段':<22}{'固定开销(B)'}")
    print(SUB)
    tunnels = [
        ("VXLAN", "MAC-in-UDP", "24 位 VNI（1600 万段）", 50),
        ("NVGRE", "MAC-in-GRE", "24 位 TNI（1600 万段）", 42),
        ("GENEVE", "以太网-in-UDP", "24 位 VNI + TLV 可变选项", 50),
        ("GRE", "IP-in-IP/GRE", "无段标识（靠 VRF 区分）", 38),
        ("VLAN", "802.1Q 标签", "12 位 VID（4094 段）", 4),
    ]
    for a, b, c, d in tunnels:
        print(f"{a:<12}{b:<18}{c:<22}{d}")
    print("  口径说明：固定开销 = 外层以太网 14 + 外层 IPv4 20 + 隧道自身头部；")
    print("            VLAN 的 4 字节为标签本身，不含重新封装的以太网头。")
    print(">>> 结论：VXLAN 用 50 字节开销换来 1600 万段与跨三层二层扩展能力，"
          "这是 Overlay 的根本价值")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. VXLAN 头固定 8 字节：1 字节 Flags（I 位 0x08）+ 3 字节保留 + 3 字节 VNI + 1 字节保留。")
    print("2. VNI 24 位可表示 16,777,215 个二层段，远超 VLAN 的 4094 个。")
    print(f"3. VXLAN 固定封装开销 = 14+20+8+8 = 50 字节，全部作用于 underlay 路径。")
    print("4. VTEP 解封装后按内层目的 MAC 查转发表转发，内层主机对 Overlay 无感知。")
    print()


if __name__ == "__main__":
    main()
