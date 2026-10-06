#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPv4 子网计算器：由 IP/前缀 算出网络号、广播地址、主机范围、通配符、类别与地址性质。

运行: python3 ipcalc.py            # 用内置默认值
     python3 ipcalc.py 10.1.2.3/22
"""
import ipaddress
import sys

sys.dont_write_bytecode = True

# 特殊用途网段表（RFC 6890 / RFC 5737 / RFC 6598）
SPECIAL_BLOCKS = [
    ("0.0.0.0/8", "「本网络」保留，仅可作源地址"),
    ("10.0.0.0/8", "RFC 1918 私有地址（A 类私有）"),
    ("100.64.0.0/10", "RFC 6598 运营商级 NAT（CGNAT）保留"),
    ("127.0.0.0/8", "回环地址，本机协议栈内部使用"),
    ("169.254.0.0/16", "链路本地地址（APIPA），DHCP 失败时自动配置"),
    ("172.16.0.0/12", "RFC 1918 私有地址（B 类私有）"),
    ("192.0.2.0/24", "RFC 5737 TEST-NET-1 文档专用"),
    ("192.168.0.0/16", "RFC 1918 私有地址（C 类私有）"),
    ("198.18.0.0/15", "RFC 2544 网络设备基准测试保留"),
    ("198.51.100.0/24", "RFC 5737 TEST-NET-2 文档专用"),
    ("203.0.113.0/24", "RFC 5737 TEST-NET-3 文档专用"),
    ("224.0.0.0/4", "组播地址（D 类）"),
    ("240.0.0.0/4", "保留地址（E 类），255.255.255.255 为受限广播"),
]
PRIVATE_NETS = [ipaddress.ip_network(b) for b, _ in SPECIAL_BLOCKS
                if "私有" in _ or "回环" in _ or "链路本地" in _]


def fmt(ip: ipaddress.IPv4Address) -> str:
    return str(ip)


def addr_class(ip: ipaddress.IPv4Address) -> tuple:
    """分类编址（Classful）下的类别与默认掩码。仅供理解历史，实际按前缀转发。"""
    o = int(str(ip).split(".")[0])
    if o == 0:
        return "保留(0/8)", 8
    if o == 127:
        return "A(回环)", 8
    if 1 <= o <= 126:
        return "A", 8
    if 128 <= o <= 191:
        return "B", 16
    if 192 <= o <= 223:
        return "C", 24
    if 224 <= o <= 239:
        return "D(组播)", 4
    return "E(保留)", 4


def classify(ip: ipaddress.IPv4Address) -> list:
    tags = []
    for block, note in SPECIAL_BLOCKS:
        if ip in ipaddress.ip_network(block):
            tags.append(f"{note} [{block}]")
    if not tags:
        tags.append("全球可路由单播地址（公网地址）")
    return tags


def wildcard(mask: ipaddress.IPv4Address) -> str:
    octets = [255 - int(x) for x in str(mask).split(".")]
    return ".".join(str(o) for o in octets)


def analyze(text: str) -> None:
    iface = ipaddress.ip_interface(text)
    net = iface.network
    ip = iface.ip
    prefix = net.prefixlen
    mask = net.netmask
    hosts = list(net.hosts())

    print(f"输入           : {text}")
    print(f"IP 地址        : {fmt(ip)}")
    print(f"前缀长度       : /{prefix}")
    print(f"子网掩码       : {mask}")
    print(f"通配符掩码     : {wildcard(mask)}   （= 255.255.255.255 − 掩码）")
    print(f"网络地址       : {net.network_address}")
    print(f"广播地址       : {net.broadcast_address}")
    print(f"地址总数       : {net.num_addresses}  （= 2^(32−{prefix})）")
    if prefix >= 31:
        print(f"可用主机数     : {len(hosts)}  （/31 为点对点，/32 为主机路由，无网络/广播地址）")
        print(f"主机范围       : {hosts[0]} ~ {hosts[-1]}" if hosts else "主机范围       : 无")
    else:
        print(f"可用主机数     : {net.num_addresses - 2}  （= 2^(32−{prefix}) − 2）")
        print(f"主机范围       : {hosts[0]} ~ {hosts[-1]}")
    cls, defp = addr_class(ip)
    print(f"分类地址类别   : {cls} 类（默认掩码 /{defp}，仅为历史概念）")
    print(f"IP 的二进制    : {'.'.join(format(b, '08b') for b in ip.packed)}")
    print(f"掩码的二进制   : {'.'.join(format(b, '08b') for b in mask.packed)}")
    print("地址性质       :")
    for t in classify(ip):
        print(f"  - {t}")
    print(f"是否私有       : {'是' if any(ip in n for n in PRIVATE_NETS) else '否'}")


def self_check() -> None:
    """自校验：内置默认用例必须逐项正确，否则直接抛错。"""
    net = ipaddress.ip_network("192.0.2.130/26", strict=False)
    assert str(net.network_address) == "192.0.2.128"
    assert str(net.broadcast_address) == "192.0.2.191"
    assert net.num_addresses == 64
    h = list(net.hosts())
    assert str(h[0]) == "192.0.2.129" and str(h[-1]) == "192.0.2.190"
    assert len(h) == 62
    assert wildcard(net.netmask) == "0.0.0.63"
    assert ipaddress.ip_address("192.0.2.130") in ipaddress.ip_network("192.0.2.0/24")
    # 校验特殊段判定
    assert any(ipaddress.ip_address("10.1.1.1") in n for n in PRIVATE_NETS)
    assert not any(ipaddress.ip_address("192.0.2.1") in n for n in PRIVATE_NETS)


def main() -> int:
    self_check()
    text = sys.argv[1] if len(sys.argv) > 1 else "192.0.2.130/26"
    print("=" * 70)
    print("IPv4 子网计算器（默认用例 192.0.2.130/26）")
    print("=" * 70)
    try:
        analyze(text)
    except ValueError as exc:
        print(f"[输入错误] {text!r} 不是合法的 IP/前缀：{exc}")
        print("正确格式示例：192.0.2.130/26 、 10.1.2.3 、 2001:db8::1/64（IPv6 请用第 07 章脚本）")
        return 0
    print("-" * 70)
    print("计算过程（以默认用例 192.0.2.130/26 为例）：")
    print("  1. 块大小 = 2^(32−26) = 2^6 = 64")
    print("  2. 网络地址 = IP 向下对齐到 64 的整数倍：130 → 128，即 192.0.2.128")
    print("  3. 广播地址 = 网络地址 + 块大小 − 1 = .128 + 64 − 1 = .191")
    print("  4. 可用主机 = 块大小 − 2 = 62（.129 ~ .190）")
    print(">>> 结论：192.0.2.130/26 属于 192.0.2.128/26，是 RFC 5737 文档专用段，非私网也非公网可路由。")
    print()
    print("小结")
    print("  1. 任何子网计算只需三步：算块大小、向下对齐求网络号、加块大小减一求广播。")
    print("  2. 通配符掩码就是掩码按位取反，ACL 里必须用它而不是正掩码。")
    print("  3. 「私有」是 RFC 1918 三个段的性质，和「保留 / 文档专用」是两回事，别混用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
