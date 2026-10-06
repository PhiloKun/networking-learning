#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""演示应用数据从 PC1 到 PC2 的逐层封装与解封装过程。

运行: python3 osi_layers_demo.py [应用数据字节数]
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

APP_PAYLOAD_DEFAULT = 100
TCP_HDR = 20         # TCP 固定首部 20 字节（不含选项）
IPV4_HDR = 20        # IPv4 固定首部 20 字节（不含选项）
ETH_HDR = 14         # 目的 MAC 6 + 源 MAC 6 + 类型/长度 2
ETH_FCS = 4          # 帧尾 FCS（CRC-32）
PREAMBLE = 8         # 前导码 7 字节 + SFD 1 字节，物理层添加

# (层名, PDU 名称, 该层新增字节)
LAYERS_ENCAP = [
    ("7 应用层", "数据/报文 (Message)", 0),
    ("6 表示层", "（并入应用层）", 0),
    ("5 会话层", "（并入应用层）", 0),
    ("4 传输层", "段 (Segment)", TCP_HDR),
    ("3 网络层", "包 (Packet)", IPV4_HDR),
    ("2 数据链路层", "帧 (Frame)", ETH_HDR + ETH_FCS),
    ("1 物理层", "比特 (Bit)", PREAMBLE),
]

SEP = "=" * 78
SUB = "-" * 78


def dw(s: str) -> int:
    """字符串显示宽度：东亚宽/全角字符按 2 列计。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def encapsulate(payload_len: int) -> list[tuple[str, str, int, int]]:
    rows: list[tuple[str, str, int, int]] = []
    total = payload_len
    for name, pdu, add in LAYERS_ENCAP:
        total += add
        rows.append((name, pdu, add, total))
    return rows


def decapsulate(payload_len: int) -> list[tuple[str, str, int, int]]:
    total = payload_len + sum(add for _, _, add in LAYERS_ENCAP)
    rows: list[tuple[str, str, int, int]] = []
    for name, pdu, add in reversed(LAYERS_ENCAP):
        remain = total - add
        rows.append((name, pdu, add, remain))
        total = remain
    return rows


def main() -> None:
    payload = int(sys.argv[1]) if len(sys.argv) > 1 else APP_PAYLOAD_DEFAULT
    frame_len = payload + TCP_HDR + IPV4_HDR + ETH_HDR + ETH_FCS
    overhead = frame_len - payload

    print(SEP)
    print("分层封装 / 解封装演示 · PC1 -> PC2")
    print(SEP)
    print(f"应用数据（例如一条 HTTP 请求的载荷） = {payload} 字节")
    print(f"统一头部：TCP {TCP_HDR}B + IPv4 {IPV4_HDR}B + 以太网头 {ETH_HDR}B + FCS {ETH_FCS}B")
    print(f"物理层额外前导码 + SFD = {PREAMBLE} 字节（不上送上层，仅用于位同步）")
    print()

    print(SUB)
    print("【一】PC1 发送方向 · 逐层封装（自顶向下）")
    print(SUB)
    print(pad("层次", 16) + pad("PDU 名称", 24) + pad("新增", 8, True) + pad("累计", 10, True))
    print(SUB)
    for name, pdu, add, total in encapsulate(payload):
        add_s = "—" if add == 0 else f"+{add}B"
        print(pad(name, 16) + pad(pdu, 24) + pad(add_s, 8, True) + pad(f"{total}B", 10, True))
    print(SUB)
    wire_bits = (frame_len + PREAMBLE) * 8
    print(f">>> 应用层 {payload}B 的数据，最终是 {frame_len}B 的以太网帧，"
          f"含前导码共 {wire_bits} bit 上线。")
    print(f">>> 封装开销 = {overhead}B，开销占比 = {overhead}B / {frame_len}B = "
          f"{overhead / frame_len * 100:.2f}%")
    if frame_len < 64:
        print(f">>> 帧长 {frame_len}B < 以太网最小帧 64B，"
              f"网卡自动填充 {64 - frame_len}B 到 64B 再发。")
    else:
        print(f">>> 帧长 {frame_len}B >= 以太网最小帧 64B，无需填充。")
    print()

    print(SUB)
    print("【二】PC2 接收方向 · 逐层解封装（自底向上）")
    print(SUB)
    print(pad("层次", 16) + pad("剥掉头部", 10, True) + pad("剩余载荷", 12, True) + "  动作")
    print(SUB)
    for name, pdu, add, remain in decapsulate(payload):
        if name.startswith("1"):
            action = "校验前导码后重组比特流"
        elif name.startswith("2"):
            action = "验 FCS，查目的 MAC，剥 14B 帧头 + 4B 帧尾"
        elif name.startswith("3"):
            action = "验首部校验和，查目的 IP，剥 20B IP 头"
        elif name.startswith("4"):
            action = "按目的端口找套接字，剥 20B TCP 头"
        elif name.startswith("7"):
            action = "还原应用数据，交给应用程序"
        else:
            action = "并入应用层，无独立动作"
        add_s = "—" if add == 0 else f"-{add}B"
        print(pad(name, 16) + pad(add_s, 10, True) + pad(f"{remain}B", 12, True) + "  " + action)
    print(SUB)
    print(f">>> PC2 交付给应用的仍是最初的 {payload}B。")
    print(">>> 每层只认识「本层头部 + 上层数据」，这就是分层解耦的价值。")
    print()

    print(SUB)
    print("【三】同层逻辑通信示意（物理上仍是纵向逐层传递）")
    print(SUB)
    print("  PC1                                                   PC2")
    print("  +--------------+      应用层逻辑通信     +--------------+")
    print("  | 7 应用层      | <=====================> | 7 应用层      |")
    print("  +--------------+                          +--------------+")
    print("  | 4 传输层(段)  | <=====================> | 4 传输层(段)  |")
    print("  +--------------+                          +--------------+")
    print("  | 3 网络层(包)  | <=====================> | 3 网络层(包)  |")
    print("  +--------------+                          +--------------+")
    print("  | 2 链路层(帧)  | <=====================> | 2 链路层(帧)  |")
    print("  +-------+------+                          +------+-------+")
    print("          |             ----- 物理介质 -----        |")
    print("          +------------------------------------------+")
    print("  虚线：同层之间「逻辑上」对话；实线：报文实际沿协议栈纵向传递。")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print("1. 每下穿一层就加一个本层头部，PDU 名依次为 数据 -> 段 -> 包 -> 帧 -> 比特。")
    print(f"2. {payload}B 应用数据被封装为 {frame_len}B 帧，头部开销 {overhead}B，"
          f"占 {overhead / frame_len * 100:.1f}%。")
    print("3. 解封装逐层剥头，任何一层校验失败（FCS / 校验和）都会丢包，不上报上层。")
    print("4. 物理层比特流才是真正上线的形态，前导码只做时钟同步，不算有效帧。")
    print()


if __name__ == "__main__":
    main()
