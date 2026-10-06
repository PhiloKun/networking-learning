#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PIM-SM 组播转发树演示：RPT(*,G) 建立 → SPT(S,G) 切换，含 RPF 检查逐跳推演。

运行: python3 multicast_tree.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


GROUP = "239.1.1.1"
SOURCE = "198.51.100.10"          # 源主机，直连 R1
RP = "203.0.113.2"                # 汇合点
RP_NAME = "R2"
LOOPBACK = {"R1": "203.0.113.1", "R2": RP, "R3": "203.0.113.3"}

# 链路开销（教学取值，取自 203.0.113.0/24 骨干网段）
LINKS = [
    ("R1", "R2", 10),
    ("R2", "R3", 10),
    ("R1", "R3", 5),
]

# 每台路由器到「源」与「RP」的单播最短路径下一跳（由上面的链路开销算出）
# 目的 -> 下一跳（"-" 表示直连/自身）
RPF = {
    "R1": {SOURCE: "直连", RP: "R2"},
    "R2": {SOURCE: "R1", RP: "自身"},
    "R3": {SOURCE: "R1", RP: "R2"},
}
# 计算依据：R3→R1 直连开销 5；R3→R2→R1 开销 10+10=20；故 R3 到源走 R1
PATH_COST = {
    ("R3", SOURCE): 5,
    ("R3", RP): 10,
    ("R2", SOURCE): 10,
}


def section(title):
    print("=" * 96)
    print(title)
    print("-" * 96)


def show_state(state):
    print(pad("路由器", 10) + pad("表项", 22) + pad("入接口(RPF)", 22) + "出接口列表")
    for r in ("R1", "R2", "R3"):
        entries = state.get(r, [])
        if not entries:
            print(pad(r, 10) + pad("(无组播表项)", 22) + pad("-", 22) + "-")
            continue
        for i, (entry, inif, outifs) in enumerate(entries):
            name = r if i == 0 else ""
            outs = "、".join(outifs) if outifs else "(空)"
            print(pad(name, 10) + pad(entry, 22) + pad(inif, 22) + outs)


