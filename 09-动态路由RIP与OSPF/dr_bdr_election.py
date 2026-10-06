#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OSPF 广播网络 DR/BDR 选举演示：优先级 → Router-ID 比较、不可抢占、优先级 0。

运行: python3 dr_bdr_election.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


# 广播网段 203.0.113.0/24（教学用），每个 (名字, 优先级, Router-ID, 接口地址)
ROUTERS = [
    ("R1", 1, "203.0.113.1", "203.0.113.1/24"),
    ("R2", 100, "203.0.113.2", "203.0.113.2/24"),
    ("R3", 50, "203.0.113.3", "203.0.113.3/24"),
    ("R4", 0, "203.0.113.4", "203.0.113.4/24"),
    ("R5", 100, "203.0.113.5", "203.0.113.5/24"),
]


def rid_key(rid):
    return tuple(int(x) for x in rid.split("."))


def elect(members):
    """按 (优先级降序, Router-ID 降序) 排序，优先级 0 者不参选。
    返回 (DR, BDR)。"""
    candidates = [r for r in members if r[1] > 0]
    candidates.sort(key=lambda r: (r[1], rid_key(r[2])), reverse=True)
    dr = candidates[0] if len(candidates) >= 1 else None
    bdr = candidates[1] if len(candidates) >= 2 else None
    return dr, bdr


def role_of(r, dr, bdr):
    if dr is not None and r[0] == dr[0]:
        return "DR"
    if bdr is not None and r[0] == bdr[0]:
        return "BDR"
    if r[1] == 0:
        return "DROther(pri0)"
    return "DROther"


def show_network(title, members, dr, bdr, note_lines=()):
    print("-" * 82)
    print(title)
    print(pad("路由器", 10) + pad("优先级", 10) + pad("Router-ID", 20)
          + pad("角色", 16) + "接口地址")
    for r in members:
        print(pad(r[0], 10) + pad(str(r[1]), 10) + pad(r[2], 20)
              + pad(role_of(r, dr, bdr), 16) + r[3])
    names = [r[0] for r in members]
    # 邻接关系：DR/BDR 之间 Full；DROther 只与 DR/BDR 达 Full
    full_pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = members[i], members[j]
            ra, rb = role_of(a, dr, bdr), role_of(b, dr, bdr)
            if "DR" in (ra, rb) or "BDR" in (ra, rb):
                full_pairs.append(f"{names[i]}<->{names[j]}")
    print("Full 邻接关系：" + "  ".join(full_pairs))
    stuck = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = members[i], members[j]
            ra, rb = role_of(a, dr, bdr), role_of(b, dr, bdr)
            if ra.startswith("DROther") and rb.startswith("DROther"):
                stuck.append(f"{names[i]}<->{names[j]}(2-Way)")
    print("保持 2-Way 的关系：" + ("  ".join(stuck) if stuck else "无"))
    for ln in note_lines:
        print("  " + ln)


