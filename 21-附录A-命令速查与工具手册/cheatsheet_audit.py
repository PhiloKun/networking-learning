#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""速查表自检工具：校验 README.md 的结构完整性与关键数据条目的覆盖率。

检查四项：
  1) 结构   —— 二级 / 三级小节是否齐全，每个小节是否都有命令块或表格
  2) 关键数据 —— 端口、协议号、类型码、保留地址、掩码、EtherType 等硬数据是否齐备
  3) 规模   —— 字节数、代码块数、表格行数、命令条目数
  4) 交叉引用 —— 指向其它章节的相对链接是否指向真实存在的目录

运行: python3 cheatsheet_audit.py
"""
import os
import re
import sys

sys.dont_write_bytecode = True

README = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (分类, 必须出现的关键字, 该项代表什么)
KEY_ITEMS = [
    ("常用端口", "443", "HTTPS"),
    ("常用端口", "22", "SSH"),
    ("常用端口", "53", "DNS"),
    ("常用端口", "179", "BGP"),
    ("常用端口", "3389", "RDP"),
    ("常用端口", "6379", "Redis"),
    ("常用端口", "27017", "MongoDB"),
    ("常用端口", "4789", "VXLAN"),
    ("协议号", "OSPF", "协议号 89 的说明"),
    ("协议号", "VRRP", "协议号 112 的说明"),
    ("协议号", "ICMPv6", "协议号 58 的说明"),
    ("ICMP 类型码", "Time Exceeded", "type 11，traceroute 依赖它"),
    ("ICMP 类型码", "Neighbor Solicitation", "type 135，NDP 的基础"),
    ("ICMP 类型码", "Destination Unreachable", "type 3，排障最常看"),
    ("保留地址", "192.0.2.0/24", "TEST-NET-1"),
    ("保留地址", "198.51.100.0/24", "TEST-NET-2"),
    ("保留地址", "203.0.113.0/24", "TEST-NET-3"),
    ("保留地址", "100.64.0.0/10", "CGNAT"),
    ("IPv6 前缀", "2001:db8::/32", "文档专用前缀"),
    ("IPv6 前缀", "fe80::/10", "链路本地地址"),
    ("IPv6 前缀", "ff02::1:ff00:0/104", "请求节点组播"),
    ("掩码表", "255.255.255.192", "/26 的掩码"),
    ("掩码表", "255.255.255.252", "/30 的掩码"),
    ("掩码表", "255.255.255.255", "/32 的掩码"),
    ("EtherType", "0x8100", "802.1Q VLAN 标签"),
    ("EtherType", "0x86DD", "IPv6"),
    ("EtherType", "0x0806", "ARP"),
    ("线序", "白橙", "T568B 第 1 芯"),
    ("线序", "白绿", "T568A 第 1 芯"),
    ("过滤器", "tcp.analysis.retransmission", "Wireshark 重传过滤器"),
    ("过滤器", "tcp.flags.syn", "Wireshark 握手过滤器"),
]

REQUIRED_SECTIONS = [
    "怎么用这份速查表",
    "主机侧命令总表",
    "设备侧命令对照",
    "显示过滤器速查",
    "捕获过滤器",
    "常用端口与服务表",
    "IP 协议号",
    "ICMP 类型与代码表",
    "IPv4 保留与私有地址表",
    "IPv6 地址类型",
    "双绞线线序",
    "子网掩码速查表",
    "以太网类型字段",
    "常见故障与首要命令",
    "本章示例索引",
]

OK, BAD, WARN, DIM, END = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def main() -> int:
    if not os.path.isfile(README):
        print(f"{BAD}找不到 {README}{END}")
        return 1
    with open(README, "r", encoding="utf-8") as fh:
        text = fh.read()
    lines = text.splitlines()

    print("=" * 92)
    print("  附录 A 速查表自检  ·  结构 / 关键数据 / 规模 / 交叉引用")
    print("=" * 92)
    print()

    problems, warns = [], []

    # ---------- 1. 结构 ----------
    h2 = [ln for ln in lines if ln.startswith("## ")]
    h3 = [ln for ln in lines if ln.startswith("### ")]

    # 把文档按标题切成小节，逐节检查是否含代码块或表格
    sections, cur = [], None
    for ln in lines:
        if ln.startswith("## ") or ln.startswith("### "):
            if cur:
                sections.append(cur)
            cur = {"title": ln.lstrip("# ").strip(), "body": [], "level": ln.count("#")}
        elif cur is not None:
            cur["body"].append(ln)
    if cur:
        sections.append(cur)

    # 标记「容器小节」：二级小节下面若还挂了三级小节，内容分散在子节里，
    # 此时不要求它自己携带代码块或表格（例如「二、主机侧命令总表」）。
    container = set()
    for i, sec in enumerate(sections):
        if sec["level"] != 2:
            continue
        for nxt in sections[i + 1:]:
            if nxt["level"] <= 2:
                break
            if nxt["level"] == 3:
                container.add(id(sec))
                break

    empty_sections, checked = [], 0
    for sec in sections:
        if id(sec) in container:
            continue
        checked += 1
        body = "\n".join(sec["body"])
        has_code = "```" in body
        has_table = any(bl.strip().startswith("|") for bl in sec["body"])
        if not (has_code or has_table):
            empty_sections.append(sec["title"])
        if has_code and body.count("```") % 2 != 0:
            problems.append(f"小节「{sec['title']}」的代码块围栏数量为奇数，存在未闭合的 ```")
    if empty_sections:
        problems.append("以下小节既没有命令块也没有表格，内容可能缺失：" + "、".join(empty_sections))

    missing_sections = [s for s in REQUIRED_SECTIONS if s not in text]
    if missing_sections:
        problems.append("缺少必需小节：" + "、".join(missing_sections))

    print(f"  [1/4] 结构检查 …… 二级小节 {len(h2)} 个、三级小节 {len(h3)} 个、"
          f"共 {len(sections)} 个标题块（其中 {len(sections) - checked} 个为分组容器）")
    print(f"        必需小节：{len(REQUIRED_SECTIONS) - len(missing_sections)}/{len(REQUIRED_SECTIONS)} 齐备")
    print()

    # ---------- 2. 关键数据 ----------
    missing_keys = [(cat, token, why) for cat, token, why in KEY_ITEMS if token not in text]
    hit = len(KEY_ITEMS) - len(missing_keys)
    print(f"  [2/4] 关键数据 …… {hit}/{len(KEY_ITEMS)} 项命中")
    for cat, token, why in missing_keys:
        warns.append(f"缺少数据项 [{cat}] {token}（{why}）")
    print()

    # ---------- 3. 规模 ----------
    code_blocks = text.count("```") // 2
    table_rows = sum(1 for ln in lines if ln.strip().startswith("|"))
    size = os.path.getsize(README)
    # 命令条目：以 # 开头的注释行 + 独立的命令行（粗估）
    comment_cmds = sum(1 for ln in lines if re.match(r"^\s*(sudo\s+)?[a-z][\w\-]*\s", ln)
                       and not ln.startswith(("    ", "|")))
    print(f"  [3/4] 规模统计 …… 笔记 {size / 1024:.1f} KB ｜ 代码块 {code_blocks} 个 ｜ "
          f"表格行 {table_rows} 行 ｜ 命令行 {comment_cmds} 条")
    if size < 9000:
        problems.append(f"README 仅 {size} 字节，低于 9000 字节下限")
    print()

    # ---------- 4. 交叉引用 ----------
    links = re.findall(r"\]\((\.\./[^)#]+)/README\.md\)", text)
    bad_links = []
    for link in sorted(set(links)):
        target = os.path.normpath(os.path.join(os.path.dirname(README), link))
        if not os.path.isdir(target):
            bad_links.append(link)
    print(f"  [4/4] 交叉引用 …… 指向其它章节的链接 {len(set(links))} 个，无效 {len(bad_links)} 个")
    for link in bad_links:
        problems.append(f"交叉引用指向不存在的目录：{link}")
    print()

    # ---------- 汇总 ----------
    if warns:
        print(f"{WARN}提示（不阻断）：{END}")
        for w in warns:
            print(f"  · {w}")
        print()
    if problems:
        print(f"{BAD}失败明细（{len(problems)} 项）：{END}")
        for p in problems:
            print(f"  ✗ {p}")
        print()

    print("=" * 92)
    print("【小结】")
    print(f"  1. 结构：{checked - len(empty_sections)}/{checked} 个内容小节通过检查"
          f"（每个都带命令块或速查表），另有 {len(sections) - checked} 个二级小节仅作分组。")
    print(f"  2. 数据：{hit}/{len(KEY_ITEMS)} 项关键数据命中，"
          f"覆盖端口、协议号、ICMP 类型、保留地址、掩码、EtherType、线序、过滤器八类。")
    print(f"  3. 规模：{size / 1024:.1f} KB / {code_blocks} 个代码块 / {table_rows} 行表格，"
          f"可直接作为日常查阅手册。")
    print("  4. 这份速查表不是用来背的——遇到问题先定位到「哪一层」和「什么症状」，"
          "再回来查对应小节的命令。")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
