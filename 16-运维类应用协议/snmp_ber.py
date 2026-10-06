#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手工 BER/ASN.1 编码 SNMP GetRequest（SEQUENCE/INTEGER/STRING/OID 的 TLV），逐字节打印。

运行: python3 snmp_ber.py
"""
import sys

sys.dont_write_bytecode = True

TAG_INTEGER = 0x02
TAG_OCTET_STRING = 0x04
TAG_NULL = 0x05
TAG_OID = 0x06
TAG_SEQUENCE = 0x30
TAG_GETREQUEST = 0xA0          # 上下文相关 + 构造类型 + PDU 类型 0


def encode_length(n: int) -> bytes:
    """BER 长度编码：短形式（<128）单字节；长形式首字节高位为 1，后跟长度字节数。"""
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + encode_length(len(value)) + value


def encode_integer(n: int) -> bytes:
    """有符号整数的最小长度二进制补码编码。"""
    if n == 0:
        return tlv(TAG_INTEGER, b"\x00")
    length = (n.bit_length() + 8) // 8          # 留一位符号位
    body = n.to_bytes(length, "big", signed=True)
    return tlv(TAG_INTEGER, body)


def encode_octet_string(s: bytes) -> bytes:
    return tlv(TAG_OCTET_STRING, s)


def encode_null() -> bytes:
    return tlv(TAG_NULL, b"")


def encode_oid(arcs: list[int]) -> bytes:
    """OID 编码：前两段合并为 40*x+y，其余每段用 base-128 变长（高位置 1 续段）。"""
    if len(arcs) < 2:
        raise ValueError("OID 至少两段")
    body = bytearray()
    body.append(40 * arcs[0] + arcs[1])
    for arc in arcs[2:]:
        if arc < 0:
            raise ValueError("OID 段不能为负")
        stack = [arc & 0x7F]
        arc >>= 7
        while arc:
            stack.append((arc & 0x7F) | 0x80)
            arc >>= 7
        body.extend(reversed(stack))
    return tlv(TAG_OID, bytes(body))


def encode_sequence(parts: list[bytes]) -> bytes:
    return tlv(TAG_SEQUENCE, b"".join(parts))


def encode_pdu(parts: list[bytes]) -> bytes:
    return tlv(TAG_GETREQUEST, b"".join(parts))


def dump(label: str, data: bytes) -> None:
    print("    %-28s (%2d 字节) %s" % (label, len(data), data.hex(" ").upper()))


def main() -> None:
    print("=" * 74)
    print("SNMP GetRequest 的 BER/ASN.1 手工编码（SNMPv2c, community=public）")
    print("=" * 74)

    oid = [1, 3, 6, 1, 2, 1, 1, 5, 0]        # sysName.0
    print("\n[1] 目标 OID = %s（sysName.0）" % ".".join(map(str, oid)))
    encoded_oid = encode_oid(oid)
    dump("OID TLV", encoded_oid)
    print("    编码规则：前两段 1.3 合并为 40×1 + 3 = %d = 0x%02X" % (40 * 1 + 3, 40 * 1 + 3))
    print("    后续每段 <128 直接用一字节：6=06 1=01 2=02 1=01 1=01 5=05 0=00")
    print("    值部分 = %s（8 字节）" % encoded_oid[2:].hex(" ").upper())
    print("    整个 TLV = 06 08 <8 字节值>，因为值长 8 < 128 用短长度形式")

    print("\n[2] 演示大段号 base-128 变长编码")
    big_oid = [1, 3, 6, 1, 4, 1, 311]        # 微软企业号 311
    enc_big = encode_oid(big_oid)
    dump("OID TLV (1.3.6.1.4.1.311)", enc_big)
    print("    311 = 0x137 = 2×128 + 55 -> 先 0x82（0x80|2）再 0x37")
    print("    即 311 编码为 82 37，高位置 1 表示「还有后续字节」")

    print("\n[3] 各基本类型的 TLV")
    dump("INTEGER version=1", encode_integer(1))
    dump("INTEGER request-id=12345", encode_integer(12345))
    dump("OCTET STRING community", encode_octet_string(b"public"))
    dump("NULL", encode_null())

    print("\n[4] 组装 VarBind 与 PDU")
    varbind = encode_sequence([encoded_oid, encode_null()])
    dump("VarBind SEQUENCE{OID,NULL}", varbind)
    varbind_list = encode_sequence([varbind])
    dump("VarBindList SEQUENCE", varbind_list)

    pdu_body = (encode_integer(12345)      # request-id
                + encode_integer(0)        # error-status = noError
                + encode_integer(0)        # error-index = 0
                + varbind_list)
    pdu = encode_pdu([pdu_body])
    dump("GetRequest PDU (0xA0)", pdu[:16])
    print("    （PDU 共 %d 字节，此处仅显示前 16 字节）" % len(pdu))

    print("\n[5] 组装完整 SNMP 报文")
    version = encode_integer(1)            # v2c = 1
    community = encode_octet_string(b"public")
    message = encode_sequence([version, community, pdu])
    print("    结构：SEQUENCE { INTEGER version, OCTET STRING community, GetRequest PDU }")
    dump("完整报文", message)

    print("\n[6] 逐字节解剖（前 24 字节）")
    print("    %-6s %-6s %-10s %s" % ("偏移", "字节", "字段", "说明"))
    print("    " + "-" * 60)
    fields = [
        (0, message[0], "SEQUENCE", "0x30 = 通用 + 构造类型"),
        (1, message[1], "长度", "整个报文的长度"),
        (2, message[2], "INTEGER", "0x02 = 版本字段"),
        (4, None, "版本值", "1 = SNMPv2c"),
    ]
    for off, b, name, note in fields:
        if b is None:
            continue
        print("    %-6d 0x%02X   %-10s %s" % (off, b, name, note))
    print("    >>> BER 是「TLV」自描述格式：每个字段先说类型(Tag)、再说长度(Length)、最后给值(Value)")

    print("\n[7] SNMP 版本安全演进")
    print("    %-8s %-16s %-24s %s" % ("版本", "认证", "加密", "说明"))
    print("    " + "-" * 70)
    ver = [
        ("v1", "community 明文", "无", "最简单，community 就是密码"),
        ("v2c", "community 明文", "无", "加了 GetBulk 与 64 位计数器"),
        ("v3", "USM 用户+MD5/SHA", "可选 DES/AES", "支持认证与加密，生产推荐"),
    ]
    for a, b, c, d in ver:
        print("    %-8s %-16s %-24s %s" % (a, b, c, d))
    print("    >>> v1/v2c 的 community（如 public）在网络上明文传输，抓包即可见，务必只在受控网段使用")

    print("\n" + "=" * 74)
    print("小结")
    print("-" * 74)
    print("1. BER 是 TLV 自描述编码：Tag 标类型、Length 标长度、Value 是内容。")
    print("2. OID 前两段合并为 40×X+Y，后续段用 base-128 变长（高位置 1 表示续段）。")
    print("3. 1.3.6.1.2.1.1.5.0 编码值 = 2B 06 01 02 01 01 05 00；311 编码为 82 37。")
    print("4. SNMPv3 用 USM 提供认证与加密，v1/v2c 的 community 是明文，抓包即泄漏。")


if __name__ == "__main__":
    main()