def main():
    print()
    print("PIM-SM 组播转发树演示 · 组 " + GROUP + "，源 " + SOURCE + "，RP = R2(" + RP + ")")
    print()

    section("零、拓扑与单播 RPF 依据")
    print("           源主机 " + SOURCE)
    print("                │")
    print("               R1")
    print("             ╱    ╲   (R1-R3 = 5，捷径)")
    print("      c=10  ╱      ╲  c=5")
    print("           ╱        ╲")
    print("         R2(RP) ─── R3 ── 接收者（加入 " + GROUP + "）")
    print("              c=10")
    print("-" * 96)
    print(pad("起点 → 目的", 34) + pad("最短路径", 26) + "总开销")
    rows = [
        ("R3 → 源 " + SOURCE, "R3 → R2 → R1", "10 + 10 = 20"),
        ("R3 → 源（另一条）", "R3 → R1", "5  ← 更短，SPT 会选它"),
        ("R3 → RP " + RP, "R3 → R2", "10"),
        ("R2 → 源 " + SOURCE, "R2 → R1", "10"),
    ]
    for a, b, c in rows:
        print(pad(a, 34) + pad(b, 26) + c)
    print("-" * 96)
    print(">>> 结论：R3 到 RP 的最短路径是经 R2，但 R3 到「源」的最短路径是经 R1。")
    print("    正是这个差异，让 SPT 切换（R3→R1）比共享树（R3→R2→R1）更短。")
    print()

    state = {}

    section("一、接收者发出 IGMP Join → R3 产生组播成员")
    print("接收主机发送 IGMP v2/v3 Membership Report，目标组 " + GROUP + "。")
    print("R3 在连接接收者的接口上记录该组，形成 (*,G) 表项的雏形。")
    state["R3"] = [("(*, " + GROUP + ")", "接入接口(接收者)", ["等待选定上游"])]
    show_state(state)
    print(">>> 此时还没有任何组播流量，R3 只知道「本地有人要这个组」。")
    print()

    section("二、R3 向 RP 发起 (*,G) Join → 建立共享树 RPT")
    print("步骤：")
    print("  1) R3 对 RP 地址 " + RP + " 做 RPF 检查：查单播路由表，到 RP 的下一跳 = R2。")
    print("  2) R3 把 (R2 方向) 的接口设为 (*,G) 入接口，并向 R2 发送 PIM Join(*, " + GROUP + ")。")
    print("  3) R2 收到 Join，创建 (*,G) 表项：入接口指向 RP 自身（由 Register 补充），")
    print("     出接口指向 R3；R2 再向自己的 RPF 邻居继续 Join，直到到达 RP（自己就是 RP，停止）。")
    state["R3"] = [("(*, " + GROUP + ")", "→ R2 (RPF 到 RP)", ["接收者接口"])]
    state["R2"] = [("(*, " + GROUP + ")", "RP 自身 (Null)", ["→ R3"])]
    show_state(state)
    print("-" * 96)
    print(">>> 共享树（RPT）成型：R2(RP) → R3 → 接收者。树根是 RP，与源位置无关。")
    print()

    section("三、源开始发送 → R1 用 Register 单播封装送到 RP")
    print("源主机向 " + GROUP + " 发送数据，R1 收到后发现自己没有 (S,G) 表项。")
    print("  1) R1 把整个组播报文封装进 PIM Register 报文，单播发给 RP(R2)。")
    print("  2) 报文中带 (S=" + SOURCE + ", G=" + GROUP + ") 信息。")
    print("  3) R2 解封装，若 (*,G) 有出接口，就把组播报文沿 RPT 转发给 R3。")
    state["R1"] = [("(S,G) 注册中", "→ RP (单播 Register)", ["(待建立)"] )]
    show_state(state)
    print(">>> 结论：Register 是「源侧还不知道树」时的临时通道，用单播把首包硬塞给 RP。")
    print()

    section("四、RP 向源发起 (S,G) Join → 建立第一段最短路径树")
    print("步骤：")
    print("  1) R2 对源 " + SOURCE + " 做 RPF 检查：查单播路由表，到源的下一跳 = R1。")
    print("  2) R2 向 R1 发送 PIM Join(S, " + GROUP + ")，建立 (S,G) 表项，入接口 = R1 方向。")
    print("  3) R1 收到 Join，建立 (S,G) 表项，出接口 = R2；此后源流量沿 SPT 到达 RP。")
    print("  4) R2 通过 SPT 收到 (S,G) 数据后，向 R1 发送 Register-Stop，停止单播封装。")
    state["R1"] = [("(S, " + GROUP + ")", "源直连接口", ["→ R2 (RP)"])]
    state["R2"] = [
        ("(*, " + GROUP + ")", "RP 自身 (Null)", ["→ R3"]),
        ("(S, " + GROUP + ")", "→ R1 (RPF 到源)", ["(*,G) 出接口 R3"]),
    ]
    show_state(state)
    print(">>> 结论：RP 到源的这一段已经是 SPT；RP 再把流量「嫁接」到共享树的出接口上。")
    print()

    section("五、R3 发起 (S,G) Join → 从共享树切换到最短路径树")
    print("R3 收到经 RPT 来的流量后（Cisco 默认阈值 0 kbps，立刻切换），执行：")
    print("  1) R3 对源 " + SOURCE + " 做 RPF 检查：查单播路由表，到源的下一跳 = R1")
    print(f"       依据：R3 → R1 直连开销 {PATH_COST[('R3', SOURCE)]}；"
          f"R3 → R2 → R1 绕行开销 10 + 10 = 20；故 RPF 邻居是 R1")
    print("  2) R3 向 R1 发送 PIM Join(S, " + GROUP + ")，形成新的 (S,G) 表项，入接口 = R1 方向。")
    print("  3) R1 的 (S,G) 出接口新增 R3：现在同时有 R2、R3 两个下游。")
    print("  4) 流量改由 R1 直接下发给 R3；R3 等待约 3 秒后向 R2 发送 (S,G) Prune。")
    state["R3"] = [
        ("(*, " + GROUP + ")", "→ R2 (RPF 到 RP)", ["接收者接口"]),
        ("(S, " + GROUP + ")", "→ R1 (RPF 到源)", ["接收者接口"]),
    ]
    state["R1"] = [("(S, " + GROUP + ")", "源直连接口", ["→ R2 (RP)", "→ R3 (SPT)"])]
    show_state(state)
    print()

    section("六、剪枝：R3 从共享树退出，全网收敛到 SPT")
    print("  1) R3 向 R2 发 (S,G) Prune，R2 的 (S,G) 出接口里移除 R3。")
    print("  2) R2 的 (*,G) 已无出接口；若长期无接收者，RP 会向源方向发 (*,G) Prune。")
    print("  3) R3 的 (*,G) 表项在 SPT 数据到达后按超时回收，最终只保留 (S,G)。")
    state["R2"] = [("(*, " + GROUP + ")", "RP 自身 (Null)", [])]
    state["R3"] = [("(S, " + GROUP + ")", "→ R1 (RPF 到源)", ["接收者接口"])]
    show_state(state)
    print("-" * 96)
    print(">>> 最终转发路径：源 → R1 → R3 → 接收者（跳过了 RP R2），")
    print("    这就是 PIM-SM 的「RPT 起步、SPT 收敛」，兼顾了「先通后优」。")
    print()

    section("七、RPF 检查为什么是组播防环的核心")
    print("RPF（Reverse Path Forwarding，反向路径转发）规则只有一条：")
    print("  只有当组播报文从「到源的最短路径接口」进来时，才接受并转发；否则丢弃。")
    print("-" * 96)
    checks = [
        ("R2 收到来自源的报文，单播表到源的下一跳是 R1", "R1 方向", "通过"),
        ("R2 又从 R3 方向收到同一 (S,G) 报文", "R3 方向", "丢弃（非 RPF 接口）"),
        ("R3 收到来自 R1 的 (S,G) 报文，到源的下一跳是 R1", "R1 方向", "通过"),
        ("R3 又从 R2 方向收到同一 (S,G) 报文", "R2 方向", "丢弃（避免 RPT/SPT 双份）"),
    ]
    print(pad("场景", 48) + pad("报文到达接口", 24) + "RPF 结果")
    for a, b, c in checks:
        print(pad(a, 48) + pad(b, 24) + c)
    print("-" * 96)
    print(">>> 结论：组播没有「目的地址」可查表，只能靠「源」来定方向，")
    print("    RPF 因此成为唯一的防环机制；单播路由不对称会让 RPF 失败，")
    print("    表现为「IGMP 收到了、表项也建了，但流量就是不来」——排障先查 `show ip rpf`。")
    print()
    print("小结：")
    print("1. PIM-SM 先用共享树 (*,G) 让流量尽快通起来（根在 RP），再用 (S,G) 最短路径树优化路径。")
    print("2. Register/Register-Stop 解决「源侧不知道树」的过渡问题；Prune 负责剪掉冗余分支。")
    print("3. RPF 检查是组播唯一的防环手段：报文必须从「回源最短路径接口」进来，否则丢弃。")
    print()


if __name__ == "__main__":
    main()
