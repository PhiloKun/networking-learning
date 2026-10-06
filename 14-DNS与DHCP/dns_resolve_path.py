#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟 DNS 递归/迭代解析全过程：本地缓存 → 递归解析器 → 根 → TLD → 权威。

运行: python3 dns_resolve_path.py
（纯逻辑模拟，不发起任何真实 DNS 查询）
"""
import sys

sys.dont_write_bytecode = True


class Cache:
    """带 TTL 的缓存：key=(name, type)，value=(answer, expire_at)。"""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], tuple[str, int]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, now: int, name: str, rtype: str) -> str | None:
        key = (name, rtype)
        if key in self.store:
            answer, expire = self.store[key]
            if now < expire:
                self.hits += 1
                return answer
            del self.store[key]          # 过期删除
        self.misses += 1
        return None

    def put(self, now: int, name: str, rtype: str, answer: str, ttl: int) -> None:
        self.store[(name, rtype)] = (answer, now + ttl)


ROOT_SERVERS = [
    ("a.root-servers.net", "198.41.0.4"),
    ("b.root-servers.net", "170.247.170.2"),
    ("c.root-servers.net", "192.33.4.12"),
    ("d.root-servers.net", "199.7.91.13"),
]
TLD = ("a.gtld-servers.net", "192.5.6.30")
AUTH = ("ns1.example.com", "203.0.113.53")
FINAL_A = "198.51.100.10"
FINAL_TTL = 300


def iterative_resolve(now: int, name: str, log: list[str]) -> str:
    """模拟递归解析器向各级权威做迭代查询，返回最终 A 记录。"""
    log.append("递归解析器缓存未命中，开始迭代查询（从根开始）")
    log.append("  [根] 向 %s(%s) 查询 %s A  -> 返回 NS a.gtld-servers.net（.com 授权）"
               % (ROOT_SERVERS[0][0], ROOT_SERVERS[0][1], name))
    log.append("  [TLD] 向 %s(%s) 查询 %s A -> 返回 NS ns1.example.com（example.com 授权）"
               % (TLD[0], TLD[1], name))
    log.append("  [权威] 向 %s(%s) 查询 %s A -> 返回 A %s TTL=%d"
               % (AUTH[0], AUTH[1], name, FINAL_A, FINAL_TTL))
    return FINAL_A


def query(now: int, client_cache: Cache, resolver_cache: Cache,
          name: str, log: list[str]) -> str:
    """完整解析一次，打印每一步。"""
    log.append("t=%-4d 客户端查询 %s A" % (now, name))
    hit = client_cache.get(now, name, "A")
    if hit is not None:
        log.append("  ├─ 本地缓存命中，直接返回 %s（不发任何网络报文）" % hit)
        return hit
    log.append("  ├─ 本地缓存未命中 -> 向递归解析器 198.51.100.53 发查询（RD=1，目的端口 53/UDP）")
    rhit = resolver_cache.get(now, name, "A")
    if rhit is not None:
        log.append("  └─ 递归解析器缓存命中 -> 返回 %s（客户端仍经历 1 个 RTT）" % rhit)
        client_cache.put(now, name, "A", rhit, FINAL_TTL)
        return rhit
    answer = iterative_resolve(now, name, log)
    resolver_cache.put(now, name, "A", answer, FINAL_TTL)
    client_cache.put(now, name, "A", answer, FINAL_TTL)
    log.append("  └─ 递归解析器把结果缓存 TTL=%d 后返回客户端（RA=1）" % FINAL_TTL)
    return answer


def main() -> None:
    print("=" * 72)
    print("DNS 解析路径模拟（本地缓存 → 递归解析器 → 根 → TLD → 权威）")
    print("=" * 72)

    print("\n[1] 全局域名服务器层次")
    print("  根域：全球 13 组根服务器（a~m.root-servers.net，IPv4 地址任播部署到各地）")
    for host, ip in ROOT_SERVERS:
        print("    · %-22s %s   （仅列 4 组示意，实际 13 组）" % (host, ip))
    print("  ├─ TLD 层：.com 由 a.gtld-servers.net 等负责")
    print("  └─ 权威层：example.com 由 ns1.example.com 负责")
    print("  说明：客户端只把查询交给「递归解析器」，其余层级由解析器自己做「迭代」查询。")

    print("\n[2] 首次解析 www.example.com（全 miss，走完整链路）")
    client_cache = Cache()
    resolver_cache = Cache()
    log: list[str] = []
    ans = query(600, client_cache, resolver_cache, "www.example.com", log)
    for line in log:
        print("    " + line)
    print("    >>> 最终解析结果：www.example.com -> %s" % ans)

    print("\n[3] 3 秒后再次解析（客户端缓存命中，TTL 未到）")
    log = []
    ans = query(603, client_cache, resolver_cache, "www.example.com", log)
    for line in log:
        print("    " + line)

    print("\n[4] TTL 老化：t=920 时客户端缓存已过期（600+300=900），但解析器缓存也过期")
    log = []
    ans = query(920, client_cache, resolver_cache, "www.example.com", log)
    for line in log:
        print("    " + line)

    print("\n[5] 缓存命中率统计")

    def rate(c: Cache) -> float:
        total = c.hits + c.misses
        return (c.hits / total * 100) if total else 0.0

    print("    客户端缓存：命中 %d 次 / 未命中 %d 次 -> 命中率 %.1f%%"
          % (client_cache.hits, client_cache.misses, rate(client_cache)))
    print("    解析器缓存：命中 %d 次 / 未命中 %d 次 -> 命中率 %.1f%%"
          % (resolver_cache.hits, resolver_cache.misses, rate(resolver_cache)))
    print(">>> 结论：TTL 越长命中率越高、越省权威服务器负载；TTL 越短故障切换越快但查询量上升。")

    print("\n[6] 记录类型分工（同一域名可同时存在多条不同类型记录）")
    records = [
        ("www.example.com", "A", "198.51.100.10", "IPv4 地址"),
        ("www.example.com", "AAAA", "2001:db8::10", "IPv6 地址"),
        ("example.com", "MX", "10 mail.example.com", "邮件服务器与优先级"),
        ("example.com", "TXT", '"v=spf1 -all"', "SPF 等文本策略"),
        ("example.com", "CAA", '0 issue "letsencrypt.org"', "限制可签发证书的 CA"),
        ("example.com", "NS", "ns1.example.com", "权威服务器"),
        ("1.100.51.198.in-addr.arpa", "PTR", "www.example.com", "反向解析"),
    ]
    print("    %-32s %-6s %-26s %s" % ("名称", "类型", "值", "用途"))
    print("    " + "-" * 82)
    for n, t, v, u in records:
        print("    %-32s %-6s %-26s %s" % (n, t, v, u))

    print("\n" + "=" * 72)
    print("小结")
    print("-" * 72)
    print("1. 客户端与递归解析器之间是「递归」关系（RD=1），解析器与各级权威之间是「迭代」关系。")
    print("2. 一次冷解析要经历 根 -> TLD -> 权威 至少 3 次网络往返；缓存命中则 0 次。")
    print("3. TTL 决定缓存有效期，是「降低负载」与「故障切换速度」之间的权衡旋钮。")
    print("4. A/AAAA 给地址，CNAME 做别名，MX/TXT/CAA/NS/PTR/SRV 各司其职，同名可多类型并存。")


if __name__ == "__main__":
    main()
