#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""链路聚合（LACP）哈希算法对比：源 MAC / 源+目的 MAC / 五元组 的分布均衡度。"""
import sys
import hashlib
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 84
SUB = "-" * 84
N_LINKS = 8

# 五元组：(源 MAC, 目的 MAC, 源 IP, 目的 IP, 目的端口)
FLOWS = [
    ("02:00:00:00:00:0A", "02:00:00:00:00:0B", "192.0.2.10", "198.51.100.10", 443),
    ("02:00:00:00:00:0A", "02:00:00:00:00:0B", "192.0.2.10", "198.51.100.10", 80),
    ("02:00:00:00:00:0A", "02:00:00:00:00:0C", "192.0.2.10", "198.51.100.11", 443),
    ("02:00:00:00:00:0A", "02:00:00:00:00:0C", "192.0.2.10", "198.51.100.11", 22),
    ("02:00:00:00:00:0B", "02:00:00:00:00:0A", "192.0.2.11", "198.51.100.10", 443),
    ("02:00:00:00:00:0B", "02:00:00:00:00:0A", "192.0.2.11", "198.51.100.10", 3306),
    ("02:00:00:00:00:0B", "02:00:00:00:00:0D", "192.0.2.11", "198.51.100.12", 8080),
    ("02:00:00:00:00:0C", "02:00:00:00:00:0D", "192.0.2.12", "198.51.100.12", 443),
    ("02:00:00:00:00:0C", "02:00:00:00:00:0E", "192.0.2.12", "198.51.100.13", 53),
    ("02:00:00:00:00:0D", "02:00:00:00:00:0E", "192.0.2.13", "198.51.100.13", 443),
    ("02:00:00:00:00:0D", "02:00:00:00:00:0F", "192.0.2.13", "198.51.100.14", 3389),
    ("02:00:00:00:00:0E", "02:00:00:00:00:0F", "192.0.2.14", "198.51.100.14", 443),
    ("02:00:00:00:00:0E", "02:00:00:00:00:0A", "192.0.2.14", "198.51.100.10", 123),
    ("02:00:00:00:00:0F", "02:00:00:00:00:0B", "192.0.2.15", "198.51.100.11", 443),
    ("02:00:00:00:00:0F", "02:00:00:00:00:0C", "192.0.2.15", "198.51.100.12", 80),
    ("02:00:00:00:00:0A", "02:00:00:00:00:0E", "192.0.2.10", "198.51.100.13", 443),
]


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def h(key: str) -> int:
    return int.from_bytes(hashlib.md5(key.encode("utf-8")).digest()[:4], "big")


def hash_link(flow: tuple, scheme: str) -> int:
    src_mac, dst_mac, src_ip, dst_ip, dport = flow
    if scheme == "src_mac":
        key = src_mac
    elif scheme == "mac_pair":
        key = f"{src_mac}|{dst_mac}"
    else:
        key = f"{src_mac}|{dst_mac}|{src_ip}|{dst_ip}|{dport}"
    return h(key) % N_LINKS + 1


def distribution(scheme: str) -> tuple[list[int], dict]:
    counts = {i: 0 for i in range(1, N_LINKS + 1)}
    mapping = {}
    for flow in FLOWS:
        link = hash_link(flow, scheme)
        counts[link] += 1
        mapping[flow] = link
    return [counts[i] for i in range(1, N_LINKS + 1)], mapping


def stats(counts: list[int]) -> tuple[float, float, float]:
    n = len(counts)
    mean = sum(counts) / n
    var = sum((c - mean) ** 2 for c in counts) / n
    return mean, var ** 0.5, (1 - (var ** 0.5) / mean) * 100 if mean else 0.0


