#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学习路径规划器：按目标画像输出推荐学习顺序、里程碑与时间规划。

运行:
    python3 learning_path_planner.py           # 默认 ops（网络运维）
    python3 learning_path_planner.py dev       # 网络开发 / 后端
    python3 learning_path_planner.py cert      # 认证考试
    python3 learning_path_planner.py --graph   # 只打印章节依赖图
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

# ---------------------------------------------------------------- 数据表
# (章号, 标题, 难度 1-3, 投入小时, 前置章号元组, (ops, dev, cert) 优先级)
# 优先级: core=核心(精读) / imp=重要(读懂) / opt=选修(略读)
CHAPTERS = [
    ("00", "学习路线与知识地图", 1, 0.5, (), ("core", "core", "core")),
    ("01", "网络概论与分层模型", 1, 3, (), ("core", "core", "core")),
    ("02", "物理层与传输介质", 2, 4, ("01",), ("core", "imp", "core")),
    ("03", "数据链路层原理", 2, 5, ("01",), ("core", "opt", "core")),
    ("04", "以太网与交换技术", 2, 8, ("03",), ("core", "opt", "core")),
    ("05", "无线局域网 WLAN", 2, 5, ("04",), ("core", "opt", "imp")),
    ("06", "IPv4 地址与子网划分", 2, 8, ("01",), ("core", "core", "core")),
    ("07", "IPv6 与过渡技术", 2, 5, ("06",), ("core", "core", "core")),
    ("08", "路由基础与静态路由", 2, 6, ("06",), ("core", "core", "core")),
    ("09", "动态路由 RIP 与 OSPF", 3, 12, ("08",), ("core", "opt", "core")),
    ("10", "动态路由 IS-IS 与 BGP", 3, 14, ("09",), ("imp", "opt", "core")),
    ("11", "网关冗余与组播", 3, 6, ("08",), ("imp", "opt", "core")),
    ("12", "TCP 协议详解", 3, 12, ("06",), ("core", "core", "core")),
    ("13", "UDP、QUIC 与套接字", 2, 8, ("12",), ("imp", "core", "opt")),
    ("14", "DNS 与 DHCP", 2, 6, ("13",), ("imp", "core", "imp")),
    ("15", "HTTP 与 Web 协议栈", 2, 8, ("12",), ("imp", "core", "opt")),
    ("16", "运维类应用协议", 2, 6, ("13",), ("imp", "core", "imp")),
    ("17", "网络安全基础", 3, 10, ("04", "06"), ("core", "imp", "core")),
    ("18", "网络排障与抓包分析", 3, 10, ("12", "17"), ("core", "imp", "core")),
    ("19", "网络自动化与可编程网络", 3, 8, ("04", "09"), ("opt", "imp", "opt")),
    ("20", "网络虚拟化与云网络", 3, 10, ("08", "12"), ("opt", "core", "opt")),
    ("21", "附录A · 命令速查与工具手册", 1, 2, (), ("core", "imp", "core")),
    ("22", "附录B · 故障案例与排障决策树", 2, 8, ("18",), ("core", "imp", "core")),
]

ROUTES = {
    "ops": ("网络运维工程师", 0, "独立维护园区网/数据中心的连通性、排查故障、做变更"),
    "dev": ("网络开发 / 后端", 1, "写好后端服务、看懂网络对性能的影响、定位线上网络问题"),
    "cert": ("认证考试（HCIA/HCIP/HCIE、CCNA/CCNP/CCIE）", 2, "覆盖考纲全部知识点，且理解得比考纲更深"),
}

MILESTONES = [
    ("阶段一 · 建立视角", ["01", "02"],
     ["能否默画一次完整的「封装 → 发送 → 解封装」流程？",
      "能否算出给定带宽与信噪比下的理论极限速率？"]),
    ("阶段二 · 局域网内部", ["03", "04", "05"],
     ["能否说出 Access 口与 Trunk 口收发帧时 802.1Q 标签的增删规则？",
      "能否手算一次 CRC 的模 2 除法余数？"]),
    ("阶段三 · 跨网段转发", ["06", "07", "08", "09", "10", "11"],
     ["能否在 30 秒内心算一个 /26 网段的地址范围？",
      "能否不看书列出 BGP 选路的前 5 条比较规则？"]),
    ("阶段四 · 端到端通信", ["12", "13", "14", "15", "16"],
     ["能否从一个抓包文件里指出三次握手、重传与零窗口？",
      "能否手工构造一个合法的 DNS 查询报文？"]),
    ("阶段五 · 安全与工程实践", ["17", "18", "19", "20"],
     ["能否独立完成一次「跨 VLAN 不通」的排障并写出报告？",
      "能否算出 VXLAN 封装在物理 MTU 1500 下的可用载荷？"]),
]

