#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可运行的排障决策树：按你的回答逐层收敛，直到定位到结论。

运行:
    python3 decision_tree.py                     # 遍历两棵树的全部分支（概览）
    python3 decision_tree.py down                # 从「完全不通」开始，走默认分支
    python3 decision_tree.py down n y n          # 用 y(是) / n(否) 指定每一步答案
    python3 decision_tree.py slow y n y          # 从「慢 / 偶发失败」开始推理
    python3 decision_tree.py tree down           # 只打印这一棵树的分支结构
"""
import sys

sys.dont_write_bytecode = True

# ------------------------------------------------------------------ 决策树
# 问题节点: {"q": 问题, "cmd": 建议执行的命令,
#           "yes": (答案含义, 下一个节点), "no": (答案含义, 下一个节点)}
# 结论节点: {"conclusion": 结论, "action": [建议动作], "learn": 对应章节}
TREES = {
    "down": {
        "title": "完全不通（自底向上）",
        "start": "Q1",
        "nodes": {
            "Q1": {
                "q": "接口是否处于 UP 状态？",
                "cmd": "ip -br link show   /   show interfaces status",
                "yes": ("接口 UP", "Q2"),
                "no": ("接口 DOWN 或未识别", "C1"),
            },
            "C1": {
                "conclusion": "物理层问题：链路根本没起来",
                "action": [
                    "查网线 / 光纤是否插好，换一根跳线交叉验证",
                    "看光模块收发光功率：ethtool -m eth0 / show interfaces transceiver",
                    "确认对端端口没被 shutdown，也没被 err-disable",
                    "PoE 设备检查供电是否足够（AP / 摄像头场景）",
                ],
                "learn": "第 02 章 物理层与传输介质",
            },
            "Q2": {
                "q": "收发包计数在增长，且没有 CRC 错包？",
                "cmd": "ip -s link show eth0   /   ethtool -S eth0   /   show interfaces",
                "yes": ("计数正常、无错包", "Q3"),
                "no": ("收 0 包，或有大量 CRC / input errors", "C2"),
            },
            "C2": {
                "conclusion": "二层链路异常：要么帧发不出去，要么在传输中被打坏",
                "action": [
                    "有大量 CRC 错包 → 物理层误码：查线缆质量、光衰、接头",
                    "本端全双工但丢包严重 → 查双工不匹配：两端都必须自动协商或两端都固定",
                    "收 0 包 → 查 VLAN 是否放行、STP 是否阻塞了该端口、端口是否被隔离",
                    "确认端口没被风暴抑制 / 端口安全 err-disable 掉",
                ],
                "learn": "第 03 章 数据链路层原理 / 第 04 章 以太网与交换技术",
            },
            "Q3": {
                "q": "同网段的对端能 ping 通吗？",
                "cmd": "ping <同网段对端>   /   arp -a",
                "yes": ("同网段可通", "Q4"),
                "no": ("同网段不通", "C3"),
            },
            "C3": {
                "conclusion": "VLAN / 掩码 / ARP 层面问题——广播域被截断",
                "action": [
                    "确认两端掩码一致（掩码不同会导致误判同网段）",
                    "查 Trunk 是否放行了该 VLAN：show interfaces trunk / display port vlan",
                    "查 Access 口的 PVID 是否正确：show vlan brief",
                    "ARP 能否解析到：ip neigh show，若 incomplete 则是二层不通",
                ],
                "learn": "第 04 章 以太网与交换技术 / 第 06 章 IPv4 地址与子网划分",
            },
            "Q4": {
                "q": "网关地址能 ping 通吗？",
                "cmd": "ping <网关>   /   ip route get <目的IP>",
                "yes": ("网关可通", "Q5"),
                "no": ("网关不通", "C4"),
            },
            "C4": {
                "conclusion": "网关不可达：网关配置、冗余协议状态或 ARP 出了问题",
                "action": [
                    "确认本机配置的网关地址与网段匹配",
                    "查 VRRP / HSRP 主备状态：show vrrp / display vrrp",
                    "查网关设备的 ARP 表里有没有这台主机",
                    "怀疑 ARP 欺骗时：连续观察 arp -a，看网关 MAC 是否在变",
                ],
                "learn": "第 08 章 路由基础与静态路由 / 第 11 章 网关冗余与组播",
            },
            "Q5": {
                "q": "路由表里有到达目的地址的条目吗？",
                "cmd": "ip route get <目的IP>   /   show ip route <目的IP>",
                "yes": ("有匹配路由", "Q6"),
                "no": ("无路由（或命中 Null0 / 默认路由但不够）", "C5"),
            },
            "C5": {
                "conclusion": "路由缺失或路由错误——包在本地就被丢了",
                "action": [
                    "无任何匹配 → 补默认路由或明细静态路由",
                    "命中 Null0 → 汇总路由造成的黑洞，检查路由聚合范围",
                    "只有默认路由但下一跳不可达 → 查默认路由的下一跳是否有效",
                    "跨设备场景查动态路由邻居：show ip ospf neighbor / show ip bgp summary",
                ],
                "learn": "第 09 章 动态路由 RIP 与 OSPF / 第 10 章 动态路由 IS-IS 与 BGP",
            },
            "Q6": {
                "q": "目的端口能连上吗？",
                "cmd": "nc -zv <IP> <端口>   /   telnet <IP> <端口>",
                "yes": ("端口可连", "C7"),
                "no": ("端口不通", "C6"),
            },
            "C6": {
                "conclusion": "三层可达但四层被拦——策略类问题",
                "action": [
                    "确认服务在监听：ss -tulnp | grep <端口>",
                    "查中间设备的 ACL / 安全策略：show access-lists / display acl all",
                    "查防火墙会话表与安全区域策略",
                    "NAT 场景确认是否需要配置端口映射（外部主动访问必须显式映射）",
                ],
                "learn": "第 17 章 网络安全基础",
            },
            "C7": {
                "conclusion": "各层都正常但仍不通——查隐形杀手",
                "action": [
                    "MTU 黑洞：ping -s 1472 -M do 测试；抓 icmp[0]=3 and icmp[1]=4",
                    "非对称路由：去程和回程走不同路径，状态防火墙会丢弃回包",
                    "策略路由 PBR：确认没有把流量引到错误的出口",
                    "中间设备的会话表 / 连接跟踪表是否已满",
                    "确认没有 IP 地址冲突（同一网段出现两个相同 IP）",
                ],
                "learn": "第 18 章 网络排障与抓包分析",
            },
        },
    },
    "slow": {
        "title": "慢 / 时通时断 / 偶发失败（自顶向下）",
        "start": "M1",
        "nodes": {
            "M1": {
                "q": "是所有终端都有问题，还是只有个别人？",
                "cmd": "多找几台不同位置的终端同时测试，别只问一个用户",
                "yes": ("所有人 / 大范围", "M2"),
                "no": ("只有个别人", "D1"),
            },
            "D1": {
                "conclusion": "终端侧问题——先别查网络",
                "action": [
                    "检查该终端的 IP / 掩码 / 网关 / DNS 配置是否与其他正常终端一致",
                    "看网卡协商速率与双工：ethtool eth0",
                    "无线终端看信号强度、信道干扰、是否频繁漫游",
                    "排查终端自身的异常（病毒、P2P、连接数打满）",
                ],
                "learn": "第 05 章 无线局域网 WLAN / 第 02 章 物理层与传输介质",
            },
            "M2": {
                "q": "是所有业务都不好，还是只有特定业务？",
                "cmd": "同时测试内网互访、访问互联网、访问具体业务系统",
                "yes": ("所有业务", "M3"),
                "no": ("只有特定业务", "D2"),
            },
            "D2": {
                "conclusion": "特定业务的专用链路问题",
                "action": [
                    "DNS：dig @内网DNS <业务域名> 与 @公网DNS 对比结果",
                    "负载均衡：确认后端健康检查状态，是否有后端被摘除",
                    "后端服务：看应用日志与响应时间分布，而不是网络层",
                    "该业务的专用 ACL / 安全策略是否近期变更",
                ],
                "learn": "第 14 章 DNS 与 DHCP / 第 15 章 HTTP 与 Web 协议栈",
            },
            "M3": {
                "q": "是一直不好，还是偶尔 / 间歇性？",
                "cmd": "用 mtr -c 100 持续探测，看丢包率与抖动是否稳定",
                "yes": ("一直不好（持续劣化）", "D3"),
                "no": ("偶发、间歇", "M4"),
            },
            "D3": {
                "conclusion": "容量或资源问题——不是「坏了」而是「不够用」",
                "action": [
                    "看出口带宽利用率：超过 70% 就该考虑扩容或限流",
                    "看 NAT 会话数 / 连接跟踪表是否接近上限",
                    "看设备 CPU 与内存：show processes cpu sorted / display cpu-usage",
                    "看是否有单台终端占用了大量连接或带宽",
                ],
                "learn": "第 17 章 网络安全基础（NAT）",
            },
            "M4": {
                "q": "故障有规律吗？（固定时间点 / 特定触发条件）",
                "cmd": "记录故障发生的时间点，与任务计划、日志时间对比",
                "yes": ("有规律，能预测", "D4"),
                "no": ("完全随机，找不到规律", "D5"),
            },
            "D4": {
                "conclusion": "周期性因素——通常是「计划任务」与「协议计时器」的碰撞",
                "action": [
                    "检查备份 / 同步 / 日志上传等定时任务是否占满带宽或链路",
                    "查路由协议重收敛时间点是否与故障时间吻合",
                    "查 ARP 老化、DHCP 续租等协议计时器周期",
                    "查 STP 拓扑变更与 TC 计数（周期性风暴）",
                ],
                "learn": "第 09 章 动态路由 RIP 与 OSPF / 第 06 章 IPv4 地址与子网划分",
            },
            "D5": {
                "conclusion": "随机故障——优先怀疑环路、ARP 欺骗与链路抖动",
                "action": [
                    "连续观察网关 MAC：arp -a 反复看是否变化 → ARP 欺骗",
                    "看 STP 拓扑变更计数是否异常增长 → 环路",
                    "看接口 CRC 错包与光功率是否波动 → 链路抖动",
                    "抓包统计重传率、乱序率、零窗口 → 定位到具体层",
                    "检查是否存在 IP 地址冲突（同网段出现重复 IP）",
                ],
                "learn": "第 18 章 网络排障与抓包分析 / 附录 B 案例 02、05",
            },
        },
    },
}

DIM, BOLD, OK, END = "\033[2m", "\033[1m", "\033[32m", "\033[0m"


def node_kind(tree, nid: str) -> str:
    return "conclusion" if "conclusion" in tree["nodes"][nid] else "question"


def all_paths(tree) -> list:
    """DFS 收集全部分支路径：[(节点序列, 答案序列), ...]"""
    paths = []

    def dfs(nid, nodes, answers):
        if node_kind(tree, nid) == "conclusion":
            paths.append((nodes + [nid], list(answers)))
            return
        node = tree["nodes"][nid]
        for branch, tag in (("yes", "y"), ("no", "n")):
            label, nxt = node[branch]
            dfs(nxt, nodes + [nid], answers + [tag])

    dfs(tree["start"], [], [])
    return paths


def show_tree(tree, key: str) -> None:
    print("=" * 92)
    print(f"  【{tree['title']}】决策树结构")
    print("=" * 92)
    print()

    def walk(nid, prefix, is_last, branch_label):
        node = tree["nodes"][nid]
        if node_kind(tree, nid) == "conclusion":
            print(f"{prefix}{'└─' if is_last else '├─'} {branch_label}【结论】{node['conclusion']}")
            return
        print(f"{prefix}{'└─' if is_last else '├─'} {branch_label}{node['q']}")
        print(f"{prefix}     {DIM}命令：{node['cmd']}{END}")
        nxt_prefix = prefix + ("   " if is_last else "│  ")
        walk(node["yes"][1], nxt_prefix, False, "[是] ")
        walk(node["no"][1], nxt_prefix, True, "[否] ")

    walk(tree["start"], "", True, "")
    print()


def traverse(tree, answers: list) -> None:
    print("=" * 92)
    print(f"  【{tree['title']}】逐步推理")
    print("=" * 92)
    print()

    nid, step, i = tree["start"], 1, 0
    while True:
        node = tree["nodes"][nid]
        if node_kind(tree, nid) == "conclusion":
            print("─" * 92)
            print(f"  {BOLD}【结论】{node['conclusion']}{END}")
            print("─" * 92)
            print("  建议动作：")
            for a in node["action"]:
                print(f"    · {a}")
            print(f"\n  相关章节：{node['learn']}")
            print()
            print("=" * 92)
            print("【小结】")
            print(f"  1. 本次推理共 {step - 1} 步，每一步都用一个命令把可能原因砍掉一半。")
            print("  2. 排障的顺序比速度重要：这一步确认不了，就不要急着查下一步。")
            print("  3. 无论结论是什么，动手前先备份配置、抓一份包——现场一旦破坏就再也回不来了。")
            return

        print(f"  [第 {step} 步] {BOLD}{node['q']}{END}")
        print(f"           建议命令：{node['cmd']}")
        if i < len(answers):
            tag = answers[i]
            label = node["yes"][0] if tag == "y" else node["no"][0]
            nxt = node["yes"][1] if tag == "y" else node["no"][1]
        else:
            tag = "y"
            label, nxt = node["yes"]
            print(f"           {DIM}（未提供答案，按默认「是」继续）{END}")
        print(f"           回答：{'是' if tag == 'y' else '否'} —— {label}")
        print()
        nid, step, i = nxt, step + 1, i + 1


def overview() -> None:
    for key, tree in TREES.items():
        paths = all_paths(tree)
        depth = max(len(p[0]) for p in paths) - 1
        print("=" * 92)
        print(f"  【{tree['title']}】共 {len(paths)} 条推理路径，最深 {depth} 步")
        print("=" * 92)
        for n, (nodes, answers) in enumerate(paths, 1):
            chain = " → ".join(answers)
            tail = tree["nodes"][nodes[-1]]["conclusion"]
            print(f"  {n:>2}. {chain:<10}  {tail}")
        print()
    print("=" * 92)
    print("【小结】")
    total = sum(len(all_paths(t)) for t in TREES.values())
    print(f"  1. 两棵树合计 {total} 条路径，但每一步都只有两个分支——"
          f"这正是「收敛」的含义：每查一步，可能性减半。")
    print("  2. 「完全不通」用自底向上（先物理层），"
          "「慢 / 偶发」用自顶向下（先确认影响范围）。")
    print("  3. 想看某条具体路径的完整推理，用：python3 decision_tree.py down n y n")
    print("  4. 想看树的完整结构，用：python3 decision_tree.py tree")


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        overview()
        return
    if argv[0] == "tree":
        targets = [argv[1]] if len(argv) > 1 and argv[1] in TREES else list(TREES)
        for key in targets:
            show_tree(TREES[key], key)
        return

    key = argv[0]
    if key not in TREES:
        print(f"未知起点「{key}」，可选：{' / '.join(TREES)}")
        print("用法示例：")
        print("  python3 decision_tree.py down          # 从「完全不通」开始")
        print("  python3 decision_tree.py slow y n y    # 指定每一步答案")
        print("  python3 decision_tree.py               # 遍历全部分支")
        return

    answers = []
    invalid = []
    for token in argv[1:]:
        if token in ("y", "Y", "yes", "是"):
            answers.append("y")
        elif token in ("n", "N", "no", "否"):
            answers.append("n")
        else:
            invalid.append(token)
    if invalid:
        print(f"忽略无法识别的答案：{', '.join(invalid)}（只接受 y / n）\n")

    traverse(TREES[key], answers)


if __name__ == "__main__":
    main()