def main() -> None:
    print(SEP)
    print("链路聚合哈希算法对比 · 8 条成员链路")
    print(SEP)
    print(f"成员链路：8 条（如 Eth-Trunk 的 8 个成员口），流数 = {len(FLOWS)}")
    print("哈希方式：源 MAC / 源+目的 MAC / 五元组，结果对 8 取模决定走哪条成员链路")
    print()

    print(SUB)
    print("【一】三条流的哈希落点明细（节选前 8 条）")
    print(SUB)
    print(pad("源 MAC", 22) + pad("目的 MAC", 22) + pad("目的端口", 10, True)
          + pad("源MAC", 8, True) + pad("MAC对", 8, True) + pad("五元组", 8, True))
    print(SUB)
    _, m1 = distribution("src_mac")
    _, m2 = distribution("mac_pair")
    _, m3 = distribution("five_tuple")
    for flow in FLOWS[:8]:
        sm, dm, _si, _di, dp = flow
        print(pad(sm, 22) + pad(dm, 22) + pad(str(dp), 10, True)
              + pad(f"L{m1[flow]}", 8, True) + pad(f"L{m2[flow]}", 8, True)
              + pad(f"L{m3[flow]}", 8, True))
    print(SUB)
    print()

    print(SUB)
    print("【二】各成员链路上的流数量分布")
    print(SUB)
    print(pad("链路", 8) + pad("源 MAC", 10, True) + pad("源+目的 MAC", 14, True)
          + pad("五元组", 10, True) + "   分布示意（五元组）")
    print(SUB)
    c1, _ = distribution("src_mac")
    c2, _ = distribution("mac_pair")
    c3, _ = distribution("five_tuple")
    for i in range(N_LINKS):
        bar = "#" * c3[i]
        print(pad(f"L{i + 1}", 8) + pad(str(c1[i]), 10, True) + pad(str(c2[i]), 14, True)
              + pad(str(c3[i]), 10, True) + "   " + bar)
    print(SUB)
    print()

    print(SUB)
    print("【三】均衡度指标（越接近 100% 越均匀）")
    print(SUB)
    print(pad("哈希方式", 16) + pad("总流数", 10, True) + pad("最多链路", 12, True)
          + pad("最少链路", 12, True) + pad("标准差", 12, True) + pad("均衡度", 12, True))
    print(SUB)
    for label, counts in [("源 MAC", c1), ("源+目的 MAC", c2), ("五元组", c3)]:
        mean, std, bal = stats(counts)
        print(pad(label, 16) + pad(str(sum(counts)), 10, True)
              + pad(str(max(counts)), 12, True) + pad(str(min(counts)), 12, True)
              + pad(f"{std:.3f}", 12, True) + pad(f"{bal:.1f}%", 12, True))
    print(SUB)
    print(">>> 参与哈希的字段越多，不同流被打散到不同链路的概率越高，分布越均衡。")
    print()

    print(SUB)
    print("【四】为什么单条会话跑不满聚合带宽")
    print(SUB)
    single = FLOWS[0]
    l1 = hash_link(single, "src_mac")
    l2 = hash_link(single, "mac_pair")
    l3 = hash_link(single, "five_tuple")
    print(f"单条会话五元组：{single[0]} -> {single[1]}  "
          f"{single[2]}:* -> {single[3]}:{single[4]}")
    print(f"  源 MAC 哈希      落点：L{l1}（固定）")
    print(f"  源+目的 MAC 哈希 落点：L{l2}（固定）")
    print(f"  五元组哈希       落点：L{l3}（固定）")
    print(">>> 同一条会话的所有报文五元组完全相同，哈希结果恒定，只能走 1 条链路。")
    print(f">>> 因此单会话上限 = 总带宽 / 成员数 = 1/{N_LINKS}，即最多约 "
          f"{100 / N_LINKS:.1f}% 的聚合带宽。")
    print(">>> 厂商哈希通常固定为「源 IP + 目的 IP + 协议」或含端口，")
    print("    同一 TCP 连接不加端口信息时无法被拆到多条链路上。")
    print()

    print(SUB)
    print("【五】工程结论")
    print(SUB)
    print(f"{'现象':<34}{'原因':<34}规避")
    print(SUB)
    rows = [
        ("大文件传输只跑到 1/8 带宽", "单条 TCP 流哈希固定到一条链路", "多并发流 / 用支持逐包分流的设备"),
        ("聚合后流量仍不均", "哈希字段少（仅源 MAC）", "改用五元组哈希"),
        ("部分成员口长期空闲", "流数太少，取模分布稀疏", "增加并发会话数"),
        ("同一对设备流量集中", "源+目的对固定", "引入端口维度或调整哈希策略"),
    ]
    for a, b, c in rows:
        print(pad(a, 34) + pad(b, 34) + c)
    print(SUB)
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. 8 条成员链路下，单条五元组会话的哈希落点固定，最多只能用 1/{N_LINKS} 带宽。")
    print(f"2. 均衡度：源 MAC 哈希 {stats(c1)[2]:.1f}%，源+目的 MAC {stats(c2)[2]:.1f}%，"
          f"五元组 {stats(c3)[2]:.1f}%。")
    print("3. 哈希字段越多分布越均匀，但仍有随机偏差，流数少时无法保证完全均衡。")
    print("4. 链路聚合解决的是「多流并发」的总带宽与冗余，不是「单流提速」；单流提速要靠多路径。")
    print()


if __name__ == "__main__":
    main()
