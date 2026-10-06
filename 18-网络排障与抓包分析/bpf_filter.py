#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BPF 风格过滤表达式解析器：把 host/net/port/tcp 与 and/or/not 编译成匹配器。

运行: python3 bpf_filter.py
"""
import ipaddress
import sys
from dataclasses import dataclass

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78


@dataclass
class Pkt:
    name: str
    proto: str          # tcp / udp / icmp / arp
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int


# ---------- 词法分析 ----------
def tokenize(expr: str) -> list:
    out = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "()!":
            out.append(ch)
            i += 1
            continue
        j = i
        while j < len(expr) and (not expr[j].isspace()) and expr[j] not in "()!":
            j += 1
        out.append(expr[i:j])
        i = j
    return out


def parse_net(token: str):
    """接受 192.0.2.0/24 或 192.0.2.0/255.255.255.0 两种写法。"""
    if "/" in token:
        addr, mask = token.split("/", 1)
        if "." in mask:
            mask_int = int(ipaddress.IPv4Address(mask))
            prefix = bin(mask_int).count("1")
            return ipaddress.ip_network(f"{addr}/{prefix}", strict=False)
        return ipaddress.ip_network(token, strict=False)
    return ipaddress.ip_network(token + "/32", strict=False)


# ---------- 语法分析（递归下降） ----------
class Parser:
    def __init__(self, tokens: list):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def parse(self):
        node = self.parse_or()
        if self.pos != len(self.tokens):
            raise ValueError(f"表达式存在多余 token: {self.peek()!r}")
        return node

    def parse_or(self):
        node = self.parse_and()
        while self.peek() in ("or", "||"):
            self.next()
            node = ("or", node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_not()
        while self.peek() in ("and", "&&"):
            self.next()
            node = ("and", node, self.parse_not())
        return node

    def parse_not(self):
        if self.peek() in ("not", "!"):
            self.next()
            return ("not", self.parse_not())
        return self.parse_primary()

    def parse_primary(self):
        tok = self.peek()
        if tok == "(":
            self.next()
            node = self.parse_or()
            if self.next() != ")":
                raise ValueError("括号不匹配")
            return node
        return self.parse_qualifier()

    def parse_qualifier(self):
        tok = self.next()
        if tok in ("tcp", "udp", "icmp", "arp", "ip"):
            return ("proto", tok)
        direction = "either"
        if tok in ("src", "dst"):
            direction = tok
            tok = self.next()
        if tok == "host":
            addr = self.next()
            ipaddress.IPv4Address(addr)
            return ("host", direction, addr)
        if tok == "net":
            return ("net", direction, parse_net(self.next()))
        if tok == "port":
            return ("port", direction, int(self.next()))
        raise ValueError(f"无法识别的过滤原语: {tok!r}")


# ---------- 求值 ----------
def evaluate(node, pkt: Pkt) -> bool:
    kind = node[0]
    if kind == "and":
        return evaluate(node[1], pkt) and evaluate(node[2], pkt)
    if kind == "or":
        return evaluate(node[1], pkt) or evaluate(node[2], pkt)
    if kind == "not":
        return not evaluate(node[1], pkt)
    if kind == "proto":
        return pkt.proto == node[1]
    if kind == "host":
        _k, direction, addr = node
        if direction == "src":
            return pkt.src_ip == addr
        if direction == "dst":
            return pkt.dst_ip == addr
        return pkt.src_ip == addr or pkt.dst_ip == addr
    if kind == "net":
        _k, direction, net = node
        src_in = ipaddress.IPv4Address(pkt.src_ip) in net
        dst_in = ipaddress.IPv4Address(pkt.dst_ip) in net
        if direction == "src":
            return src_in
        if direction == "dst":
            return dst_in
        return src_in or dst_in
    if kind == "port":
        _k, direction, port = node
        if direction == "src":
            return pkt.src_port == port
        if direction == "dst":
            return pkt.dst_port == port
        return pkt.src_port == port or pkt.dst_port == port
    raise ValueError(f"未知节点 {kind}")


def describe(node) -> str:
    kind = node[0]
    if kind in ("and", "or"):
        return f"({describe(node[1])} {kind} {describe(node[2])})"
    if kind == "not":
        return f"not {describe(node[1])}"
    if kind == "proto":
        return node[1]
    if kind == "host":
        return f"{node[1]} host {node[2]}"
    if kind == "net":
        return f"{node[1]} net {node[2]}"
    if kind == "port":
        return f"{node[1]} port {node[2]}"
    return "?"


def sample_packets() -> list:
    return [
        Pkt("PC1 -> 对外 HTTPS", "tcp", "192.0.2.10", "198.51.100.10", 51000, 443),
        Pkt("PC1 -> 办公 SSH", "tcp", "192.0.2.10", "192.0.2.20", 51001, 22),
        Pkt("PC1 -> DNS 查询", "udp", "192.0.2.10", "198.51.100.53", 33000, 53),
        Pkt("PC2 -> DNS 查询", "udp", "192.0.2.11", "198.51.100.53", 33001, 53),
        Pkt("PC1 ping R1", "icmp", "192.0.2.10", "203.0.113.1", 0, 0),
        Pkt("PC1 ARP 请求网关", "arp", "192.0.2.10", "192.0.2.1", 0, 0),
    ]


EXPRESSIONS = [
    "tcp and port 443",
    "host 192.0.2.10 and not tcp",
    "(tcp or udp) and port 53",
    "net 192.0.2.0/24 and dst port 22",
    "icmp or arp",
    "not net 192.0.2.0/24",
]


def run_expression(expr: str, packets: list) -> None:
    print(SUB)
    print(f"表达式: {expr}")
    try:
        tokens = tokenize(expr)
        tree = Parser(tokens).parse()
    except (ValueError, IndexError) as exc:
        print(f"  解析失败: {exc}")
        return
    print(f"  等价树: {describe(tree)}")
    print(SUB)
    print(f"{'报文':<22}{'协议':<7}{'源':<22}{'目的':<22}{'判定'}")
    print(SUB)
    hits = 0
    for pkt in packets:
        ok = evaluate(tree, pkt)
        hits += 1 if ok else 0
        src = f"{pkt.src_ip}:{pkt.src_port}" if pkt.src_port else pkt.src_ip
        dst = f"{pkt.dst_ip}:{pkt.dst_port}" if pkt.dst_port else pkt.dst_ip
        print(f"{pkt.name:<22}{pkt.proto:<7}{src:<22}{dst:<22}"
              f"{'匹配' if ok else '不匹配'}")
    print(SUB)
    print(f">>> 结论：表达式 `{expr}` 命中 {hits} / {len(packets)} 个包")


def main() -> None:
    print(SEP)
    print("BPF 风格过滤表达式引擎（对应 tcpdump 的 libpcap 语法子集）")
    print(SEP)
    print("支持的原语：tcp | udp | icmp | arp | ip | host X | net X/len | port N")
    print("方向限定：src / dst 前缀；逻辑运算：and / or / not（也接受 && || ! 与括号）")
    print()

    packets = sample_packets()
    print(SUB)
    print("示例报文集合")
    print(SUB)
    print(f"{'#':<4}{'说明':<26}{'协议':<7}{'源':<22}{'目的'}")
    print(SUB)
    for i, pkt in enumerate(packets, 1):
        src = f"{pkt.src_ip}:{pkt.src_port}" if pkt.src_port else pkt.src_ip
        dst = f"{pkt.dst_ip}:{pkt.dst_port}" if pkt.dst_port else pkt.dst_ip
        print(f"{i:<4}{pkt.name:<26}{pkt.proto:<7}{src:<22}{dst}")

    for expr in EXPRESSIONS:
        print()
        run_expression(expr, packets)

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. BPF 表达式本质是一棵布尔语法树，and/or/not 是节点，host/net/port/proto 是叶子。")
    print("2. 无方向前缀的 host / port 是「源或目的任一命中」，加了 src/dst 才限定单方向。")
    print("3. 过滤表达式越靠前、越精确，抓包时的内核过滤越省资源——先过滤再落盘。")
    print("4. 同一个表达式可以逐包复现判定过程，这正是 Wireshark 显示过滤器的底层逻辑。")
    print()


if __name__ == "__main__":
    main()
