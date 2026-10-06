#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OSPF LSA 类型/作用域对照表与邻居状态机 7 状态迁移演示。

运行: python3 ospf_lsa_types.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


# (类型, 名称, 生成者, 洪泛范围, 关键内容, 典型用途)
LSAS = [
    ("Type 1", "Router-LSA", "每一台 OSPF 路由器", "本区域",
     "Router-ID、接口列表(类型/开销/邻居)、Flags", "描述自己的链路状态，SPF 的输入"),
    ("Type 2", "Network-LSA", "广播网中的 DR", "本区域",
     "DR 接口掩码、所连接的 Router-ID 清单", "代表多路访问网段这台「伪节点」"),
    ("Type 3", "Summary-LSA", "ABR", "跨区域(除 Totally-Stub)",
     "目的网段 + 掩码 + 累加开销 + 通告者 ABR", "把区域内的网段汇总播给其它区域"),
    ("Type 4", "ASBR-Summary-LSA", "ABR", "跨区域",
     "ASBR 的 Router-ID + 到该 ASBR 的开销", "告诉其它区域「ASBR 在哪、多远」"),
    ("Type 5", "AS-External-LSA", "ASBR", "整个 AS(Stub/NSSA 除外)",
     "外部网段 + 掩码 + 度量类型 E1/E2 + Forwarding Address", "引入 RIP/BGP/静态等外部路由"),
    ("Type 7", "NSSA-External-LSA", "NSSA 内的 ASBR", "只在 NSSA 区域",
     "同 Type 5 的字段结构", "NSSA 里引入外部路由，ABR 再翻译成 Type 5"),
]

# 邻居状态机：(状态, 触发条件/动作, 此时链路状态库状态)
STATES = [
    ("Down", "接口 up 后开始按 HelloInterval 发 Hello，尚未收到任何对端 Hello",
     "只有自己的 Router-LSA"),
    ("Init", "收到对端 Hello，但 Hello 的邻居列表里还没有自己的 Router-ID",
     "同上"),
    ("2-Way", "Hello 双向可见（对端列表里有我），DR 选举在此完成",
     "同上，选举完毕即定型 DR/BDR/DROther"),
    ("ExStart", "协商主从(Master/Slave)，用空的 DBD 比 Router-ID 定序列号",
     "开始交换 LSA 头部摘要"),
    ("Exchange", "互发 DBD(Database Description) 描述各自 LSDB 摘要",
     "收到 LSA 头部列表，比对谁新谁旧"),
    ("Loading", "对 DBD 中缺失/过期的条目发 LSR，对方回 LSU，自己回 LSAck",
     "补齐差异的 LSA，LSDB 趋向一致"),
    ("Full", "双方 LSDB 完全同步，形成完全邻接",
     "LSDB 一致，各自跑 SPF"),
]

# 各状态可用的调试输出（真实设备上会看到什么）
DEBUG_HINT = {
    "Down": "debug ip ospf adj 无任何输出；接口 up 后 0~10s 内就会看到 Hello",
    "Init": "能看到 Received Hello，但 Neighbor list 里没有自己 → 多为单向可达/ACL 拦截",
    "2-Way": "显示 2WAY/DROTHER（DROther 之间）或 2WAY（DR/BDR 之间），属正常稳态",
    "ExStart": "两边 MTU 不一致时会卡在 EXSTART/DR 之间来回翻转",
    "Exchange": "反复 EXCHANGE，通常是对端 LSDB 里有自己不认识的自造 LSA",
    "Loading": "长期 LOADING 说明 LSR/LSU 有去无回，检查过滤或链路质量",
    "Full": "稳态；若在邻居状态里看到 FULL/DR、FULL/BDR、FULL/DROTHER 均为正常",
}


def box(lines, inner):
    """用 pad() 按显示宽度画方框，保证中英混排也不歪。"""
    top = "┌" + "─" * inner + "┐"
    bot = "└" + "─" * inner + "┘"
    body = ["│" + pad(l, inner) + "│" for l in lines]
    return [top] + body + [bot]


