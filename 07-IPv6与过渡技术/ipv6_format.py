#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPv6 地址压缩 / 展开 / 合法性校验 / 类型识别，含「:: 只能出现一次」边界用例。

运行: python3 ipv6_format.py            # 跑内置用例集
     python3 ipv6_format.py 2001:db8::1
"""
import ipaddress
import sys

sys.dont_write_bytecode = True

# (地址, 期望规范形式) —— 用 RFC 5952 的压缩规则校验自己的实现
CASES = [
    ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
    ("2001:db8:0:0:0:0:0:1", "2001:db8::1"),
    ("2001:db8::0:1", "2001:db8::1"),
    ("0000:0000:0000:0000:0000:0000:0000:0001", "::1"),
    ("0000:0000:0000:0000:0000:0000:0000:0000", "::"),
    ("fe80:0000:0000:0000:0200:00ff:fe00:000a", "fe80::200:ff:fe00:a"),
    ("2001:db8:abcd:0012:0000:0000:0000:0001", "2001:db8:abcd:12::1"),
    ("ff02:0000:0000:0000:0000:0000:0000:0001", "ff02::1"),
    # 边界：8 组全非零时不能压缩，且必须去掉前导零
    ("2001:0db8:0001:0002:0003:0004:0005:0006", "2001:db8:1:2:3:4:5:6"),
    # 边界：单个零组不能用 :: 代替
    ("2001:db8:0:1:2:3:4:5", "2001:db8:0:1:2:3:4:5"),
]

INVALID = [
    "2001:db8::1::2",          # :: 出现两次
    "2001:db8:1:2:3:4:5",      # 组数不足且无 ::
    "2001:db8:1:2:3:4:5:6:7",  # 组数过多
    "2001:db8:::1",            # 三个冒号
    "2001:db8:gggg::1",        # 非法十六进制字符
    "2001:db8::1/129",         # 非法前缀长度
]

# 地址类型表：(前缀, 类型名, 用途说明)
TYPES = [
    ("::1/128", "环回 Loopback", "本机协议栈内部，等价于 IPv4 的 127.0.0.1"),
    ("::/128", "未指定 Unspecified", "仅作 SLAAC/DAD 的源地址，不能作目的地址"),
    ("::ffff:0:0/96", "IPv4 映射 IPv4-mapped", "双栈 socket 表示 IPv4 对端"),
    ("64:ff9b::/96", "NAT64 知名前缀", "RFC 6052，NAT64 转换用的固定前缀"),
    ("100::/64", "丢弃前缀 Discard-Only", "RFC 6666，发给它的包一律丢弃"),
    ("2001::/23", "IETF 协议保留", "含 Teredo 2001::/32 等"),
    ("2001:db8::/32", "文档专用 Documentation", "RFC 3849，本仓库教学统一使用"),
    ("2002::/16", "6to4", "自动隧道，内嵌 IPv4 地址"),
    ("fc00::/7", "唯一本地 Unicast Local (ULA)", "RFC 4193，私网用途，等价于 IPv4 私网"),
    ("fe80::/10", "链路本地 Link-Local", "每接口自动生成，仅本链路有效"),
    ("ff00::/8", "组播 Multicast", "取代 IPv4 广播，替代 D 类"),
    ("2000::/3", "全球单播 Global Unicast (GUA)", "公网可路由，2000::/3 = 2000~3fff"),
]


def strip_group(g: str) -> str:
    return g.lstrip("0") or "0"


def compress(addr: ipaddress.IPv6Address) -> str:
    """按 RFC 5952 压缩：① 去前导零 ② 最长连续零组（长度 ≥2）用 :: ③ 取最靠左的等长零段。"""
    groups = addr.exploded.split(":")           # 8 组，每组 4 位十六进制
    best_start, best_len, cur = -1, 0, -1
    for i, g in enumerate(groups):
        if g == "0000":
            if cur < 0:
                cur = i
        else:
            if cur >= 0:
                if i - cur > best_len:          # 用 > 保证「最靠左」胜出
                    best_start, best_len = cur, i - cur
                cur = -1
    if cur >= 0 and 8 - cur > best_len:
        best_start, best_len = cur, 8 - cur
    if best_len < 2:                            # 单个零组不能压缩
        return ":".join(strip_group(g) for g in groups)
    left = ":".join(strip_group(g) for g in groups[:best_start])
    right = ":".join(strip_group(g) for g in groups[best_start + best_len:])
    return f"{left}::{right}"


def expand(text: str) -> str:
    return ipaddress.ip_address(text).exploded


def identify(addr: ipaddress.IPv6Address) -> list:
    out = []
    for net, name, note in TYPES:
        if addr in ipaddress.ip_network(net):
            out.append((name, note, net))
    if not out:
        out.append(("其他/未知", "不在内置类型表中", "-"))
    return out


def solicited_node(addr: ipaddress.IPv6Address) -> str:
    """请求节点组播 = ff02::1:ff00:0/104 + 地址低 24 位。"""
    low24 = int(addr) & 0xFFFFFF
    return f"ff02::1:ff{low24 >> 16:02x}:{low24 & 0xFFFF:x}"


def is_valid(text: str) -> bool:
    """含 / 的按接口（地址+前缀）校验，否则按纯地址校验。"""
    try:
        if "/" in text:
            ipaddress.ip_interface(text)
        else:
            ipaddress.ip_address(text)
        return True
    except ValueError:
        return False


def self_check() -> None:
    for text, expect in CASES:
        got = compress(ipaddress.ip_address(text))
        assert got == expect, f"压缩错误: {text} → {got}，期望 {expect}"
        # 与标准库的规范形式一致
        assert str(ipaddress.ip_address(text)) == expect, text
        # 展开后必须恰好 8 组、每组 4 位
        ex = expand(text)
        assert len(ex.split(":")) == 8 and all(len(g) == 4 for g in ex.split(":")), ex
    for bad in INVALID:
        assert not is_valid(bad), f"应当拒绝但被接受: {bad}"
    # 请求节点组播的精确校验
    assert solicited_node(ipaddress.ip_address("2001:db8::1")) == "ff02::1:ff00:1"
    assert solicited_node(ipaddress.ip_address("fe80::200:ff:fe00:a")) == "ff02::1:ff00:a"


def show(text: str) -> None:
    addr = ipaddress.ip_address(text)
    print(f"输入           : {text}")
    print(f"规范压缩形式   : {compress(addr)}")
    print(f"完整展开形式   : {expand(addr)}")
    print(f"二进制         : {format(int(addr), '0128b')}")
    print(f"是否合法       : 是")
    for name, note, net in identify(addr):
        print(f"类型           : {name}  [匹配 {net}]")
        print(f"                 {note}")
    print(f"请求节点组播   : {solicited_node(addr)}   （NDP 的 NS 报文就发给它）")
    lo, hi = int(addr) & 0xFFFFFF, int(addr) & 0xFFFFFF
    print(f"低 24 位       : {lo:06x}   （请求节点组播只取这 24 位，故同一 /104 内会重叠）")


def main() -> int:
    self_check()
    print("=" * 80)
    print("IPv6 地址压缩 / 展开 / 校验 / 类型识别（压缩严格遵循 RFC 5952）")
    print("=" * 80)
    print("内置用例集（压缩结果已与标准库逐条断言一致）：")
    print("-" * 80)
    print(f"{'输入':<46}{'规范形式'}")
    print("-" * 80)
    for text, expect in CASES:
        print(f"{text:<46}{expect}")
    print("-" * 80)
    print(f"{'非法输入':<46}{'拒绝原因'}")
    print("-" * 80)
    reasons = [
        ":: 只能出现一次",
        "组数不足 8 且无 ::",
        "组数超过 8",
        "连续三个冒号非法",
        "含非法十六进制字符 g",
        "前缀长度必须 0~128",
    ]
    for bad, why in zip(INVALID, reasons):
        got = "被接受（不应发生）" if is_valid(bad) else "已拒绝"
        print(f"{bad:<46}{got}：{why}")
    print()
    text = sys.argv[1] if len(sys.argv) > 1 else "2001:db8:abcd:0012:0000:0000:0000:0001"
    print("=" * 80)
    print("单地址分析")
    print("=" * 80)
    try:
        show(text)
    except ValueError as exc:
        print(f"[输入错误] {text!r} 不是合法 IPv6 地址：{exc}")
        return 0
    print("-" * 80)
    print("压缩三条规则（RFC 5952）：")
    print("  1. 每组十六进制去掉前导零，但至少要保留 1 位（0000 写成 0，不写成空）。")
    print("  2. 最长的一段连续零组用 :: 代替，且长度必须 ≥ 2 组。")
    print("  3. 有多段等长时只压缩最靠左的那一段；整个地址全零写作 :: 。")
    print(">>> 结论：2001:0db8:0000:...:0001 的规范形式是 2001:db8::1，输入输出都应按此规范化。")
    print(">>> 结论：:: 只能出现一次，出现两次就无法确定补多少组零，直接判非法。")
    print()
    print("小结")
    print("  1. 128 位地址写成 8 组 16 位十六进制；压缩只为可读性，语义完全等价。")
    print("  2. 请求节点组播只取地址低 24 位，因此同一 ff02::1:ff00:0/104 内多个地址会映射到同一组播。")
    print("  3. 类型识别靠前缀匹配：fe80::/10 链路本地、fc00::/7 私有、2000::/3 公网、ff00::/8 组播。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
