#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构造 UDP 报文并用伪首部计算校验和，演示 16 位分组求和与回卷。

运行: python3 udp_checksum.py
"""
import sys

sys.dont_write_bytecode = True


def hex16(value: int) -> str:
    return "0x%04X" % (value & 0xFFFF)


def sum_16bit_words(data: bytes) -> tuple[int, list[tuple[str, int]]]:
    """把字节流按 16 位分组求和，返回（折叠前的和，逐项明细）。"""
    detail: list[tuple[str, int]] = []
    total = 0
    if len(data) % 2 == 1:  # 奇数长度补一个 0 字节
        data = data + b"\x00"
    for i in range(0, len(data), 2):
        word = (data[i] << 8) | data[i + 1]
        total += word
        detail.append(("%04X" % word, word))
    return total, detail


def fold_carry(total: int) -> tuple[int, int]:
    """把超过 16 位的进位回卷折叠到低 16 位。返回（折叠次数记录, 结果）。"""
    folds = 0
    while total > 0xFFFF:
        carry = total >> 16
        total = (total & 0xFFFF) + carry
        folds += 1
    return folds, total


def checksum(data: bytes) -> int:
    total, _ = sum_16bit_words(data)
    _, folded = fold_carry(total)
    return (~folded) & 0xFFFF


def build_pseudo_header(src: str, dst: str, proto: int, udp_len: int) -> bytes:
    import ipaddress

    s = int(ipaddress.IPv4Address(src)).to_bytes(4, "big")
    d = int(ipaddress.IPv4Address(dst)).to_bytes(4, "big")
    return s + d + b"\x00" + bytes([proto]) + udp_len.to_bytes(2, "big")


def build_udp(sport: int, dport: int, payload: bytes) -> bytes:
    length = 8 + len(payload)
    header = sport.to_bytes(2, "big") + dport.to_bytes(2, "big")
    header += length.to_bytes(2, "big") + b"\x00\x00"  # 校验和先置 0
    return header + payload


def main() -> None:
    src = "192.0.2.10"
    dst = "198.51.100.20"
    sport, dport = 53000, 53
    payload = b"DNS?"  # 4 字节，制造奇数长度场景由另一例覆盖
    print("=" * 68)
    print("UDP 校验和计算演示（含 IPv4 伪首部）")
    print("=" * 68)
    print("源 IP / 目的 IP : %s -> %s" % (src, dst))
    print("源端口 / 目的端口: %d -> %d" % (sport, dport))
    print("载荷            : %r（%d 字节）" % (payload, len(payload)))

    udp_len = 8 + len(payload)
    pseudo = build_pseudo_header(src, dst, 17, udp_len)
    udp = build_udp(sport, dport, payload)
    print("\n[1] IPv4 伪首部（12 字节，不真正在线路上发送，只参与校验计算）")
    print("    源IP(4) | 目的IP(4) | 全0(1) | 协议=17(1) | UDP长度(2)")
    print("    十六进制: " + pseudo.hex(" "))
    print("    UDP 长度字段 = 8(首部) + %d(载荷) = %d" % (len(payload), udp_len))

    print("\n[2] UDP 首部（8 字节）：源端口 | 目的端口 | 长度 | 校验和(先置0)")
    print("    十六进制: " + udp[:8].hex(" "))
    print("    完整报文: " + udp.hex(" "))

    print("\n[3] 按 16 位分组求和（伪首部 + UDP 头 + 载荷 + 必要时补 0 字节）")
    buf = pseudo + udp
    if len(buf) % 2 == 1:
        print("    注意：总长为奇数，末尾补 1 个 0x00 字节后再分组")
    total, detail = sum_16bit_words(buf)
    for i, (h, _v) in enumerate(detail):
        print("    第 %2d 个 16 位字: %s" % (i + 1, h))
    print("    未折叠的原始和 = 0x%X（十进制 %d）" % (total, total))

    print("\n[4] 进位回卷（把高 16 位不断加到低 16 位，直到不超过 0xFFFF）")
    folds, folded = fold_carry(total)
    print("    回卷次数 = %d" % folds)
    print("    折叠后结果 = %s（十进制 %d）" % (hex16(folded), folded))

    ck = (~folded) & 0xFFFF
    print("\n[5] 取反得到校验和 = ~%s = %s" % (hex16(folded), hex16(ck)))
    print(">>> 结论：该 UDP 报文校验和字段应填入 %s" % hex16(ck))

    print("\n[6] 接收端验证：把校验和填入后再对整个报文求和，结果应为 0xFFFF")
    udp2 = udp[:6] + ck.to_bytes(2, "big") + payload
    total2, _ = sum_16bit_words(pseudo + udp2)
    _, folded2 = fold_carry(total2)
    print("    填入校验和后折叠和 = %s" % hex16(folded2))
    print(">>> 结论：校验通过（接收端求和结果为 0xFFFF，取反后为 0x0000）")

    print("\n[7] 边界：计算结果为 0x0000 时，按 RFC 768 必须发送 0xFFFF")
    print("    因为 0x0000 表示「发送方未计算校验和」，语义冲突。")
    zero_case = 0x0000
    on_wire = 0xFFFF if zero_case == 0 else zero_case
    print("    计算得到 %s -> 线路上实际填 %s" % (hex16(zero_case), hex16(on_wire)))

    print("\n" + "=" * 68)
    print("小结")
    print("-" * 68)
    print("1. UDP 校验和覆盖「伪首部 + UDP 首部 + 载荷」，伪首部把 IP 层地址也纳入校验。")
    print("2. 算法三步：16 位分组求和 -> 进位回卷到低 16 位 -> 取反码（~）得到结果。")
    print("3. 校验和为 0x0000 时线上必须写 0xFFFF，这是 IPv4 UDP 独有的历史约定。")
    print("4. 接收端把校验和一起求和应得 0xFFFF，以此判断报文是否被篡改或损坏。")


if __name__ == "__main__":
    main()