DEP_GRAPH = r"""
    00 学习路线
     │
     ├─▶ 01 网络概论与分层模型 ────┬─▶ 02 物理层与传输介质
     │                            │
     │                            ├─▶ 03 数据链路层原理 ─▶ 04 以太网与交换 ─▶ 05 无线 WLAN
     │                            │
     │                            ├─▶ 06 IPv4 与子网划分 ─┬─▶ 07 IPv6 与过渡技术
     │                            │                       │
     │                            │                       └─▶ 08 路由基础与静态路由
     │                            │                                │
     │                            │        ┌───────────────────────┼──────────────────────┐
     │                            │        ▼                       ▼                      ▼
     │                            │   09 RIP 与 OSPF        11 网关冗余与组播      12 TCP 协议详解
     │                            │        │                                              │
     │                            │        ▼                                              ├─▶ 13 UDP/QUIC
     │                            │   10 IS-IS 与 BGP                                    ├─▶ 14 DNS 与 DHCP
     │                            │                                                      └─▶ 15 HTTP 与 Web
     │                            │                                                            │
     │                            └────────────────────────────────────────────────────────────┤
     │                                                                                         ▼
     │                                   17 网络安全 ─▶ 18 排障与抓包 ─▶ 22 故障案例与决策树
     │                                        ▲                        ▲
     └────────────────────────────────────────┴── 19 自动化 / 20 云网络（可选）── 16 运维协议
                                                   21 命令速查（随查随用）
"""

LEVEL_LABEL = {"core": "核心 精读", "imp": "重要 读懂", "opt": "选修 略读"}
LEVEL_MARK = {"core": "[**]", "imp": "[ *]", "opt": "[  ]"}
STARS = {1: "★☆☆", 2: "★★☆", 3: "★★★"}


