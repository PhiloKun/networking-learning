#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IS-IS 报文 TLV 编码与解析演示（Hello / LSP 关键 TLV，含 NET 地址）。

运行: python3 isis_tlv.py
"""
import sys
import binascii
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


def hexs(b):
    return binascii.hexlify(b).decode("ascii")


def hx(b):
    """带空格分组的十六进制，便于阅读。"""
    return " ".join(f"{x:02X}" for x in b)


def tlv(t, value):
    """IS-IS 短 TLV：类型 1 字节 + 长度 1 字节 + 值。长度上限 255。"""
    if len(value) > 255:
        raise ValueError("本演示只处理 <=255 字节的短 TLV")
    return bytes([t, len(value)]) + value


# ---------------- 值构造器 ----------------
def v_area_addr(area_hex):
    """Area Addresses TLV(1)：地址个数 + 每个地址长度 + 地址。"""
    area = binascii.unhexlify(area_hex.replace(".", ""))
    return bytes([1, len(area)]) + area


def v_is_neighbors(items):
    """IS Neighbors TLV(6)：每个邻居 6 字节 System ID + 1 字节伪节点号。"""
    out = b""
    for sysid, pseudo in items:
        out += binascii.unhexlify(sysid.replace(".", "")) + bytes([pseudo])
    return out


def v_ext_is_reach(items):
    """Extended IS Reachability TLV(22)：7 字节邻居 ID + 3 字节度量 + 子 TLV。"""
    out = b""
    for sysid, pseudo, metric, sub in items:
        out += binascii.unhexlify(sysid.replace(".", "")) + bytes([pseudo])
        out += metric.to_bytes(3, "big")
        out += sub
    return out


def v_protocols(nlpids):
    return bytes(nlpids)


def v_ip_ifaddr(ips):
    out = b""
    for ip in ips:
        out += bytes(int(x) for x in ip.split("."))
    return out


def v_hostname(name):
    return name.encode("ascii")


def v_auth(scheme, data):
    return bytes([scheme]) + data


# ---------------- 值解析器 ----------------
def d_area_addr(v):
    n, ln = v[0], v[1]
    addrs = []
    p = 2
    for _ in range(n):
        seg = v[p:p + ln]
        p += ln
        # 区域地址按 NET 习惯写成 AFI.其余（如 49.0001）
        h = hexs(seg).upper()
        addrs.append(h[0:2] + "." + h[2:])
    return f"区域地址个数={n}，地址={','.join(addrs)}"


def d_is_neighbors(v):
    out = []
    for i in range(0, len(v) - 6, 7):
        seg = v[i:i + 6]
        pseudo = v[i + 6]
        h = hexs(seg).upper()
        out.append(".".join([h[j:j + 4] for j in range(0, 12, 4)]) + f" 伪节点={pseudo}")
    return "；".join(out)


def d_ext_is_reach(v):
    out = []
    i = 0
    while i + 10 <= len(v):
        seg = v[i:i + 7]
        metric = int.from_bytes(v[i + 7:i + 10], "big")
        h = hexs(seg[:6]).upper()
        sid = ".".join([h[j:j + 4] for j in range(0, 12, 4)]) + f".{seg[6]:02X}"
        # 子 TLV：类型 1 字节 + 长度 1 字节
        sub_type, sub_len = v[i + 10], v[i + 11]
        sub_val = v[i + 12:i + 12 + sub_len]
        desc = ""
        if sub_type == 6 and sub_len == 4:
            desc = "，子TLV6(接口地址)=" + ".".join(str(x) for x in sub_val)
        out.append(f"{sid} 度量={metric}{desc}")
        i += 12 + sub_len
    return "；".join(out)


def d_protocols(v):
    names = {0xCC: "IPv4", 0x8E: "IPv6", 0x81: "IS-IS"}
    return "NLPID=" + ",".join(f"0x{x:02X}({names.get(x, '未知')})" for x in v)


def d_ip_ifaddr(v):
    return "接口地址=" + ",".join(
        ".".join(str(x) for x in v[i:i + 4]) for i in range(0, len(v), 4))


def d_hostname(v):
    try:
        return "设备名=" + v.decode("ascii")
    except UnicodeDecodeError:
        return "设备名（非 ASCII，按十六进制展示）=" + hx(v)


def d_auth(v):
    scheme = v[0]
    sn = {1: "明文", 3: "HMAC-MD5", 54: "HMAC-SHA256(私用)"}
    return f"认证类型={scheme}({sn.get(scheme, '未知')})，数据={hx(v[1:])}"


TLV_SPEC = {
    1: ("Area Addresses", "区域地址列表，标识本路由器所在区域", d_area_addr),
    6: ("IS Neighbors", "本网段上已发现的邻居（LAN IIH 使用）", d_is_neighbors),
    8: ("Padding", "填充字段，把 Hello 补齐到接口 MTU", lambda v: f"填充 {len(v)} 字节"),
    10: ("Authentication", "认证信息", d_auth),
    22: ("Extended IS Reachability", "扩展邻居可达性，含度量与子 TLV", d_ext_is_reach),
    129: ("Protocols Supported", "支持的协议（NLPID 列表）", d_protocols),
    132: ("IP Interface Address", "接口 IPv4 地址", d_ip_ifaddr),
    137: ("Hostname", "动态主机名，便于运维识别", d_hostname),
}


def build_pdu():
    body = b""
    # LAN L1 IIH 专有字段
    body += bytes([1])                                   # Circuit Type: 1=L1
    body += binascii.unhexlify("203000110001")           # Source ID (System ID)
    body += (30).to_bytes(2, "big")                      # Holding Time = 30s
    body += (0).to_bytes(2, "big")                       # PDU Length（占位，稍后回填）
    body += bytes([64])                                  # Priority = 64
    body += binascii.unhexlify("203000110001") + bytes([2])  # LAN ID = SysID + CircuitID

    body += tlv(1, v_area_addr("49.0001"))                       # 区域地址 49.0001
    body += tlv(129, v_protocols([0xCC, 0x8E]))                  # 支持 IPv4/IPv6
    body += tlv(132, v_ip_ifaddr(["203.0.113.1"]))               # 接口地址
    body += tlv(137, v_hostname("R1"))                           # 主机名
    body += tlv(22, v_ext_is_reach([                             # 扩展邻居
        ("2030.0011.0002", 0x00, 10, tlv(6, bytes([203, 0, 113, 2]))),
    ]))
    body += tlv(6, v_is_neighbors([("2030.0011.0002", 0x00)]))   # 普通邻居
    body += tlv(10, v_auth(1, b"cisco"))                         # 明文认证

    # 8 字节公共头
    id_len = 6
    pdu_type = 15                                                # 15 = L1 LAN IIH
    type_byte = (pdu_type << 3) | 0x01                           # R=0, Version=1
    header = bytes([0x83, 0, 0x01, id_len, type_byte, 0x01, 0x00, 0x03])
    total = len(header) + len(body)
    # Length Indicator 覆盖公共头，PDU Length 覆盖整个 PDU
    header = bytearray(header)
    header[1] = len(header)
    header = bytes(header)
    body = bytearray(body)
    body[9:11] = total.to_bytes(2, "big")   # PDU 专有字段里的 PDU Length
    pdu = header + bytes(body)
    return header, bytes(body), pdu


def parse_pdu(pdu):
    header = pdu[:8]
    id_len = header[3]
    pdu_type = (header[4] >> 3) & 0x1F
    body = pdu[8:]
    print(pad("公共头字段", 26) + pad("取值", 20) + "说明")
    print(pad("Discriminator", 26) + pad(f"0x{header[0]:02X}", 20)
          + "0x83 = IS-IS，固定值")
    print(pad("Length Indicator", 26) + pad(str(header[1]), 20)
          + "固定头长度（通常 8）")
    print(pad("Version/Proto ID Ext", 26) + pad(str(header[2]), 20) + "固定为 1")
    print(pad("ID Length", 26) + pad(str(id_len), 20) + "System ID 长度，通常 6")
    print(pad("PDU Type", 26) + pad(str(pdu_type), 20)
          + "15=L1 LAN IIH 16=L2 LAN IIH 17=P2P IIH 18/20=LSP 24/25=CSNP 26/27=PSNP")
    types = {15: "L1 LAN Hello", 16: "L2 LAN Hello", 17: "P2P Hello",
             18: "L1 LSP", 20: "L2 LSP", 24: "L1 CSNP", 25: "L2 CSNP",
             26: "L1 PSNP", 27: "L2 PSNP"}
    print(pad("  → 译为", 26) + pad(types.get(pdu_type, "未知"), 20) + "")
    print(pad("Version", 26) + pad(str(header[5]), 20) + "固定为 1")
    print(pad("Max Area Addresses", 26) + pad(str(header[7]), 20) + "本节点支持的区域地址上限")
    print()
    # PDU 专有字段
    print(pad("PDU 专有字段", 26) + pad("取值", 20) + "说明")
    ct = body[0]
    print(pad("Circuit Type", 26) + pad(str(ct), 20) + f"{ct}=L1，2=L2，3=L1+L2")
    src = body[1:1 + id_len]
    h = hexs(src).upper()
    print(pad("Source ID", 26) + pad(".".join([h[i:i + 4] for i in range(0, 12, 4)]), 20)
          + "源 System ID")
    hold = int.from_bytes(body[7:9], "big")
    print(pad("Holding Time", 26) + pad(f"{hold} 秒", 20) + "邻居保持时间，默认 30s")
    plen = int.from_bytes(body[9:11], "big")
    print(pad("PDU Length", 26) + pad(str(plen), 20) + "整个 PDU 的字节数")
    pri = body[11]
    print(pad("Priority", 26) + pad(str(pri), 20) + "DIS 选举用，大者优")
    lanid = body[12:12 + id_len + 1]
    h = hexs(lanid).upper()
    print(pad("LAN ID", 26)
          + pad(".".join([h[i:i + 4] for i in range(0, 12, 4)]) + "." + h[12:14], 20)
          + "伪节点标识")
    print()
    # TLV 区
    off = 12 + id_len + 1
    print(pad("偏移", 8) + pad("类型", 12) + pad("长度", 8) + pad("名称", 28) + "解码")
    while off + 2 <= len(body):
        t = body[off]
        ln = body[off + 1]
        val = body[off + 2:off + 2 + ln]
        if len(val) != ln:
            break
        spec = TLV_SPEC.get(t)
        if spec:
            name, _, dec = spec
            decoded = dec(val)
        else:
            name, decoded = "未知 TLV", "原始值=" + hx(val)
        print(pad(str(off), 8) + pad(f"{t}(0x{t:02X})", 12) + pad(str(ln), 8)
              + pad(name, 28) + decoded)
        off += 2 + ln
    return pdu_type


def main():
    print()
    print("IS-IS Hello PDU 的 TLV 编码与解析演示 · 节点 R1（NET 49.0001.2030.0011.0001.00）")
    print()
    print("=" * 100)
    print("一、NET 地址（NSAP）结构：49.0001 | 2030.0011.0001 | 00")
    print("-" * 100)
    print(pad("字段", 22) + pad("长度", 12) + pad("本例取值", 22) + "说明")
    print(pad("AFI", 22) + pad("1 字节", 12) + pad("0x49", 22)
          + "地址族标识，49 为本地管理（私用）")
    print(pad("Area ID", 22) + pad("1~13 字节", 12) + pad("0x0001", 22)
          + "区域号，同区域才能建 L1 邻接")
    print(pad("System ID", 22) + pad("6 字节", 12) + pad("2030.0011.0001", 22)
          + "路由器唯一标识（类比 Router-ID）")
    print(pad("N-Selector", 22) + pad("1 字节", 12) + pad("0x00", 22)
          + "固定为 00，表示走 IS-IS 路由")
    print("-" * 100)
    print(">>> 结论：NET 就是「区域号 + System ID + 00」，OSPF 里 Router-ID 与区域号是分开的，")
    print("    IS-IS 把它们塞进同一个地址里；改区域就等于改 NET。")
    print()

    header, body, pdu = build_pdu()
    print("=" * 100)
    print("二、编码出的 LAN L1 Hello PDU（十六进制）")
    print("-" * 100)
    raw = hx(pdu).split()
    for i in range(0, len(raw), 16):
        print("  " + " ".join(raw[i:i + 16]))
    print("-" * 100)
    print(f"总长度 {len(pdu)} 字节 = 公共头 8 字节 + PDU 专有字段 {12 + 6 + 1} 字节 + TLV 区 "
          f"{len(pdu) - 8 - 19} 字节")
    print()

    print("=" * 100)
    print("三、把上面的字节流解析回来")
    print("-" * 100)
    parse_pdu(pdu)
    print()

    print("=" * 100)
    print("四、常考 IS-IS TLV 一览")
    print("-" * 100)
    print(pad("TLV", 8) + pad("名称", 30) + "用途与出现位置")
    extra = [
        (2, "IS Neighbors (旧)", "已废弃，被 6/22 取代"),
        (9, "LSP Entries", "LSP 里列出的其它 LSP，用于 CSNP/PSNP 同步"),
        (128, "IP Internal Reachability", "旧的内部 IPv4 可达性（narrow 度量）"),
        (130, "IPv4 Interface Address", "接口 IPv4 地址（扩展）"),
        (133, "IP Authentication", "IPv4 认证"),
        (240, "Router Capability", "路由器能力，如 SR/SRv6、Router-ID"),
    ]
    for t, name, use in extra:
        print(pad(str(t), 8) + pad(name, 30) + use)
    print("-" * 100)
    print(">>> 结论：TLV 是 IS-IS 的扩展基石 —— 新特性只需定义新 TLV，老设备跳过不认识的类型即可，")
    print("    因此 IS-IS 在不改协议版本的前提下持续演进（如 Segment Routing 用 TLV 240）。")
    print()
    print("小结：")
    print("1. IS-IS 报文 = 8 字节公共头 + PDU 专有字段 + 一串 TLV；解析的关键是「类型|长度|值」逐个推进。")
    print("2. NET = Area ID + System ID(6B) + N-Selector(00)，改 NET 就等于同时改区域与路由器标识。")
    print("3. PDU Type 决定报文语义（Hello/LSP/CSNP/PSNP），单播还是组播、L1 还是 L2 都写在类型里。")
    print()


if __name__ == "__main__":
    main()
