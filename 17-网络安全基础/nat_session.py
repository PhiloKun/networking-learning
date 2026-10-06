#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NAT / PAT 会话表模拟：五元组转换、端口复用上限、超时回收与外部无法主动进入。

运行: python3 nat_session.py
"""
import ipaddress
import sys
from dataclasses import dataclass, field

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

PUBLIC_IP = "203.0.113.5"
INTERNAL_NET = "192.0.2.0/24"
PORT_LOW, PORT_HIGH = 1024, 65535          # PAT 可复用的公网端口池
POOL_SIZE = PORT_HIGH - PORT_LOW + 1


@dataclass
class Session:
    proto: str
    inside_ip: str
    inside_port: int
    outside_ip: str
    outside_port: int
    global_port: int
    idle: int = 0                          # 已空闲秒数
    timeout: int = 300                     # TCP 已建连会话默认 300s 超时
    state: str = "ESTABLISHED"


@dataclass
class PatTable:
    # 会话索引：五元组 -> Session（O(1) 查找，避免线性扫描）
    sessions: dict = field(default_factory=dict)
    # 反向索引：(协议, 外网IP, 外网端口, 公网端口) -> Session
    reverse: dict = field(default_factory=dict)
    used_ports: set = field(default_factory=set)
    recycled: list = field(default_factory=list)   # 超时回收后待复用的端口
    next_port: int = PORT_LOW

    def alloc_port(self) -> int:
        """优先复用已回收端口，否则顺序上新端口；两者皆空返回 -1。"""
        if self.recycled:
            p = self.recycled.pop()
        elif self.next_port <= PORT_HIGH:
            p = self.next_port
            self.next_port += 1
        else:
            return -1
        self.used_ports.add(p)
        return p

    def translate_out(self, proto: str, sip: str, sport: int,
                      dip: str, dport: int) -> tuple:
        """内网 -> 外网方向：命中已有会话则复用端口，否则新建会话。"""
        key = (proto, sip, sport, dip, dport)
        s = self.sessions.get(key)
        if s is not None:
            s.idle = 0
            return (f"{PUBLIC_IP}:{s.global_port}", "复用已有会话")
        gport = self.alloc_port()
        if gport < 0:
            return (None, "端口池耗尽，新建会话失败（丢包）")
        s = Session(proto, sip, sport, dip, dport, gport)
        self.sessions[key] = s
        self.reverse[(proto, dip, dport, gport)] = s
        return (f"{PUBLIC_IP}:{gport}", "新建会话并分配公网端口")

    def translate_in(self, proto: str, src: str, sport: int,
                     dst: str, dport: int) -> tuple:
        """外网 -> 内网方向：只有能匹配到会话反向键的才放行，否则丢弃。"""
        s = self.reverse.get((proto, src, sport, dport))
        if s is not None:
            return (f"{s.inside_ip}:{s.inside_port}", "命中会话反向映射")
        return (None, "无匹配会话，NAT 丢弃（外部主动访问进不来）")

    def age(self, seconds: int) -> list:
        """时间推进：把空闲超时的会话回收，释放公网端口。"""
        expired = []
        for key, s in list(self.sessions.items()):
            s.idle += seconds
            if s.idle >= s.timeout:
                del self.sessions[key]
                self.reverse.pop((s.proto, s.outside_ip, s.outside_port,
                                  s.global_port), None)
                self.used_ports.discard(s.global_port)
                self.recycled.append(s.global_port)
                expired.append(s)
        return expired

    def dump(self, title: str) -> None:
        print(f"\n{title}")
        print(f"{'协议':<6}{'内网五元组':<34}{'公网映射':<24}{'状态':<12}{'空闲(s)'}")
        print(SUB)
        for s in self.sessions.values():
            inside = f"{s.inside_ip}:{s.inside_port} -> {s.outside_ip}:{s.outside_port}"
            mapping = f"{PUBLIC_IP}:{s.global_port}"
            print(f"{s.proto:<6}{inside:<34}{mapping:<24}{s.state:<12}{s.idle}")
        print(f"已占用公网端口数 = {len(self.used_ports)} / {POOL_SIZE}")


def main() -> None:
    print(SEP)
    print(f"PAT（端口地址转换）会话表演示 · 公网地址 {PUBLIC_IP}")
    print(SEP)
    print(f"内网网段 {INTERNAL_NET}（RFC 5737 文档专用）")
    print(f"PAT 公网端口池 = {PORT_LOW} ~ {PORT_HIGH}，共 {POOL_SIZE} 个可复用端口")

    table = PatTable()

    print()
    print(SUB)
    print("【一】内网发起 3 条连接，全部复用同一个公网 IP")
    print(SUB)
    flows = [
        ("TCP", "192.0.2.10", 51000, "198.51.100.10", 443),
        ("TCP", "192.0.2.11", 51000, "198.51.100.10", 443),
        ("UDP", "192.0.2.10", 33000, "198.51.100.53", 53),
    ]
    for proto, sip, sport, dip, dport in flows:
        result, action = table.translate_out(proto, sip, sport, dip, dport)
        print(f"  {sip}:{sport} -> {dip}:{dport}  ==>  {result}   （{action}）")
    table.dump("当前会话表：")
    print(">>> 结论：三台主机的源端口可能相同，但映射到公网后端口互不相同，靠「公网端口」区分会话。")

    print()
    print(SUB)
    print("【二】同一个源端口重复发起相同连接：命中会话、复用端口")
    print(SUB)
    r1, a1 = table.translate_out("TCP", "192.0.2.10", 51000, "198.51.100.10", 443)
    r2, a2 = table.translate_out("TCP", "192.0.2.10", 51000, "198.51.100.11", 443)
    print(f"  相同目的 + 相同源端口 -> {r1} （{a1}）")
    print(f"  不同目的 + 相同源端口 -> {r2} （{a2}）")
    print(">>> 结论：会话用「协议+源+源端口+目的+目的端口」五元组做键，目的不同就是新会话。")

    print()
    print(SUB)
    print("【三】外部主动访问内网（无会话）——数据被丢弃")
    print(SUB)
    inbound = ("TCP", "203.0.113.99", 40000, PUBLIC_IP, 8080)
    result, action = table.translate_in(*inbound)
    print(f"  203.0.113.99:40000 -> {PUBLIC_IP}:8080  ==>  {result}  （{action}）")
    print(">>> 结论：NAT 把公网 IP 后面的内网主机「藏起来」了；外部只有先被动建立会话，回包才能进。")
    print(">>> 这正是「端口映射 / 端口转发」存在的原因：人工在 NAT 上预置一条静态映射。")

    print()
    print(SUB)
    print("【四】端口复用上限：单台内网主机最多占用多少并发会话")
    print(SUB)
    print(f"  单公网 IP 的 PAT 理论上限 = 端口池 {POOL_SIZE} 个")
    host_count = POOL_SIZE // 1200
    print("  若每台内网主机按 1200 个并发连接估算：")
    print(f"    {POOL_SIZE} / 1200 = {host_count} 台主机（之后新连接会因端口/内存耗尽失败）")
    small = PatTable()
    consumed = 0
    while consumed <= POOL_SIZE:
        r, a = small.translate_out("TCP", "192.0.2.99", 20000 + consumed,
                                   "198.51.100.10", 443)
        if r is None:
            break
        consumed += 1
    print(f"  实测：循环新建直到分配失败，共建立 {consumed} 条会话后被拒绝（{a}）")
    print(">>> 结论：PAT 的端口池是硬上限，大规模 NAT 出口必须监控端口占用率。")

    print()
    print(SUB)
    print("【五】超时回收：会话空闲超时后释放公网端口")
    print(SUB)
    table.age(299)
    print("  推进 299 秒（未超时）：")
    print(f"    会话数 = {len(table.sessions)}")
    expired = table.age(1)
    print("  再推进 1 秒（累计 300 秒，达到 TCP 300s 超时）：")
    for s in expired:
        print(f"    回收 {s.inside_ip}:{s.inside_port} -> {s.outside_ip}:{s.outside_port}"
              f"，释放公网端口 {s.global_port}")
    print(f"    剩余会话数 = {len(table.sessions)}")
    print(">>> 结论：长连接被静默掐断常见原因就是 NAT 表项超时早于应用心跳周期。")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. PAT 用「公网 IP + 端口」区分不同内网会话，一个公网 IP 理论上限约 6.4 万条会话。")
    print("2. 会话键是五元组，同一源端口访问不同目的地会各建一条独立会话。")
    print("3. 外部主动访问内网因缺少会话映射而被丢弃，需靠静态端口映射 / 反向连接解决。")
    print("4. 会话表有超时回收机制（TCP 常见 300s），超时早于应用心跳会导致连接被静默重置。")
    print()


if __name__ == "__main__":
    main()
