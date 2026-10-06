#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手工构造与解析 DNS 报文：QNAME 长度前缀编码、Header 标志位、压缩指针 0xC0。

运行: python3 dns_wire_format.py
（本脚本只在内存中编解码，不发起任何真实 DNS 查询）
"""
import struct
import sys

sys.dont_write_bytecode = True

QTYPE = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR", 15: "MX",
         16: "TXT", 28: "AAAA", 33: "SRV", 257: "CAA"}
QCLASS = {1: "IN", 3: "CH", 4: "HS", 255: "ANY"}


def encode_name(name: str) -> bytes:
    """把域名编码成 QNAME：每个标签用 1 字节长度前缀，末尾 1 个 0x00。"""
    stripped = name.rstrip(".")
    if stripped == "":
        return b"\x00"                       # 根域：单个 0 字节
    out = b""
    for label in stripped.split("."):
        raw = label.encode("ascii")
        if not 1 <= len(raw) <= 63:
            raise ValueError("标签长度必须在 1~63 之间: %r" % label)
        out += bytes([len(raw)]) + raw
    out += b"\x00"
    return out


def decode_name(data: bytes, offset: int) -> tuple[str, int]:
    """解析域名，支持压缩指针 0xC0。返回（域名, 指针字段之后的下一个偏移）。"""
    labels: list[str] = []
    next_offset = -1
    pos = offset
    jumps = 0
    while True:
        if pos >= len(data):
            raise ValueError("域名解析越界")
        length = data[pos]
        if length == 0:
            pos += 1
            if next_offset < 0:
                next_offset = pos
            break
        if (length & 0xC0) == 0xC0:          # 压缩指针
            ptr = ((length & 0x3F) << 8) | data[pos + 1]
            if next_offset < 0:
                next_offset = pos + 2
            jumps += 1
            if jumps > 20:
                raise ValueError("压缩指针成环")
            pos = ptr
            continue
        if (length & 0xC0) != 0:
            raise ValueError("非法的标签长度类型 0x%02X" % length)
        pos += 1
        label = data[pos:pos + length]
        if len(label) != length:
            raise ValueError("标签越界")
        labels.append(label.decode("ascii"))
        pos += length
    return (".".join(labels) if labels else "<root>"), next_offset


def build_query(qid: int, name: str, qtype: int = 1, rd: bool = True) -> bytes:
    """构造 DNS 查询报文：Header(12) + Question。"""
    flags = 0x0100 if rd else 0x0000       # QR=0 Opcode=0 AA=0 TC=0 RD=? RA=0 Z=0 RCODE=0
    header = struct.pack(">HHHHHH", qid, flags, 1, 0, 0, 0)
    question = encode_name(name) + struct.pack(">HH", qtype, 1)
    return header + question


def parse_header(data: bytes) -> dict:
    qid, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    return {
        "ID": qid,
        "QR": (flags >> 15) & 1,
        "Opcode": (flags >> 11) & 0xF,
        "AA": (flags >> 10) & 1,
        "TC": (flags >> 9) & 1,
        "RD": (flags >> 8) & 1,
        "RA": (flags >> 7) & 1,
        "Z": (flags >> 4) & 0x7,
        "RCODE": flags & 0xF,
        "QDCOUNT": qd, "ANCOUNT": an, "NSCOUNT": ns, "ARCOUNT": ar,
        "flags_raw": flags,
    }


def parse_message(data: bytes) -> dict:
    h = parse_header(data)
    pos = 12
    sections = {"question": [], "answer": [], "authority": [], "additional": []}
    names = {"question": h["QDCOUNT"], "answer": h["ANCOUNT"],
             "authority": h["NSCOUNT"], "additional": h["ARCOUNT"]}
    for sec in ("question", "answer", "authority", "additional"):
        for _ in range(names[sec]):
            name, pos = decode_name(data, pos)
            rtype, rclass = struct.unpack(">HH", data[pos:pos + 4])
            pos += 4
            entry = {"name": name, "type": rtype, "class": rclass}
            if sec != "question":
                ttl, rdlen = struct.unpack(">IH", data[pos:pos + 6])
                pos += 6
                rdata = data[pos:pos + rdlen]
                pos += rdlen
                entry.update(ttl=ttl, rdlen=rdlen, rdata=rdata)
            sections[sec].append(entry)
    return {"header": h, "sections": sections}


def fmt_flags(h: dict) -> str:
    parts = []
    if h["QR"]:
        parts.append("QR")
    if h["AA"]:
        parts.append("AA")
    if h["TC"]:
        parts.append("TC")
    if h["RD"]:
        parts.append("RD")
    if h["RA"]:
        parts.append("RA")
    return "|".join(parts) if parts else "（全 0）"


def main() -> None:
    print("=" * 72)
    print("DNS 报文线格式编解码（纯内存自校验，不联网）")
    print("=" * 72)

    name = "www.example.com"
    qid = 0x1A2B
    print("\n[1] QNAME 长度前缀编码：%s" % name)
    qname = encode_name(name)
    print("    %-8s 编码为：%s" % ("标签", "长度字节 + ASCII"))
    for label in name.split("."):
        print("    %-8s -> %02X + %s" % (label, len(label), label.encode().hex(" ")))
    print("    结束标志 -> 00")
    print("    完整 QNAME = " + qname.hex(" "))
    n_labels = len(name.split("."))
    print("    总长 %d 字节（%d 个长度字节 + %d 个字符 + 1 个结束 0）"
          % (len(qname), n_labels, len(name) - (n_labels - 1)))

    query = build_query(qid, name, qtype=1, rd=True)
    print("\n[2] 完整查询报文（Header 12 字节 + Question）")
    print("    " + query.hex(" ").upper())
    print("\n    Header 逐字段：")
    hdr = struct.unpack(">HHHHHH", query[:12])
    print("    ID = 0x%04X（客户端随机生成，用于匹配响应）" % hdr[0])
    print("    标志位 = 0x%04X -> QR=0(查询) Opcode=0(标准查询) RD=1(期望递归)" % hdr[1])
    print("    QDCOUNT=%d ANCOUNT=%d NSCOUNT=%d ARCOUNT=%d" % hdr[2:6])

    print("\n[3] 解析自己构造的查询报文，验证编解码一致")
    parsed = parse_message(query)
    q0 = parsed["sections"]["question"][0]
    print("    解析出的 QNAME = %s" % q0["name"])
    print("    QTYPE=%d(%s)  QCLASS=%d(%s)"
          % (q0["type"], QTYPE.get(q0["type"]), q0["class"], QCLASS.get(q0["class"])))
    print("    >>> 往返一致：%s" % (q0["name"] == name))

    print("\n[4] 构造含压缩指针 0xC0 的响应报文")
    # 响应：QR=1 AA=1 RD=1 RA=1 RCODE=0 -> 0x8580
    resp_flags = 0x8580
    resp_header = struct.pack(">HHHHHH", qid, resp_flags, 1, 1, 0, 0)
    resp_q = encode_name(name) + struct.pack(">HH", 1, 1)
    # Answer 的 NAME 用压缩指针指向偏移 12（即 Question 的 QNAME 起点）
    answer = b"\xC0\x0C"                      # 0xC0 | 高 6 位偏移，后跟低 8 位偏移 = 0x0C
    answer += struct.pack(">HHIH", 1, 1, 300, 4)   # TYPE=A CLASS=IN TTL=300 RDLENGTH=4
    answer += bytes([198, 51, 100, 10])            # RDATA = 198.51.100.10
    response = resp_header + resp_q + answer

    print("    压缩指针字节 = C0 0C  ->  指向偏移 12（Question 的 QNAME 起点）")
    print("    指针编码规则：高 2 位固定 11，剩下 14 位放偏移量")
    print("    偏移 12 的编码 = 0xC000 | 12 = 0x%04X -> 大端两字节 %s"
          % (0xC000 | 12, b"\xC0\x0C".hex(" ").upper()))
    print("    完整响应 = " + response.hex(" ").upper())

    print("\n[5] 解析响应，验证压缩指针还原正确")
    pr = parse_message(response)
    rh = pr["header"]
    print("    ID=0x%04X  标志=0x%04X(%s)  RCODE=%d(0=无错误)"
          % (rh["ID"], rh["flags_raw"], fmt_flags(rh), rh["RCODE"]))
    a0 = pr["sections"]["answer"][0]
    ip = ".".join(str(b) for b in a0["rdata"])
    print("    Answer: NAME=%s TYPE=%s TTL=%d  RDATA=%s"
          % (a0["name"], QTYPE.get(a0["type"]), a0["ttl"], ip))
    print("    >>> 压缩指针把 NAME 从 %d 字节压到 2 字节，节省 %d 字节"
          % (len(qname), len(qname) - 2))

    print("\n[6] 边界：域名各标签长度上限与根域")
    print("    单个标签最长 63 字节（长度字节低 6 位最多 0x3F=63）")
    print("    整个域名（编码后）最长 255 字节")
    print("    根域编码 = 单个 0x00 字节（长度为 0，代表域名结束即根）")
    print("    根域编码十六进制 = " + encode_name("").hex(" "))

    print("\n" + "=" * 72)
    print("小结")
    print("-" * 72)
    print("1. DNS 域名的线格式是「长度前缀 + 内容」，末尾 0x00 结束；单标签 ≤63、整名 ≤255 字节。")
    print("2. Header 12 字节含 ID 与 16 位标志；QR 区分查询/响应，RD 请求递归、RA 表示可递归。")
    print("3. 压缩指针 0xC0 把 14 位偏移塞进两字节，指向报文中已出现的域名，显著压缩体积。")
    print("4. 解析压缩指针必须防成环，且「下一个偏移」要取指针字段之后而非被指向处。")


if __name__ == "__main__":
    main()
