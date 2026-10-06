#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯标准库解析 pcap：自造 pcap 字节流（全局头 + 包记录）再逐层解析。

运行: python3 pcap_parse.py
"""
import ipaddress
import struct
import sys
import tempfile

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

MAGIC_US = 0xA1B2C3D4          # 微秒精度 pcap
MAGIC_NS = 0xA1B23C4D          # 纳秒精度 pcap
LINKTYPE_ETHERNET = 1
SNAP_LENGTH = 65535

ETH_HDR = 14                   # 目的 MAC(6) + 源 MAC(6) + 类型(2)
IPV4_FIXED = 20                # 无选项的 IPv4 固定头
IPV6_FIXED = 40
TCP_FIXED = 20
UDP_FIXED = 8

PROTO_NAME = {1: "ICMP", 6: "TCP", 17: "UDP", 58: "ICMPv6"}
ETHERTYPE_NAME = {0x0800: "IPv4", 0x0806: "ARP", 0x86DD: "IPv6", 0x8100: "802.1Q"}


def mac_to_bytes(text: str) -> bytes:
    return bytes(int(part, 16) for part in text.split(":"))


def ipv4_to_bytes(text: str) -> bytes:
    return int(ipaddress.IPv4Address(text)).to_bytes(4, "big")


def checksum16(data: bytes) -> int:
    """Internet 校验和：16 位分组求和 + 进位回卷 + 取反。"""
    if len(data) % 2:
        data += b"\x00"
    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) | data[i + 1]
    while total > 0xFFFF:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def build_eth(dst: str, src: str, ethertype: int) -> bytes:
    return mac_to_bytes(dst) + mac_to_bytes(src) + struct.pack("!H", ethertype)


def build_ipv4(src: str, dst: str, proto: int, ttl: int, payload: bytes,
               ident: int = 1, df: bool = True) -> bytes:
    total_len = IPV4_FIXED + len(payload)
    flags_frag = 0x4000 if df else 0x0000
    hdr = struct.pack("!BBHHHBBH4s4s",
                      0x45,               # 版本 4 + 首部长度 5（5×4=20 字节）
                      0,                  # DSCP/ECN
                      total_len,
                      ident,
                      flags_frag,
                      ttl,
                      proto,
                      0,                  # 校验和先置 0
                      ipv4_to_bytes(src),
                      ipv4_to_bytes(dst))
    ck = checksum16(hdr)
    hdr = hdr[:10] + struct.pack("!H", ck) + hdr[12:]
    return hdr + payload


def build_ipv6(src: str, dst: str, next_header: int, hop_limit: int,
               payload: bytes) -> bytes:
    hdr = struct.pack("!IHBB16s16s",
                      0x60000000,          # 版本 6 + 流量类别 + 流标签
                      len(payload),
                      next_header,
                      hop_limit,
                      ipaddress.IPv6Address(src).packed,
                      ipaddress.IPv6Address(dst).packed)
    return hdr + payload


def build_tcp(sport: int, dport: int, seq: int, ack: int, flags: int,
              payload: bytes = b"", window: int = 65535) -> bytes:
    data_offset = 5 << 4                  # 5×4=20 字节首部长度
    hdr = struct.pack("!HHIIBBHHH", sport, dport, seq, ack,
                      data_offset, flags, window, 0, 0)
    return hdr + payload


def build_udp(sport: int, dport: int, payload: bytes) -> bytes:
    return struct.pack("!HHHH", sport, dport, UDP_FIXED + len(payload), 0) + payload


def build_icmp(itype: int, code: int, ident: int, seq: int, payload: bytes) -> bytes:
    body = struct.pack("!HH", ident, seq) + payload
    ck = checksum16(struct.pack("!BBH", itype, code, 0) + body)
    return struct.pack("!BBH", itype, code, ck) + body


def build_arp(oper: int, sha: str, spa: str, tha: str, tpa: str) -> bytes:
    return struct.pack("!HHBBH", 1, 0x0800, 6, 4, oper) + \
        mac_to_bytes(sha) + ipv4_to_bytes(spa) + \
        mac_to_bytes(tha) + ipv4_to_bytes(tpa)


def build_pcap(records: list) -> bytes:
    """records = [(ts_sec, ts_usec, frame_bytes), ...]，返回完整 pcap 字节流。"""
    out = struct.pack("<IHHiIII", MAGIC_US, 2, 4, 0, 0, SNAP_LENGTH,
                      LINKTYPE_ETHERNET)
    for ts_sec, ts_usec, frame in records:
        out += struct.pack("<IIII", ts_sec, ts_usec, len(frame), len(frame))
        out += frame
    return out


def read_pcap_header(blob: bytes) -> dict:
    magic_le = struct.unpack("<I", blob[:4])[0]
    if magic_le in (MAGIC_US, MAGIC_NS):
        endian = "<"
        magic = magic_le
    else:
        endian = ">"
        magic = struct.unpack(">I", blob[:4])[0]
    ver_major, ver_minor, thiszone, sigfigs, snaplen, network = \
        struct.unpack(endian + "HHiIII", blob[4:24])
    return {
        "magic": magic,
        "endian": endian,
        "magic_name": "纳秒精度" if magic == MAGIC_NS else "微秒精度",
        "version": f"{ver_major}.{ver_minor}",
        "thiszone": thiszone,
        "snaplen": snaplen,
        "network": network,
        "network_name": "Ethernet" if network == LINKTYPE_ETHERNET else "其它",
    }


def parse_flags(flags: int) -> str:
    names = []
    if flags & 0x01:
        names.append("FIN")
    if flags & 0x02:
        names.append("SYN")
    if flags & 0x04:
        names.append("RST")
    if flags & 0x08:
        names.append("PSH")
    if flags & 0x10:
        names.append("ACK")
    if flags & 0x20:
        names.append("URG")
    return "|".join(names) if names else "NONE"


def parse_packet(frame: bytes, idx: int) -> None:
    print(SUB)
    print(f"包 #{idx}  帧总长 = {len(frame)} 字节")
    print(SUB)
    dst_mac = ":".join("%02X" % b for b in frame[0:6])
    src_mac = ":".join("%02X" % b for b in frame[6:12])
    ethertype = struct.unpack("!H", frame[12:14])[0]
    print(f"  [以太网] 目的MAC={dst_mac} 源MAC={src_mac} "
          f"类型=0x{ethertype:04X}({ETHERTYPE_NAME.get(ethertype, '未知')})")

    body = frame[ETH_HDR:]
    if ethertype == 0x0806:
        parse_arp(body)
    elif ethertype == 0x0800:
        parse_ipv4(body)
    elif ethertype == 0x86DD:
        parse_ipv6(body)
    else:
        print(f"  [上层] 未解析的类型，载荷前 16 字节: {body[:16].hex(' ')}")


def parse_arp(body: bytes) -> None:
    htype, ptype, hlen, plen, oper = struct.unpack("!HHBBH", body[:8])
    sha = ":".join("%02X" % b for b in body[8:14])
    spa = str(ipaddress.IPv4Address(body[14:18]))
    tha = ":".join("%02X" % b for b in body[18:24])
    tpa = str(ipaddress.IPv4Address(body[24:28]))
    opname = {1: "request", 2: "reply"}.get(oper, str(oper))
    print(f"  [ARP] 操作={opname}({oper}) 发送者MAC={sha} 发送者IP={spa} "
          f"目标MAC={tha} 目标IP={tpa}")
    print(f"  >>> 作业：ARP 无认证，收到 reply 即更新缓存——这就是 ARP 欺骗的入口")


def parse_ipv4(body: bytes) -> None:
    ver_ihl, tos, total_len, ident, flags_frag, ttl, proto, ck, src, dst = \
        struct.unpack("!BBHHHBBH4s4s", body[:20])
    ihl = (ver_ihl & 0x0F) * 4
    version = ver_ihl >> 4
    df = bool(flags_frag & 0x4000)
    mf = bool(flags_frag & 0x2000)
    frag_off = (flags_frag & 0x1FFF) * 8
    print(f"  [IPv4] 版本={version} 首部长度={ihl}B 总长={total_len} ID=0x{ident:04X}")
    print(f"         标志 DF={int(df)} MF={int(mf)} 片偏移={frag_off}B "
          f"TTL={ttl} 协议={proto}({PROTO_NAME.get(proto, '?')}) 校验和=0x{ck:04X}")
    print(f"         源={ipaddress.IPv4Address(src)} 目的={ipaddress.IPv4Address(dst)}")
    payload = body[ihl:total_len]
    if proto == 6:
        parse_tcp(payload)
    elif proto == 17:
        parse_udp(payload)
    elif proto == 1:
        parse_icmp(payload)


def parse_ipv6(body: bytes) -> None:
    word0, plen, next_header, hop_limit, src, dst = struct.unpack("!IHBB16s16s",
                                                                  body[:40])
    version = word0 >> 28
    print(f"  [IPv6] 版本={version} 载荷长度={plen} 下一头部={next_header}"
          f"({PROTO_NAME.get(next_header, '?')}) 跳数限制={hop_limit}")
    print(f"         源={ipaddress.IPv6Address(src)} 目的={ipaddress.IPv6Address(dst)}")
    payload = body[IPV6_FIXED:IPV6_FIXED + plen]
    if next_header == 58:
        icmp_type = payload[0]
        code = payload[1]
        tname = {135: "邻居请求 NS", 136: "邻居通告 NA", 128: "回显请求",
                 129: "回显应答"}.get(icmp_type, str(icmp_type))
        print(f"  [ICMPv6] 类型={icmp_type}({tname}) code={code}")


def parse_tcp(payload: bytes) -> None:
    sport, dport, seq, ack, off_byte, flags, window, ck, urg = \
        struct.unpack("!HHIIBBHHH", payload[:20])
    offset = (off_byte >> 4) * 4
    data = payload[offset:]
    print(f"  [TCP] 源端口={sport} 目的端口={dport} 序列号={seq} 确认号={ack}")
    print(f"        标志={parse_flags(flags)}(0x{flags:02X}) 窗口={window} "
          f"首部长度={offset}B 校验和=0x{ck:04X}")
    show_payload(data)


def parse_udp(payload: bytes) -> None:
    sport, dport, length, ck = struct.unpack("!HHHH", payload[:8])
    print(f"  [UDP] 源端口={sport} 目的端口={dport} 长度={length} 校验和=0x{ck:04X}")
    show_payload(payload[8:length])


def parse_icmp(payload: bytes) -> None:
    itype, code, ck = struct.unpack("!BBH", payload[:4])
    tname = {0: "回显应答", 3: "目的不可达", 8: "回显请求",
             11: "超时"}.get(itype, str(itype))
    print(f"  [ICMP] 类型={itype}({tname}) code={code} 校验和=0x{ck:04X}")


def show_payload(data: bytes) -> None:
    if not data:
        print("  [载荷] （无）")
        return
    preview = data[:48]
    text = "".join(chr(b) if 32 <= b < 127 else "." for b in preview)
    print(f"  [载荷] {len(data)} 字节，前 {len(preview)} 字节: {preview.hex(' ')}")
    print(f"         可打印预览: {text}")


def build_all_frames() -> list:
    """构造 6 个典型帧，覆盖 ARP / IPv4(ICMP,TCP,UDP) / IPv6(ICMPv6)。"""
    frames = []

    # 1. ARP 请求（广播）
    arp = build_arp(1, "02:00:00:00:00:0A", "192.0.2.10",
                    "00:00:00:00:00:00", "192.0.2.1")
    frames.append((1735689600, 1000,
                   build_eth("ff:ff:ff:ff:ff:ff", "02:00:00:00:00:0A", 0x0806) + arp))

    # 2. IPv4 ICMP 回显请求
    icmp = build_icmp(8, 0, 0x1234, 1, b"ABCDEFGHIJKLMNOPQRSTUVWXYZ012345")
    frames.append((1735689600, 2000,
                   build_eth("02:00:00:00:00:0B", "02:00:00:00:00:0A", 0x0800) +
                   build_ipv4("192.0.2.10", "198.51.100.10", 1, 64, icmp, ident=0x1A2B)))

    # 3. IPv4 TCP SYN
    tcp_syn = build_tcp(51000, 443, 0x0A0B0C0D, 0, 0x02)
    frames.append((1735689600, 3000,
                   build_eth("02:00:00:00:00:0B", "02:00:00:00:00:0A", 0x0800) +
                   build_ipv4("192.0.2.10", "198.51.100.10", 6, 64, tcp_syn, ident=0x1A2C)))

    # 4. IPv4 TCP PSH+ACK 携带 HTTP 请求
    http = b"GET / HTTP/1.1\r\nHost: 198.51.100.10\r\nConnection: keep-alive\r\n\r\n"
    tcp_data = build_tcp(51000, 443, 0x0A0B0C0E, 0x11223344, 0x18, http)
    frames.append((1735689600, 4000,
                   build_eth("02:00:00:00:00:0B", "02:00:00:00:00:0A", 0x0800) +
                   build_ipv4("192.0.2.10", "198.51.100.10", 6, 63, tcp_data, ident=0x1A2D)))

    # 5. IPv4 UDP（DNS 查询样式）
    dns = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    udp = build_udp(33000, 53, dns + b"\x03www\x07example\x03com\x00\x00\x01\x00\x01")
    frames.append((1735689600, 5000,
                   build_eth("02:00:00:00:00:0B", "02:00:00:00:00:0A", 0x0800) +
                   build_ipv4("192.0.2.10", "198.51.100.53", 17, 64, udp, ident=0x1A2E)))

    # 6. IPv6 ICMPv6 邻居请求
    ns = struct.pack("!BBH", 135, 0, 0) + b"\x00" * 4 + \
        ipaddress.IPv6Address("2001:db8::b").packed
    frames.append((1735689600, 6000,
                   build_eth("33:33:ff:00:00:0b", "02:00:00:00:00:0A", 0x86DD) +
                   build_ipv6("2001:db8::a", "ff02::1:ff00:b", 58, 255, ns)))

    return frames


def main() -> None:
    print(SEP)
    print("pcap 文件格式解析演示 · 自造字节流（不依赖任何外部抓包文件）")
    print(SEP)

    frames = build_all_frames()
    blob = build_pcap(frames)

    print(SUB)
    print("【一】pcap 全局头（前 24 字节，逐字段解析）")
    print(SUB)
    gh = read_pcap_header(blob)
    print(f"  magic_number = 0x{gh['magic']:08X}（{gh['magic_name']}，字节序 {gh['endian']}）")
    print(f"  version      = {gh['version']}")
    print(f"  thiszone     = {gh['thiszone']}（GMT 偏移秒数，实际抓包恒为 0）")
    print(f"  snaplen      = {gh['snaplen']}（每包最多截取字节数）")
    print(f"  network      = {gh['network']}（{gh['network_name']}）")
    print(f"  原始字节: {blob[:24].hex(' ')}")
    print(">>> 结论：全局头固定 24 字节；magic 0xA1B2C3D4 表示微秒精度，"
          "0xA1B23C4D 表示纳秒精度")

    print()
    print(SUB)
    print("【二】包记录头（每条 16 字节）")
    print(SUB)
    print(f"{'#':<4}{'ts_sec':<12}{'ts_usec':<10}{'incl_len':<10}{'orig_len':<10}")
    print(SUB)
    offset = 24
    metas = []
    for i, (_s, _u, frame) in enumerate(frames, 1):
        ts_sec, ts_usec, incl, orig = struct.unpack("<IIII", blob[offset:offset + 16])
        metas.append((ts_sec, ts_usec, incl, orig))
        print(f"{i:<4}{ts_sec:<12}{ts_usec:<10}{incl:<10}{orig:<10}")
        offset += 16 + incl
    print(">>> 结论：每条包记录头 16 字节 = 时间戳(8B) + 抓取长度(4B) + 原始长度(4B)；"
          "抓取长度 < 原始长度说明被 snaplen 截断")

    print()
    print(SUB)
    print("【三】逐包解析各层头部")
    print(SUB)
    offset = 24
    for i in range(len(frames)):
        incl = metas[i][2]
        frame = blob[offset + 16: offset + 16 + incl]
        parse_packet(frame, i + 1)
        offset += 16 + incl

    print()
    print(SUB)
    print("【四】临时文件往返：写入磁盘再读回，验证字节流一致")
    print(SUB)
    with tempfile.TemporaryDirectory() as tmp:
        path = tmp + "/demo.pcap"
        with open(path, "wb") as fh:
            fh.write(blob)
        with open(path, "rb") as fh:
            back = fh.read()
        print(f"  文件大小 = {len(back)} 字节，与内存字节流一致 = {back == blob}")
        print(f"  'file' 命令通常识别为: pcap capture file, microsecond ts"
              f" - {len(frames)} packets")
    print(">>> 结论：pcap 是极简格式，24B 全局头 + N×(16B 记录头 + 帧)，"
          "完全可以用 struct 手工读写")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. pcap 全局头 24 字节，magic 决定字节序与时间戳精度（微秒/纳秒两种）。")
    print("2. 每条包记录头 16 字节：ts_sec(4) + ts_usec(4) + incl_len(4) + orig_len(4)。")
    print("3. 帧数据以以太网头开始（linktype=1），逐层解封装只需按固定长度切片。")
    print("4. 本次 6 个包覆盖 ARP / IPv4(ICMP,TCP,UDP) / IPv6(ICMPv6)，全部由脚本自造。")
    print()


if __name__ == "__main__":
    main()