# ---------------------------------------------------------------- 工具
def dw(text: str) -> int:
    """字符串显示宽度：东亚宽字符按 2 列计。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def pad(text: str, width: int, align: str = "left") -> str:
    gap = width - dw(text)
    if gap <= 0:
        return text
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def rule(char: str = "─", width: int = 76) -> str:
    return char * width


def topo_order() -> list:
    """按前置依赖做稳定拓扑排序（同层保持章号顺序）。"""
    done, result = set(), []
    remaining = list(CHAPTERS)
    while remaining:
        progressed = False
        for item in list(remaining):
            if all(p in done for p in item[4]):
                result.append(item)
                done.add(item[0])
                remaining.remove(item)
                progressed = True
        if not progressed:                      # 理论上不会发生，防御性处理
            result.extend(remaining)
            break
    return result


def print_graph() -> None:
    print(rule("═"))
    print("  章节依赖图（箭头方向 = 「先学 → 后学」）")
    print(rule("═"))
    print(DEP_GRAPH.rstrip())


# ---------------------------------------------------------------- 主流程
def main() -> None:
    argv = sys.argv[1:]
    if "--graph" in argv:
        print_graph()
        print(">>> 小结：依赖关系有三条硬规则——先分层再协议、先地址再路由、先单播再组播/安全。")
        print(">>> 违反它们不会报错，只会让你在后面的章节里反复「知其然不知其所在」。")
        return

    route_key = "ops"
    for key in ROUTES:
        if key in argv:
            route_key = key
            break
    else:
        if argv and not any(a.startswith("-") for a in argv):
            print(f"未知的目标画像「{argv[0]}」，可选：{' / '.join(ROUTES)}。已按默认 ops 处理。\n")

    idx = ROUTES[route_key][1]
    route_name, _, route_goal = ROUTES[route_key]

    print(rule("═"))
    print(f"  网络工程学习路径规划  ·  目标画像：{route_name}")
    print(f"  画像说明：{route_goal}")
    print(rule("═"))
    print()

    order = topo_order()
    print("【一】推荐学习顺序")
    print(rule())
    header = (f"  {pad('序号', 6)}{pad('章', 5)}{pad('标题', 30)}"
              f"{pad('难度', 8)}{pad('投入', 8)}{pad('优先级', 12)}")
    print(header)
    print("  " + rule("-", 68))

    total_core = total_imp = total_opt = 0
    hours_core = hours_imp = hours_opt = 0.0
    skippable, order_by_level = [], {"core": [], "imp": [], "opt": []}

    for n, (cid, title, diff, hours, _, levels) in enumerate(order, 1):
        level = levels[idx]
        order_by_level[level].append(cid)
        if level == "core":
            total_core += 1
            hours_core += hours
        elif level == "imp":
            total_imp += 1
            hours_imp += hours
        else:
            total_opt += 1
            hours_opt += hours
            skippable.append(f"{cid} {title}")
        print(f"  {pad(str(n), 6)}{pad(cid, 5)}{pad(title, 30)}"
              f"{pad(STARS[diff], 8)}{pad(f'{hours:g} h', 8)}{pad(LEVEL_LABEL[level], 12)}")

    print("  " + rule("-", 68))
    print(f"  标记说明：{LEVEL_MARK['core']} 核心精读 ｜ {LEVEL_MARK['imp']} 重要读懂 ｜ "
          f"{LEVEL_MARK['opt']} 选修略读")
    print()

    hours_focus = hours_core + hours_imp
    print("【二】投入核算")
    print(rule())
    print(f"  {'类别':<10}{'章数':>6}{'投入':>12}   说明")
    print("  " + rule("-", 62))
    print(f"  {'核心':<10}{total_core:>6}{f'{hours_core:g} h':>12}   必须精读并完成全部自测题")
    print(f"  {'重要':<10}{total_imp:>6}{f'{hours_imp:g} h':>12}   读懂机制 + 跑通示例脚本 + 记住排查方向")
    print(f"  {'选修':<10}{total_opt:>6}{f'{hours_opt:g} h':>12}   先跳过，遇到实际问题再回查")
    print("  " + rule("-", 62))
    print(f"  {'主路径合计':<10}{total_core + total_imp:>6}{f'{hours_focus:g} h':>12}   核心 + 重要，这是建议的完整学习量")
    print(f"  {'全部章节':<10}{len(order):>6}{f'{hours_focus + hours_opt:g} h':>12}   含选修")
    print()

    print("【三】时间规划（按每天固定投入折算）")
    print(rule())
    for per_day in (1.0, 1.5, 2.0, 3.0):
        weeks = hours_focus / (per_day * 7)
        print(f"  每天 {per_day:g} 小时  →  约 {weeks:.1f} 周（{weeks * 7:.0f} 天）完成主路径")
    print("  建议节奏：每周 1~2 章，学完立刻做自测题；难题章节（09/10/12/17/18）单独留出整块时间。")
    print()

    if skippable:
        print("【四】本路线可跳读的章")
        print(rule())
        for item in skippable:
            print(f"  · {item}")
        print("  跳读不等于不学：先建立「知道它存在、解决什么问题」的印象，")
        print("  等实际工作里撞上了，再回来精读对应章节。")
        print()

    print("【五】阶段里程碑（做完这些检验题才算过关）")
    print(rule())
    sym = {"core": "★", "imp": "☆", "opt": "·"}
    for name, ids, checks in MILESTONES:
        marks = " ".join(f"{cid}{sym[order_level(order, cid, idx)]}" for cid in ids)
        print(f"  ■ {name}   章节：{marks}   （★精读 ☆读懂 ·可跳）")
        for q in checks:
            print(f"      □ {q}")
        print()

    print_graph()
    print(rule("═"))
    print("【小结】")
    print(f"  1. 按「{route_name}」路线，建议精读 {total_core} 章、读懂 {total_imp} 章、"
          f"跳过 {total_opt} 章，主路径投入约 {hours_focus:g} 小时。")
    print(f"  2. 每天 1.5 小时约 {hours_focus / 10.5:.0f} 周，每天 3 小时约 {hours_focus / 21:.0f} 周。")
    print("  3. 顺序不可随意调换：先 01 建立分层视角，再 06 打通地址与掩码，之后才谈得上路由与传输。")
    print("  4. 学完一章就跑该章的示例脚本 —— 看得懂和跑得出来是两件事。")


def order_level(order, cid, idx) -> str:
    for item in order:
        if item[0] == cid:
            return item[5][idx]
    return "opt"


if __name__ == "__main__":
    main()
