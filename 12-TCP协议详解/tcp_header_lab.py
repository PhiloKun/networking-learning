#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手工构造并解析 TCP 首部（含 MSS 选项），逐字段打印比特位并验算含伪首部的校验和。

运行: python3 tcp_header_lab.py
"""
import sys
import struct
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


def hx(b):
    return " ".join(f"{x:02X}" for x in b)


def ip_bytes(ip):
    return bytes(int(x) for x in ip.split("."))


def ones_complement_sum(data):
    """16 位反码求和：分组相加、回卷进位，最后取反。"""
    if len(data) % 2:
        data += b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) | data[i + 1]
        if s > 0xFFFF:
            s = (s & 0xFFFF) + (s >> 16)
    return s & 0xFFFF


def checksum(data):
    return (~ones_complement_sum(data)) & 0xFFFF


def build_options():
    """MSS(1460) + SACK Permitted + NOP + Window Scale(7) + 时间戳，补齐到 4 字节倍数。"""
    opts = b""
    opts += struct.pack("!BBH", 2, 4, 1460)          # MSS，4 字节
    opts += struct.pack("!BB", 4, 2)                 # SACK Permitted，2 字节
    opts += struct.pack("!B", 1)                     # NOP，1 字节
    opts += struct.pack("!BBB", 3, 3, 7)             # Window Scale = 7，3 字节
    opts += struct.pack("!BBII", 8, 10, 0x12345678, 0x00000000)  # 时间戳，10 字节
    while len(opts) % 4 != 0:
        opts += b"\x00"                              # 填充 EOL
    return opts


def main():
    print()
    print("TCP 首部构造与解析实验 · 模拟 PC1(192.0.2.10) → PC2(198.51.100.20) 的 SYN 段")
    print()

    src_ip, dst_ip = "192.0.2.10", "198.51.100.20"
    src_port, dst_port = 49152, 443
    seq, ack = 1000, 0
    window = 65535
    options = build_options()
    data_offset = (20 + len(options)) // 4          # 单位是 4 字节

    # 标志位字节：CWR ECE URG ACK PSH RST SYN FIN
    flags = dict(CWR=0, ECE=0, URG=0, ACK=0, PSH=0, RST=0, SYN=1, FIN=0)
    flag_byte = 0
    for i, name in enumerate(("CWR", "ECE", "URG", "ACK", "PSH", "RST", "SYN", "FIN")):
        flag_byte |= flags[name] << (7 - i)

    offset_reserved_ns = (data_offset << 4) | 0      # 高 4 位偏移，低 4 位保留+NS

    print("=" * 96)
    print("一、首部字段逐个拼装（不含校验和的占位）")
    print("-" * 96)
    print(pad("字段", 24) + pad("长度", 10) + pad("取值", 18) + "二进制 / 说明")
    print(pad("Source Port", 24) + pad("2 字节", 10) + pad(str(src_port), 18)
          + format(src_port, "016b"))
    print(pad("Destination Port", 24) + pad("2 字节", 10) + pad(str(dst_port), 18)
          + format(dst_port, "016b"))
    print(pad("Sequence Number", 24) + pad("4 字节", 10) + pad(str(seq), 18)
          + format(seq, "032b"))
    print(pad("Acknowledgment Number", 24) + pad("4 字节", 10) + pad(str(ack), 18)
          + format(ack, "032b") + "  （SYN 段不携带 ACK 时填 0）")
    print(pad("Data Offset", 24) + pad("4 bit", 10) + pad(str(data_offset), 18)
          + format(data_offset, "04b") + f"  → 首部长度 {data_offset * 4} 字节")
    print(pad("Reserved + NS", 24) + pad("4 bit", 10) + pad("0", 18)
          + "0000  保留位，必须置 0")
    print(pad("Flags", 24) + pad("8 bit", 10) + pad(f"0x{flag_byte:02X}", 18)
          + format(flag_byte, "08b") + "  （8 位顺序 CWR ECE URG ACK PSH RST SYN FIN）")
    print(pad("Window", 24) + pad("2 字节", 10) + pad(str(window), 18)
          + format(window, "016b") + f"  → 通告接收窗口 {window} 字节")
    print(pad("Checksum", 24) + pad("2 字节", 10) + "稍后计算")
    print(pad("Urgent Pointer", 24) + pad("2 字节", 10) + pad("0", 18)
          + "URG=0 时无意义")
    print(pad("Options", 24) + pad(f"{len(options)} 字节", 10) + "见下表")
    print("-" * 96)

    print("=" * 96)
    print("二、Options 区（本段共 %d 字节，补齐到 4 的倍数）" % len(options))
    print("-" * 96)
    print(pad("Kind", 8) + pad("名称", 22) + pad("长度", 8) + "值 / 含义")
    print(pad("1", 8) + pad("NOP", 22) + pad("1", 8) + "占位，用于选项对齐")
    print(pad("2", 8) + pad("MSS", 22) + pad("4", 8) + "1460 → 本机期望的对端最大段长")
    print(pad("3", 8) + pad("Window Scale", 22) + pad("3", 8)
          + "7 → 窗口扩大因子 2^7 = 128 倍")
    print(pad("4", 8) + pad("SACK Permitted", 22) + pad("2", 8) + "声明支持选择确认")
    print(pad("8", 8) + pad("Timestamps", 22) + pad("10", 8)
          + "TSval=0x12345678，TSecr=0（用于 RTT 测量与 PAWS 防回绕）")
    print(pad("0", 8) + pad("EOL / 填充", 22) + pad("可变", 8) + "补齐到 4 字节边界")
    print("-" * 96)
    print(f"选项原始字节：{hx(options)}")
    print()

    # 先拼首部（校验和置 0），再算校验和并回填
    def build(chk):
        return struct.pack("!HHIIBBHHH", src_port, dst_port, seq, ack,
                           offset_reserved_ns, flag_byte, window, chk, 0)

    header_no_cks = build(0) + options
    pseudo = ip_bytes(src_ip) + ip_bytes(dst_ip) + b"\x00\x06" + struct.pack(
        "!H", len(header_no_cks))
    full = pseudo + header_no_cks
    cks = checksum(full)
    header = build(cks) + options

    print("=" * 96)
    print("三、校验和计算（含伪首部）")
    print("-" * 96)
    print("伪首部构成（12 字节）：源 IP(4) + 目的 IP(4) + 全 0(1) + 协议号 6(1) + TCP 长度(2)")
    print(f"  源 IP        {src_ip}  → {hx(ip_bytes(src_ip))}")
    print(f"  目的 IP      {dst_ip}  → {hx(ip_bytes(dst_ip))}")
    print(f"  零 + 协议号  00 06")
    print(f"  TCP 长度     {len(header_no_cks)} 字节 → {hx(struct.pack('!H', len(header_no_cks)))}")
    print(f"伪首部原始字节：{hx(pseudo)}")
    print("-" * 96)
    print("步骤：")
    print("  1) 把伪首部 + TCP 首部（校验和字段先置 0）按 16 位分组相加。")
    print("  2) 每产生进位就回卷：把高 16 位加回低 16 位，直到高 16 位为 0。")
    print("  3) 对结果取反码，即得校验和。")
    total = ones_complement_sum(full)
    print(f"  分组求和（回卷后）= 0x{total:04X}")
    print(f"  取反              = 0x{checksum(full):04X}  ← 填入校验和字段")
    print()

    print("=" * 96)
    print("四、最终完整首部（十六进制）")
    print("-" * 96)
    print(f"  20 字节固定头：{hx(header[:20])}")
    print(f"  {len(options)} 字节选项：{hx(header[20:])}")
    print(f"  首部总长 {len(header)} 字节，Data Offset 字段 = {data_offset}"
          f"（{data_offset} × 4 = {len(header)}）")
    print()

    print("=" * 96)
    print("五、解析回来并验证")
    print("-" * 96)
    sp, dp, sq, ak, orn, fb, win, chk, urg = struct.unpack("!HHIIBBHHH", header[:20])
    print(pad("字段", 24) + pad("解析值", 20) + "校验")
    print(pad("Source Port", 24) + pad(str(sp), 20) + ("一致" if sp == src_port else "不一致"))
    print(pad("Destination Port", 24) + pad(str(dp), 20)
          + ("一致" if dp == dst_port else "不一致"))
    print(pad("Sequence Number", 24) + pad(str(sq), 20) + ("一致" if sq == seq else "不一致"))
    print(pad("Acknowledgment Number", 24) + pad(str(ak), 20)
          + ("一致" if ak == ack else "不一致"))
    doff = orn >> 4
    print(pad("Data Offset", 24) + pad(f"{doff} ({doff * 4} 字节)", 20)
          + ("一致" if doff == data_offset else "不一致"))
    print(pad("Flags", 24) + pad(f"0x{fb:02X} ({format(fb, '08b')})", 20)
          + ("一致" if fb == flag_byte else "不一致"))
    print(pad("Window", 24) + pad(str(win), 20) + ("一致" if win == window else "不一致"))
    print(pad("Checksum", 24) + pad(f"0x{chk:04X}", 20) + "见下方验算")
    print(pad("Urgent Pointer", 24) + pad(str(urg), 20) + "一致")
    print("-" * 96)
    print("验算规则：接收端把「伪首部 + 收到的 TCP 段（含校验和）」整体做反码求和，")
    verify = ones_complement_sum(pseudo + header)
    print(f"  整体反码求和 = 0x{verify:04X}"
          + ("  → 全 1，校验和正确" if verify == 0xFFFF else "  → 校验失败"))
    print()
    print(">>> 结论：TCP 校验和覆盖「伪首部 + 整个 TCP 段」，因此目的 IP 被篡改会导致校验失败；")
    print("    这也是 NAT 设备改地址后必须重算 TCP/UDP 校验和的原因。")
    print()
    print("小结：")
    print("1. TCP 固定首部 20 字节，Data Offset 以 4 字节为单位，所以首部必是 4 的倍数。")
    print("2. 8 个标志位按 CWR ECE URG ACK PSH RST SYN FIN 排列，SYN 与 FIN 各消耗 1 个序号。")
    print("3. 校验和含伪首部（源 IP + 目的 IP + 零 + 协议号 + TCP 长度），计算方法是 16 位反码求和后取反。")
    print()


if __name__ == "__main__":
    main()
