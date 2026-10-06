#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OSI 七层 / TCP-IP 四层 / 五层三套模型对照与协议映射。

运行: python3 layer_mapping.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 82
SUB = "-" * 82

# (OSI, 五层模型, TCP/IP 四层, PDU)
MODELS = [
    ("7 应用层",    "5 应用层",  "4 应用层",       "数据 Message"),
    ("6 表示层",    "并入应用层", "并入应用层",      "数据 Message"),
    ("5 会话层",    "并入应用层", "并入应用层",      "数据 Message"),
    ("4 传输层",    "4 传输层",  "3 传输层",       "段 Segment"),
    ("3 网络层",    "3 网络层",  "2 网际层",       "包 Packet"),
    ("2 数据链路层", "2 数据链路层", "1 网络接口层",   "帧 Frame"),
    ("1 物理层",    "1 物理层",  "并入网络接口层",   "比特 Bit"),
]

PROTOCOLS = [
    ("HTTP",    "应用层", "应用层", "应用层"),
    ("TLS",     "表示层", "应用层", "应用层"),
    ("TCP",     "传输层", "传输层", "传输层"),
    ("IP",      "网络层", "网络层", "网际层"),
    ("ARP",     "网络层", "网络层", "网际层"),
    ("Ethernet", "数据链路层", "数据链路层", "网络接口层"),
    ("STP",     "数据链路层", "数据链路层", "网络接口层"),
    ("UTP 双绞线", "物理层", "物理层", "网络接口层"),
]


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def main() -> None:
    print(SEP)
    print("三套分层模型对照：OSI 七层 / TCP-IP 四层 / 五层教学模型")
    print(SEP)
    print()
    print(SUB)
    print(pad("OSI 七层", 16) + pad("五层模型", 16) + pad("TCP/IP 四层", 18) + pad("PDU", 16))
    print(SUB)
    for osi, five, four, pdu in MODELS:
        print(pad(osi, 16) + pad(five, 16) + pad(four, 18) + pad(pdu, 16))
    print(SUB)
    print(">>> 五层模型 = 把 OSI 上三层合并为应用层；")
    print(">>> TCP/IP 四层 = 再把下两层合并为网络接口层。")
    print(">>> 传输层与网络层在三套模型中都独立存在，这是全书的固定锚点。")
    print()

    print(SUB)
    print("同一份协议清单，分别落到三套模型上")
    print(SUB)
    print(pad("协议", 14) + pad("OSI 七层落点", 16) + pad("五层落点", 16) + pad("四层落点", 18))
    print(SUB)
    for p, osi, five, four in PROTOCOLS:
        print(pad(p, 14) + pad(osi, 16) + pad(five, 16) + pad(four, 18))
    print(SUB)
    print(">>> TLS 在 OSI 属表示层，在 TCP/IP 里并入应用层，这是两套模型最常见的分歧。")
    print(">>> ARP 在 TCP/IP 里通常归网际层（服务于 IP），OSI 视角下横跨 2/3 层。")
    print()

    print(SUB)
    print("同层逻辑通信 · 异层实体调用")
    print(SUB)
    print("  场景：PC1 浏览器访问 PC2 上的 Web 服务")
    print()
    print("  PC1 协议栈                               PC2 协议栈")
    print("  +--------------+                        +--------------+")
    print("  | 应用层 HTTP   | <----- 逻辑对等 -----> | 应用层 HTTP   |")
    print("  +--------------+                        +--------------+")
    print("  | 传输层 TCP    | <----- 逻辑对等 -----> | 传输层 TCP    |")
    print("  +--------------+                        +--------------+")
    print("  | 网络层 IPv4   | <----- 逻辑对等 -----> | 网络层 IPv4   |")
    print("  +--------------+                        +--------------+")
    print("  | 链路层 ETH    | <----- 逻辑对等 -----> | 链路层 ETH    |")
    print("  +--------------+                        +--------------+")
    print("        ||  纵向：上层调用下层服务 HTTP -> TCP -> IP -> ETH")
    print("        \\/  横向：同层之间才是真正的逻辑对话")
    print()
    print("  异层调用示例：HTTP 通过 socket 接口把请求交给 TCP（跨层调用）")
    print("                TCP 分段后交给 IP；IP 查路由后交给以太网")
    print("  同层通信示例：PC1 的 TCP 只与 PC2 的 TCP 对话，两者按同一份 RFC 793 解释字段")
    print()

    print(SUB)
    print("三套模型的取舍")
    print(SUB)
    print(pad("模型", 16) + pad("层数", 8) + pad("主要用途", 34) + "为什么不直接用另一套")
    print(SUB)
    rows = [
        ("OSI 七层", "7", "教学、认证考试、故障分析通用语言", "层多但职责最清晰"),
        ("TCP/IP 四层", "4", "描述互联网真实协议实现", "上三层合并，贴合代码栈"),
        ("五层教学模型", "5", "讲「封装 / 解封装」最方便", "物理层要单独讲比特"),
    ]
    for name, n, use, why in rows:
        print(pad(name, 16) + pad(n, 8) + pad(use, 34) + why)
    print(SUB)
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print("1. 三套模型不是三套协议，是同一批协议的三种切分方式。")
    print("2. 差异只出现在上三层（会话/表示）与下两层（物理/链路）的归并。")
    print("3. 排障用「五层」最快：物理->链路->网络->传输->应用，逐层排除。")
    print("4. 同层逻辑通信、异层实体调用，是理解整个协议栈的起点。")
    print()


if __name__ == "__main__":
    main()