def main():
    print()
    print("OSPF DR/BDR 选举演示 · 广播网络 203.0.113.0/24")
    print("选举规则：比较接口优先级（大者胜，0 表示不参选）→ 平局比 Router-ID（大者胜）")
    print()

    print("=" * 82)
    print("一、初始选举（所有路由器接口 up，进入 2-Way 后立即选举）")
    dr, bdr = elect(ROUTERS)
    show_network("第一轮：全网同时参与", ROUTERS, dr, bdr, [
        f"DR  = {dr[0]}（优先级 {dr[1]}，Router-ID {dr[2]}）",
        f"BDR = {bdr[0]}（优先级 {bdr[1]}，Router-ID {bdr[2]}）",
        "R2 与 R5 优先级同为 100，平局由 Router-ID 决定：203.0.113.5 > 203.0.113.2 → R5 当 DR。",
        "R4 优先级 0，永不参选 DR/BDR，只能是 DROther。",
    ])
    print(">>> 结论：优先级是第一位判据，Router-ID 只在优先级平局时用来打破僵局。")
    print()

    print("=" * 82)
    print("二、注入一台高优先级新路由器 R6（优先级 200）")
    r6 = ("R6", 200, "203.0.113.6", "203.0.113.6/24")
    members2 = ROUTERS + [r6]
    show_network("R6 加入后的现状（注意：角色没有变化）", members2, dr, bdr, [
        "R6 优先级 200 高于现任 DR(R5=100)，但它仍只是 DROther。",
        "这就是「DR/BDR 不可抢占」：除非现任 DR 失效，否则选举结果保持稳定。",
    ])
    print(">>> 结论：新加入的更高优先级路由器不会抢走 DR，避免每次上电都全网重选举。")
    print("    可用 clear ip ospf process（Cisco）或 reset ospf process（华为）强制重选。")
    print()

    print("=" * 82)
    print("三、现任 DR（R5）失效，触发重新选举")
    members3 = [r for r in members2 if r[0] != "R5"]
    # BDR 直接升为 DR；空出的 BDR 在剩余 DROther 中重选
    new_dr = bdr                                  # R2 由 BDR 升为 DR
    rest = [r for r in members3 if r[0] != new_dr[0]]
    cands = [r for r in rest if r[1] > 0]
    cands.sort(key=lambda r: (r[1], rid_key(r[2])), reverse=True)
    new_bdr = cands[0] if cands else None
    show_network("R5 掉线后：BDR 自动升 DR，再补选一个 BDR", members3, new_dr, new_bdr, [
        f"原 BDR {new_dr[0]} 直接升为 DR（不用重新比较全部，这是 BDR 存在的意义）。",
        f"空出的 BDR 在余下 DROther 中重选：R6(200) > R3(50) > R1(1) → R6 当选 BDR。",
    ])
    print(">>> 结论：BDR 是「热备份」。DR 一倒，BDR 立即接管，网络不用再做一次全量选举。")
    print()

    print("=" * 82)
    print("四、Hello 报文里与选举相关的字段（抓包/display 会看到）")
    print("-" * 82)
    hello = [
        ("Version", "1 字节", "OSPF 版本，IPv4 为 2，IPv6 为 3"),
        ("Type", "1 字节", "报文类型：1=Hello 2=DBD 3=LSR 4=LSU 5=LSAck"),
        ("Packet Length", "2 字节", "整包长度，含 24 字节 OSPF 公共头"),
        ("Router ID", "4 字节", "发送者的 Router-ID，选举平局时用它比大小"),
        ("Area ID", "4 字节", "接口所属区域；两接口区域不同则不建邻接"),
        ("Checksum", "2 字节", "覆盖整个 OSPF 报文（不含 IP 头）"),
        ("AuType / Auth", "8 字节", "认证类型与认证数据：0=无 1=明文 2=MD5"),
        ("Network Mask", "4 字节", "接口掩码；不一致则无法建立邻居（点对点除外）"),
        ("HelloInterval", "2 字节", "默认 10 秒（NBMA/点对点广播为 30 秒）"),
        ("Options", "1 字节", "E/N/DC 等能力位，决定能否处理 5 类/7 类 LSA"),
        ("Rtr Pri", "1 字节", "接口优先级，0~255，默认 1；=0 不参选"),
        ("DeadInterval", "4 字节", "默认 40 秒 = 4 × HelloInterval"),
        ("DR / BDR", "4+4 字节", "发送者认为的 DR、BDR 的接口 IP"),
        ("Neighbor", "变长", "已双向可见的邻居 Router-ID 列表（Init 与 2-Way 的分界线）"),
    ]
    print(pad("字段", 22) + pad("长度", 12) + "作用")
    for f, l, d in hello:
        print(pad(f, 22) + pad(l, 12) + d)
    print("-" * 82)
    print(">>> 结论：HelloInterval 与 DeadInterval 两端必须一致，否则邻居起不来；")
    print("    DR 用组播地址 224.0.0.5（AllSPFRouters）收发，")
    print("    DROther 向 DR/BDR 发 DBD/LSR/LSU 时用 224.0.0.6（AllDRouters）。")
    print()
    print("小结：")
    print("1. 选举顺序为「优先级大者胜 → Router-ID 大者胜」，优先级 0 者永不参选。")
    print("2. DR/BDR 不可抢占：新入网的高优先级路由器不会顶掉现任，除非现任失效或手动 reset。")
    print("3. BDR 是热备；DROther 之间只停留在 2-Way，所有 DROther 只与 DR/BDR 建 Full，")
    print("   邻接数量从 N(N-1)/2 降到 2(N-2)+1，这是 DR 机制存在的根本原因。")
    print()


if __name__ == "__main__":
    main()
