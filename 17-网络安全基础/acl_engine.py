#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ACL 顺序匹配引擎：通配符掩码逐位比对 + 隐式 deny any 演示。

运行: python3 acl_engine.py
"""
import ipaddress
import sys
from dataclasses import dataclass
from typing import Optional

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78
WILDCARD_MAX = 0xFFFFFFFF


def ip2int(text: str) -> int:
    return int(ipaddress.IPv4Address(text))


def int2ip(value: int) -> str:
    return str(ipaddress.IPv4Address(value & WILDCARD_MAX))


def wildcard_from_prefix(prefix_len: int) -> int:
    """由前缀长度算通配符掩码（反掩码）。掩码位为 0 表示「必须匹配」，为 1 表示「忽略」。"""
    mask = (WILDCARD_MAX << (32 - prefix_len)) & WILDCARD_MAX
    return (~mask) & WILDCARD_MAX


def addr_matches(packet_ip: str, rule_ip: str, wildcard: int) -> tuple[bool, int]:
    """
    ACL 地址比对核心公式：((packet XOR rule) AND NOT wildcard) == 0
    NOT wildcard 把「忽略位」清零，只留下必须一致的比特参与比较。
    """
    diff = (ip2int(packet_ip) ^ ip2int(rule_ip)) & ((~wildcard) & WILDCARD_MAX)
    return diff == 0, diff


@dataclass
class AclRule:
    seq: int
    action: str              # permit / deny
    proto: str               # ip / tcp / udp / icmp
    src_ip: str
    src_wc: int
    src_port: Optional[int]
    dst_ip: str
    dst_wc: int
    dst_port: Optional[int]
    text: str


@dataclass
class Packet:
    proto: str
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    text: str


def evaluate(rules: list[AclRule], pkt: Packet) -> None:
    print(SUB)
    print(f"待匹配报文：{pkt.text}")
    print(f"  五元组 = proto={pkt.proto} src={pkt.src_ip}:{pkt.src_port} "
          f"dst={pkt.dst_ip}:{pkt.dst_port}")
    print(SUB)
    print(f"{'序号':<6}{'规则':<60}{'结果':<8}原因")
    print(SUB)
    for rule in rules:
        # 1) 协议比对
        proto_ok = (rule.proto == "ip") or (rule.proto == pkt.proto)
        # 2) 源地址比对
        src_ok, src_diff = addr_matches(pkt.src_ip, rule.src_ip, rule.src_wc)
        # 3) 目的地址比对
        dst_ok, dst_diff = addr_matches(pkt.dst_ip, rule.dst_ip, rule.dst_wc)
        # 4) 端口比对（仅 tcp/udp 规则有端口字段）
        sport_ok = rule.src_port is None or rule.src_port == pkt.src_port
        dport_ok = rule.dst_port is None or rule.dst_port == pkt.dst_port

        reasons = []
        if not proto_ok:
            reasons.append(f"协议不符(规则={rule.proto})")
        if not src_ok:
            reasons.append(f"源地址不匹配(XOR&mask=0x{src_diff:08X})")
        if not dst_ok:
            reasons.append(f"目的地址不匹配(XOR&mask=0x{dst_diff:08X})")
        if not sport_ok:
            reasons.append("源端口不符")
        if not dport_ok:
            reasons.append("目的端口不符")

        if not reasons:
            mark = "命中"
            detail = "所有字段一致"
            print(f"{rule.seq:<6}{rule.text:<60}{mark:<8}{detail}")
            print(SUB)
            verdict = "允许 (permit)" if rule.action == "permit" else "拒绝 (deny)"
            print(f">>> 结论：第 1 条命中规则是 seq={rule.seq}，动作 = {verdict}")
            if rule.action == "deny":
                print(">>> 该报文被丢弃，后续规则不再检查（ACL 命中即停，不继续往下匹配）")
            return
        print(f"{rule.seq:<6}{rule.text:<60}{'跳过':<8}{reasons[0]}")

    print(SUB)
    print(">>> 结论：所有显式规则都不匹配，命中「隐式 deny any」（每条 ACL 末尾自动隐含）")
    print(">>> 该报文被丢弃。这意味着「只写 permit 不写 deny」是危险的默认拒绝陷阱。")


def build_rules() -> list[AclRule]:
    # 规则中的 "any" 在数据结构里记作 0.0.0.0 + 通配符 255.255.255.255
    any_addr = "0.0.0.0"
    rules = [
        AclRule(10, "permit", "tcp", "192.0.2.0",
                wildcard_from_prefix(24), None, "198.51.100.10", 0, 443,
                "permit tcp 192.0.2.0 0.0.0.255 host 198.51.100.10 eq 443"),
        AclRule(20, "deny", "tcp", any_addr, WILDCARD_MAX, None, any_addr,
                WILDCARD_MAX, 23, "deny tcp any any eq 23"),
        AclRule(30, "permit", "icmp", "192.0.2.0", wildcard_from_prefix(24),
                None, any_addr, WILDCARD_MAX, None,
                "permit icmp 192.0.2.0 0.0.0.255 any"),
        AclRule(40, "permit", "udp", any_addr, WILDCARD_MAX, None, "198.51.100.0",
                wildcard_from_prefix(24), 53,
                "permit udp any 198.51.100.0 0.0.0.255 eq 53"),
    ]
    return rules


def wildcard_table() -> None:
    print(SUB)
    print("附：通配符掩码计算表（ACL 与 OSPF network 语句共用同一算法）")
    print(SUB)
    print(f"{'前缀':<8}{'点分掩码':<18}{'通配符掩码':<18}{'地址数':<10}等价写法")
    print(SUB)
    for plen in (8, 16, 20, 24, 25, 26, 27, 28, 30, 32):
        mask_int = (WILDCARD_MAX << (32 - plen)) & WILDCARD_MAX
        wc_int = (~mask_int) & WILDCARD_MAX
        count = 1 << (32 - plen)
        if plen == 32:
            equiv = "host <单个IP>"
        elif plen == 0:
            equiv = "any"
        else:
            equiv = "网络号 + 通配符"
        print(f"/{plen:<7}{int2ip(mask_int):<18}{int2ip(wc_int):<18}{count:<10}{equiv}")
    print(SUB)
    print(">>> host 等价于 通配符 0.0.0.0（32 位全比较）；any 等价于 255.255.255.255（32 位全忽略）")
    print(">>> 通配符掩码不是「子网掩码取反」的巧合，而是 ACL 的「忽略位标记」语义")


def main() -> None:
    print(SEP)
    print("ACL 顺序匹配引擎演示 · 扩展 ACL（编号 100）")
    print(SEP)

    print(SUB)
    print("ACL 100 规则表（自上而下匹配，命中即停）")
    print(SUB)
    for rule in build_rules():
        print(f"  {rule.seq:<5}{rule.action:<8}{rule.text}")
    print(f"  {'-':<5}{'deny':<8}any any（隐式 deny，不可见但真实存在）")
    print()

    packets = [
        Packet("tcp", "192.0.2.130", 51000, "198.51.100.10", 443,
               "办公网 PC 访问对外 HTTPS 服务"),
        Packet("tcp", "192.0.2.130", 51001, "198.51.100.10", 23,
               "办公网 PC 尝试 Telnet（应被 seq=20 拒绝）"),
        Packet("icmp", "192.0.2.77", 0, "203.0.113.1", 0,
               "办公网 PC1 ping 骨干路由器 R1"),
        Packet("udp", "203.0.113.9", 33000, "198.51.100.53", 53,
               "骨干网设备向对外 DNS 服务器查询"),
        Packet("tcp", "203.0.113.9", 40000, "192.0.2.130", 22,
               "外部设备尝试 SSH 进办公网（应命中隐式 deny）"),
    ]

    for idx, pkt in enumerate(packets, 1):
        print(f"\n【场景 {idx}】")
        evaluate(build_rules(), pkt)

    print()
    wildcard_table()

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. ACL 自上而下顺序匹配，命中第一条就执行动作并停止，绝不会有「后面的规则覆盖前面」的情况。")
    print("2. 地址比对公式 ((packet XOR rule) AND NOT wildcard) == 0；通配符位为 1 的比特被忽略。")
    print("3. 每条 ACL 末尾隐含 deny any，所以「只写 permit」= 其余全部拒绝，不是「全部放通」。")
    print("4. 精确匹配用 host（通配符 0.0.0.0），全放通用 any（通配符 255.255.255.255）。")
    print("5. 扩展 ACL 能匹配协议 + 源目地址 + 源目端口，标准 ACL 只能匹配源地址，粒度粗。")
    print()


if __name__ == "__main__":
    main()