def main():
    print()
    print("OSPF LSA 类型与邻居状态机演示 · 单区域/多区域结构对照")
    print()
    print("=" * 96)
    print("一、OSPF 区域结构（LSA 作用域一眼看清）")
    print("-" * 96)
    area0 = box([" 骨干区域 Area 0 (0.0.0.0)", " R1 ────────── R2"], 36)
    area1 = box([" Area 1 (普通区域)", " R3 ── R4", " 内部 LSA: 1 / 2"], 28)
    area2 = box([" Area 2 (NSSA)", " R5 ── R6 (ASBR)", " 内部 LSA: 1 / 2 / 7"], 28)
    indent = " " * 28
    for ln in area0:
        print(indent + ln)
    print(indent + "  │ABR              │ABR")
    for i in range(len(area1)):
        print(" " * 18 + area1[i] + "  " + area2[i])
    print(" " * 18 + "外部 RIP 网段 198.51.100.0/24 由 R6 引入：Type 7 → ABR 翻译成 Type 5")
    print("-" * 96)
    print(">>> 结论：LSA 的作用域是分层设计的。Type 1/2 只在区域内部洪泛；")
    print("    跨区域靠 ABR 产生的 Type 3/4；外部路由靠 ASBR 产生的 Type 5/7。")
    print()

    print("=" * 96)
    print("二、LSA 类型 / 生成者 / 作用域 / 用途")
    print("-" * 96)
    print(pad("类型", 10) + pad("名称", 24) + pad("生成者", 22)
          + pad("洪泛范围", 24) + "作用")
    print("-" * 96)
    for t, name, gen, scope, content, use in LSAS:
        print(pad(t, 10) + pad(name, 24) + pad(gen, 22) + pad(scope, 24) + use)
        print(pad("", 10) + pad("  关键字段", 24) + content)
    print("-" * 96)

    print("=" * 96)
    print("三、LSA 头部公共字段（20 字节，所有 LSA 一致）")
    print("-" * 96)
    fields = [
        ("LS Age", "2 字节", "LSA 年龄，0~3600 秒；到 3600 且未被刷新即被删除"),
        ("Options", "1 字节", "能力位：E=可处理 Type 5，N/P=支持 NSSA 及迁移"),
        ("LS Type", "1 字节", "1/2/3/4/5/7，决定作用域"),
        ("Link State ID", "4 字节", "随类型变：Type 2 为 DR 接口 IP，Type 3 为目的网段"),
        ("Advertising Router", "4 字节", "产生该 LSA 的 Router-ID"),
        ("LS Sequence Number", "4 字节", "从 0x80000001 起，每次重发递增，越大越新"),
        ("LS Checksum", "2 字节", "仅覆盖 LSA 内容，不含 LS Age"),
        ("LS Length", "2 字节", "含 20 字节头部在内的 LSA 总长"),
    ]
    print(pad("字段", 24) + pad("长度", 10) + "作用")
    for f, l, d in fields:
        print(pad(f, 24) + pad(l, 10) + d)
    print("-" * 96)
    print(">>> 结论：比较两个 LSA 新旧的三步顺序是 —— 先比 LS Sequence Number（大者新），")
    print("    再比 LS Checksum（大者新），最后比 LS Age（小时新，差 >900 秒才比较）。")
    print()

    print("=" * 96)
    print("四、邻居状态机：Down → Init → 2-Way → ExStart → Exchange → Loading → Full")
    print("-" * 96)
    print(pad("序号", 6) + pad("状态", 12) + "LSDB / 握手进展")
    print("-" * 96)
    for i, (st, cond, lsdb) in enumerate(STATES, start=1):
        print(pad(str(i), 6) + pad(st, 12) + lsdb)
        print(pad("", 6) + pad("", 12) + "触发：" + cond)
    print("-" * 96)
    print("状态迁移图：")
    print("  Down ──收Hello──> Init ──双向Hello──> 2-Way ──DR选举完成──> ExStart")
    print("    ↑                                                          │")
    print("    │                                                     主从协商")
    print("    │                                                          ↓")
    print("  Full <──LSDB同步── Loading <──LSR/LSU/LSAck── Exchange <──────┘")
    print("  （任何时候收到 Kill 邻居事件 / Dead 计时器超时 → 回到 Down）")
    print("-" * 96)
    print("各状态的排障要点（真实设备上会看到什么）：")
    for st, _, _ in STATES:
        print(pad("  · " + st + ":", 18) + DEBUG_HINT[st])
    print()
    print("卡在中间状态的两大高频根因：")
    print("  1) 卡在 ExStart/Exchange 反复翻转 → 两端接口 MTU 不一致（DBD 协商失败）。")
    print("  2) 长期停留在 Init / 无法到 2-Way → 单向可达，常见于 ACL 放行不完整、")
    print("     或两接口一个配了 OSPF 认证而另一个没配（Hello 被丢弃）。")
    print()
    print("小结：")
    print("1. LSA 按作用域分层：Type 1/2 在区内，Type 3/4 跨区，Type 5 全局，Type 7 限于 NSSA。")
    print("2. 所有 LSA 共用 20 字节头部，比新旧严格按「序列号 → 校验和 → 年龄」三步走。")
    print("3. 邻居要走到 Full 才完全同步 LSDB；卡在 ExStart/Exchange 先怀疑 MTU，卡在 Init 先查单向可达。")
    print()


if __name__ == "__main__":
    main()
