#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BGP 四种报文结构（OPEN/UPDATE/KEEPALIVE/NOTIFICATION）与状态机迁移演示。

运行: python3 bgp_sm.py
"""
import sys
import binascii
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


def hx(b):
    return " ".join(f"{x:02X}" for x in b)


def msg(mtype, body):
    """BGP 公共报文头：16 字节 Marker(全 1) + 2 字节长度 + 1 字节类型。"""
    length = 19 + len(body)
    header = bytes([0xFF] * 16) + length.to_bytes(2, "big") + bytes([mtype])
    return header + body


def parse_msg(data):
    marker = data[:16]
    length = int.from_bytes(data[16:18], "big")
    mtype = data[18]
    types = {1: "OPEN", 2: "UPDATE", 3: "NOTIFICATION", 4: "KEEPALIVE",
             5: "ROUTE-REFRESH"}
    print(pad("字段", 22) + pad("长度", 12) + pad("取值", 26) + "说明")
    print(pad("Marker", 22) + pad("16 字节", 12) + pad(hx(marker[:4]) + " ...", 26)
          + "全 1，接收方用它做同步校验")
    print(pad("Length", 22) + pad("2 字节", 12) + pad(str(length), 26)
          + "含报文头的总长度，范围 19~4096")
    print(pad("Type", 22) + pad("1 字节", 12)
          + pad(f"{mtype}({types.get(mtype, '未知')})", 26) + "报文类型")
    return mtype, length


ATTR_FLAG = {
    1: ("ORIGIN", "0x40", "well-known mandatory，起源：0=IGP 1=EGP 2=INCOMPLETE"),
    2: ("AS_PATH", "0x40", "well-known mandatory，AS 序列（防环核心）"),
    3: ("NEXT_HOP", "0x40", "well-known mandatory，下一跳 IP"),
    4: ("MULTI_EXIT_DISC", "0x80", "optional non-transitive，MED，只在邻居 AS 间比较"),
    5: ("LOCAL_PREF", "0x40", "well-known discretionary，仅 iBGP 内传播"),
    6: ("ATOMIC_AGGREGATE", "0x40", "well-known discretionary，告知聚合已丢弃明细"),
    7: ("AGGREGATOR", "0xC0", "optional transitive，聚合者 AS 与 Router-ID"),
    8: ("COMMUNITY", "0xC0", "optional transitive，团体属性，用于打标签做策略"),
}


def describe_update(body):
    i = 0
    wlen = int.from_bytes(body[i:i + 2], "big")
    i += 2
    withdrawn = body[i:i + wlen]
    i += wlen
    plen = int.from_bytes(body[i:i + 2], "big")
    i += 2
    attrs = body[i:i + plen]
    i += plen
    nlri = body[i:]
    print(pad("Withdrawn Routes Length", 30) + pad("2 字节", 12) + str(wlen))
    print(pad("Withdrawn Routes", 30) + pad(f"{wlen} 字节", 12)
          + (hx(withdrawn) if withdrawn else "（无撤销）"))
    print(pad("Total Path Attribute Len", 30) + pad("2 字节", 12) + str(plen))
    print(pad("Path Attributes", 30) + pad(f"{plen} 字节", 12) + "见下表")
    print(pad("NLRI", 30) + pad(f"{len(nlri)} 字节", 12)
          + (hx(nlri) if nlri else "（纯撤销报文）"))
    print("-" * 100)
    print(pad("属性", 8) + pad("Flags", 10) + pad("值长", 8) + pad("名称", 24) + "含义")
    p = 0
    while p + 3 <= len(attrs):
        flags = attrs[p]
        atype = attrs[p + 1]
        alen = attrs[p + 2]
        val = attrs[p + 3:p + 3 + alen]
        name, flagnote, desc = ATTR_FLAG.get(atype, (f"类型{atype}", "?", "未知属性"))
        extra = ""
        if atype == 1 and alen == 1:
            extra = f"  值={val[0]}({['IGP', 'EGP', 'INCOMPLETE'][val[0]] if val[0] < 3 else '?'})"
        elif atype == 2:
            ases = [int.from_bytes(val[k:k + 2], "big") for k in range(2, len(val), 2)]
            if val and val[0] == 2:
                extra = "  值=AS_SEQUENCE " + " ".join(str(a) for a in ases)
            else:
                extra = "  值=" + hx(val)
        elif atype == 3 and alen == 4:
            extra = "  值=" + ".".join(str(x) for x in val)
        elif atype == 5 and alen == 4:
            extra = "  值=" + str(int.from_bytes(val, "big"))
        elif atype == 4 and alen == 4:
            extra = "  值=" + str(int.from_bytes(val, "big"))
        elif atype == 8:
            extra = "  值=" + hx(val)
        print(pad(str(atype), 8) + pad(f"0x{flags:02X}", 10) + pad(str(alen), 8)
              + pad(name, 24) + desc + extra)
        p += 3 + alen


def main():
    print()
    print("BGP 报文类型与状态机演示 · 本机 AS 65001，邻居 203.0.113.2（AS 65002）")
    print()

    # ---------------- 四类报文 ----------------
    print("=" * 100)
    print("一、四种报文（外加 ROUTE-REFRESH）的结构")
    print("-" * 100)
    print(pad("类型值", 8) + pad("名称", 18) + pad("长度范围", 14) + "作用")
    rows = [
        (1, "OPEN", "19 + 可变", "建连后首个报文，协商版本、AS、Hold Time、能力"),
        (2, "UPDATE", "19 + 可变", "宣告/撤销路由，承载路径属性与 NLRI"),
        (3, "NOTIFICATION", "19 + 可变", "出错时发送并立即断开，带错误码与子码"),
        (4, "KEEPALIVE", "19", "保活，只有公共头，没有正文"),
        (5, "ROUTE-REFRESH", "23", "请求对端重发某地址族的全部路由"),
    ]
    for t, n, l, d in rows:
        print(pad(str(t), 8) + pad(n, 18) + pad(l, 14) + d)
    print("-" * 100)
    print(">>> 结论：KEEPALIVE 只有 19 字节（16 字节 Marker + 2 字节长度 + 1 字节类型），")
    print("    所以 BGP 邻居保活的开销极低；默认 Hold Time 180 秒、Keepalive 60 秒（= Hold/3）。")
    print()

    # OPEN 报文
    caps = bytes([1, 4]) + bytes([0x00, 0x01, 0x00, 0x01])   # 能力1: MP-BGP, AFI=1(IPv4)
    caps += bytes([65, 4]) + (65001).to_bytes(4, "big")       # 能力65: 4 字节 AS 号
    caps += bytes([2, 0])                                     # 能力2: Route Refresh
    opt = bytes([2, len(caps)]) + caps                        # 可选参数类型 2 = 能力
    open_body = (bytes([4]) + (65001).to_bytes(2, "big")
                 + (180).to_bytes(2, "big") + bytes([203, 0, 113, 1])
                 + bytes([len(opt)]) + opt)
    open_msg = msg(1, open_body)
    print("=" * 100)
    print(f"二、构造一个 OPEN 报文（共 {len(open_msg)} 字节）")
    print("-" * 100)
    print("  " + hx(open_msg[:24]))
    print("  " + hx(open_msg[24:]))
    print("-" * 100)
    parse_msg(open_msg)
    print()
    print(pad("OPEN 正文", 28) + pad("长度", 12) + "取值 / 说明")
    print(pad("Version", 28) + pad("1 字节", 12) + "4（BGP-4，IPv6 也用 BGP-4 + MP-BGP）")
    print(pad("My Autonomous System", 28) + pad("2 字节", 12)
          + "65001（2 字节 AS；4 字节 AS 靠能力 65 协商）")
    print(pad("Hold Time", 28) + pad("2 字节", 12)
          + "180 秒；两端取较小值，0 表示不发送 Keepalive")
    print(pad("BGP Identifier", 28) + pad("4 字节", 12) + "203.0.113.1（BGP Router-ID）")
    print(pad("Opt Parm Len", 28) + pad("1 字节", 12) + f"{len(opt)} 字节可选参数")
    print(pad("Optional Parameters", 28) + pad(f"{len(opt)} 字节", 12)
          + "能力协商：MP-BGP / 4 字节 AS / Route Refresh")
    print()

    # UPDATE 报文
    attr_origin = bytes([0x40, 1, 1, 0])                       # ORIGIN = IGP
    aspath_val = bytes([2, 1]) + (65002).to_bytes(2, "big")    # AS_SEQUENCE, 1 个 AS
    attr_aspath = bytes([0x40, 2, len(aspath_val)]) + aspath_val
    attr_nh = bytes([0x40, 3, 4]) + bytes([203, 0, 113, 2])    # NEXT_HOP
    attr_med = bytes([0x80, 4, 4]) + (50).to_bytes(4, "big")   # MED = 50
    attrs = attr_origin + attr_aspath + attr_nh + attr_med
    nlri = bytes([24, 198, 51, 100])                           # /24 前缀，掩码 24
    upd_body = (bytes([0, 0])                                  # Withdrawn Routes Length = 0
                + len(attrs).to_bytes(2, "big") + attrs + nlri)
    upd_msg = msg(2, upd_body)
    print("=" * 100)
    print(f"三、构造一个 UPDATE 报文：宣告 198.51.100.0/24（共 {len(upd_msg)} 字节）")
    print("-" * 100)
    print("  " + hx(upd_msg))
    print("-" * 100)
    describe_update(upd_body)
    print("-" * 100)
    print(">>> 结论：NLRI 的编码是「1 字节前缀长度 + 前缀字节（末尾按字节补齐）」；")
    print("    198.51.100.0/24 只需 3 字节前缀 + 1 字节长度，共 4 字节。")
    print()

    # ---------------- 状态机 ----------------
    print("=" * 100)
    print("四、BGP 状态机：Idle → Connect → Active → OpenSent → OpenConfirm → Established")
    print("-" * 100)
    states = [
        ("Idle", "初始态，等待启动事件；拒绝所有入向连接",
         "接口 down / 路由不可达时停在这里；通常只看到「无邻居」"),
        ("Connect", "发起 TCP 179 连接，等待三次握手完成",
         "ConnectRetry 计时器 120s；若超时退到 Active"),
        ("Active", "TCP 连接失败后的重试态，持续尝试重新发起连接",
         "最常见的「卡住」状态：对端没监听 179、ACL 拦了、路由不可达"),
        ("OpenSent", "TCP 已建立，已发出 OPEN，等待对端 OPEN",
         "收到对端 OPEN 后校验版本/AS/Hold Time/Router-ID"),
        ("OpenConfirm", "已收到对端 OPEN 并回了 KEEPALIVE，等待对端 KEEPALIVE",
         "双方都在等对方的 KEEPALIVE，很快进入 Established"),
        ("Established", "邻居关系建立完成，开始交换 UPDATE",
         "稳态；可传路由。Hold Time 到点未收到任何报文则回 Idle"),
    ]
    print(pad("序号", 6) + pad("状态", 14) + pad("含义 / 动作", 52) + "排障要点")
    for i, (s, d, t) in enumerate(states, start=1):
        print(pad(str(i), 6) + pad(s, 14) + pad(d, 52) + t)
    print("-" * 100)
    print("迁移图：")
    print("  Idle ──启动──> Connect ──TCP成功──> OpenSent ──收到OPEN──> OpenConfirm")
    print("    ↑               │                                            │")
    print("    │         TCP失败│                                    收到KEEPALIVE")
    print("    │               ↓                                            ↓")
    print("    └──错误/超时/收到NOTIFICATION─────────── Established <────────┘")
    print("        Active <────ConnectRetry 120s 超时───── (从 Connect 退下)")
    print("-" * 100)
    print("常见卡点与原因对照：")
    trouble = [
        ("Idle", "没有到对端的路由，或邻居未使能", "先 ping 通对端环回，再检查是否 peer 配置生效"),
        ("Active", "TCP 179 连不上：对端没监听 / 中间 ACL 拦 / 路由不可达",
         "telnet 对端 179 测连通；display bgp peer 看是否反复 Connect/Active"),
        ("OpenSent", "版本或 AS 号不匹配，或 Router-ID 冲突",
         "检查两端的 AS 配置与 BGP Router-ID 是否重复"),
        ("OpenConfirm", "认证失败 / Hold Time 不匹配（0 与非 0）",
         "核对密码与 Hold Time 配置"),
        ("Established", "能建立但学不到路由", "查路由策略（filter-policy / route-policy）与地址族是否使能"),
    ]
    print(pad("卡在", 16) + pad("典型原因", 54) + "排查动作")
    for s, r, a in trouble:
        print(pad(s, 16) + pad(r, 54) + a)
    print("-" * 100)
    print(">>> 结论：邻居卡在 Active 几乎等价于「TCP 179 不通」；")
    print("    telnet <对端> 179 能立刻验证，是 BGP 排障的第一步。")
    print()
    print("小结：")
    print("1. BGP 四类报文共用 19 字节头（16 字节全 1 Marker + 长度 + 类型），网络层跑在 TCP 179 之上。")
    print("2. OPEN 协商版本、AS、Hold Time 与能力（MP-BGP / 4 字节 AS / Route Refresh），两端不一致就断。")
    print("3. UPDATE 由「撤销 + 路径属性 + NLRI」三段组成；ORIGIN/AS_PATH/NEXT_HOP 是必带属性。")
    print("4. 状态机 6 态里，Active 与 OpenSent 是两大高频卡点，分别对应 TCP 不通与参数不匹配。")
    print()


if __name__ == "__main__":
    main()
