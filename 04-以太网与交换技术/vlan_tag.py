#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""802.1Q VLAN 标签构造与解析，以及 Access / Trunk 口收发规则的逐帧演示。"""
import sys
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 80
SUB = "-" * 80
TPID = 0x8100          # 802.1Q 标签协议标识


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def encode_tci(pcp: int, dei: int, vid: int) -> int:
    return ((pcp & 0x7) << 13) | ((dei & 0x1) << 12) | (vid & 0x0FFF)


def decode_tci(tci: int) -> tuple[int, int, int]:
    return (tci >> 13) & 0x7, (tci >> 12) & 0x1, tci & 0x0FFF


def fmt_frame(pcp: int, dei: int, vid: int, tagged: bool = True) -> str:
    if not tagged:
        return "未打标（Untagged）"
    return f"TPID 0x{TPID:04X}  PCP={pcp}  DEI={dei}  VID={vid}"


def main() -> None:
    print(SEP)
    print("802.1Q VLAN 标签构造 / 解析 与 Access / Trunk 口收发规则")
    print(SEP)

    print(SUB)
    print("【一】802.1Q 标签的比特布局（TCI 共 16 位）")
    print(SUB)
    print("  以太网帧插入位置：[DA 6B][SA 6B][TPID 2B][TCI 2B][Type 2B][载荷][FCS 4B]")
    print("                            ^^^^^^^^^^^^^^^^^^")
    print("  标签总长 = 4 字节（TPID 2 字节 + TCI 2 字节），帧因此变成 1518+4=1522 B")
    print()
    print("  TCI 16 位分配（高位在左）：")
    print("  +-----+-----+-----+-----+-------------------------------+")
    print("  |  PCP 3 位 | DEI 1 位 |           VID 12 位            |")
    print("  +-----+-----+-----+-----+-------------------------------+")
    print("   15    13    12      11                              0")
    print("   PCP：优先级 0~7，越大越优先（QoS）")
    print("   DEI：丢弃资格位，1 表示拥塞时可优先丢弃（原 CFI）")
    print("   VID：VLAN 编号 0~4095，其中 0 与 4095 保留，可用 1~4094（共 4094 个）")
    print()

    print(SUB)
    print("【二】手工构造几个标签，验证位运算")
    print(SUB)
    print(pad("PCP", 6) + pad("DEI", 6) + pad("VID", 8) + pad("TCI(十进制)", 14, True)
          + pad("TCI(十六进制)", 16, True) + "  完整标签")
    print(SUB)
    samples = [(0, 0, 10), (0, 0, 20), (5, 0, 30), (7, 1, 4094), (0, 0, 1)]
    for pcp, dei, vid in samples:
        tci = encode_tci(pcp, dei, vid)
        print(pad(str(pcp), 6) + pad(str(dei), 6) + pad(str(vid), 8)
              + pad(str(tci), 14, True) + pad(f"0x{tci:04X}", 16, True)
              + "  " + fmt_frame(pcp, dei, vid))
    print(SUB)
    print()
    # 解析回读
    print("解析回读（验证 encode / decode 对称）：")
    for pcp, dei, vid in samples:
        tci = encode_tci(pcp, dei, vid)
        dp, dd, dv = decode_tci(tci)
        ok = (dp, dd, dv) == (pcp, dei, vid)
        print(f"  TCI=0x{tci:04X} -> PCP={dp}, DEI={dd}, VID={dv}   一致: {ok}")
    print()
    # 展示 VID=10 的二进制
    tci = encode_tci(0, 0, 10)
    print(f"  例：VID=10 时 TCI = 0b{tci:016b}，其中低 12 位 {tci & 0xFFF:012b} = 10")
    print()

    print(SUB)
    print("【三】Access 口入站：未打标帧按 PVID 打标")
    print(SUB)
    print("端口 G0/1：mode access，PVID = 10")
    print(SUB)
    frames_in = [
        ("PC1", "02:00:00:00:00:0A", "02:00:00:00:00:0B"),
        ("PC3", "02:00:00:00:00:0C", "02:00:00:00:00:0A"),
    ]
    for label, src, dst in frames_in:
        pcp, dei, vid = 0, 0, 10
        tci = encode_tci(pcp, dei, vid)
        print(f"  [{label}] 入站：{fmt_frame(0, 0, 0, tagged=False)}")
        print(f"        动作：Access 口把未打标帧打上 PVID 标签 -> {fmt_frame(pcp, dei, vid)}"
              f"  (TCI=0x{tci:04X})")
        print()
    print(">>> Access 口不关心帧进来时有没有标签，统一按 PVID 打标后送入交换机内部。")
    print()

    print(SUB)
    print("【四】Trunk 口出站：按允许列表放行，Native VLAN 去标")
    print(SUB)
    print("端口 G0/24：mode trunk，允许 VLAN 1,10,20,30，Native VLAN = 1")
    print(SUB)
    print(pad("帧 VID", 10) + pad("是否在允许列表", 18) + pad("出站动作", 16) + "出站帧形态")
    print(SUB)
    cases = [1, 10, 20, 30, 40]
    for vid in cases:
        allowed = vid in (1, 10, 20, 30)
        if not allowed:
            action = "丢弃"
            form = "不发送"
        elif vid == 1:
            action = "去标后发送"
            form = fmt_frame(0, 0, 0, tagged=False)
        else:
            action = "带标发送"
            form = fmt_frame(0, 0, vid)
        print(pad(str(vid), 10) + pad("是" if allowed else "否", 18)
              + pad(action, 16) + form)
    print(SUB)
    print(">>> Trunk 口用标签区分不同 VLAN；Native VLAN 的帧不打标出去，")
    print("    对端 Trunk 口的 Native VLAN 必须配置一致，否则会串 VLAN。")
    print()

    print(SUB)
    print("【五】完整收发链路：PC1 -> SW1 -> Trunk -> SW2 -> PC2")
    print(SUB)
    print("  PC1 --(access, PVID10)-- SW1 --(trunk, 允许10/20)-- SW2 --(access, PVID10)-- PC2")
    print()
    steps = [
        ("PC1 发出", "未打标帧（PVID 由接入交换机决定）"),
        ("SW1 G0/1 入站", "Access 口按 PVID 打标 -> VID=10"),
        ("SW1 查 MAC 表", "从 G0/24 Trunk 口转发，保持 VID=10 标签"),
        ("SW1 G0/24 出站", "VID=10 非 Native，带标发送 TPID 0x8100 VID=10"),
        ("SW2 G0/24 入站", "Trunk 口识别标签，保留 VID=10"),
        ("SW2 查 MAC 表", "从 PC2 所在 Access 口转发"),
        ("SW2 Access 口出站", "剥掉标签，还原成未打标帧发给 PC2"),
        ("PC2 收到", "未打标帧，与 PC1 发出的完全一致"),
    ]
    for i, (where, what) in enumerate(steps, 1):
        print(f"  {i}. {pad(where, 20)} {what}")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print("1. 802.1Q 标签共 4 字节（TPID 2B + TCI 2B），TCI 内含 PCP 3 位、DEI 1 位、VID 12 位。")
    print("2. VID 可用范围 1~4094，共 4094 个，这是二层网络段数量的硬上限（由 12 位决定）。")
    print("3. Access 口入站打 PVID、出站剥标签；Trunk 口默认带标收发，Native VLAN 去标。")
    print("4. Trunk 两端的 Native VLAN 与允许列表必须一致，否则会出现 VLAN 泄漏或流量被丢。")
    print()


if __name__ == "__main__":
    main()
