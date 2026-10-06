#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""故障案例重放：把 14 个真实场景的排查过程按时间线逐条重放出来。

运行:
    python3 case_replay.py          # 打印全部案例的摘要与统计
    python3 case_replay.py 4        # 详细重放案例 04
    python3 case_replay.py all      # 依次详细重放全部案例
"""
import sys

sys.dont_write_bytecode = True

CASES = [
    {
        "no": 1,
        "title": "跨网段不通：Trunk 链路漏放了一个 VLAN",
        "tags": ["VLAN", "二层", "变更遗漏"],
        "symptom": "VLAN 20 的终端能上网、能访问 VLAN 10，但访问同 VLAN 20 的打印机超时。",
        "timeline": [
            ("T+0m", "用户报障", "研发区终端访问同 VLAN 打印机超时，访问其它资源正常"),
            ("T+5m", "缩小范围", "确认同交换机内的 VLAN 20 主机互通，跨交换机不通 → 问题在链路"),
            ("T+12m", "采集现场", "show vlan brief 确认两端交换机都有 VLAN 20 且端口已划入"),
            ("T+18m", "关键一步", "show interfaces trunk 发现 allowed vlan 列表里没有 20"),
            ("T+22m", "排除干扰", "show spanning-tree vlan 20 无该实例，确认不是生成树阻塞"),
            ("T+26m", "定位根因", "新划 VLAN 时只在本地创建并划口，忘记在级联 Trunk 上放行"),
            ("T+30m", "修复", "两端 Trunk 执行 switchport trunk allowed vlan add 20"),
        ],
        "root_cause": "VLAN 的广播域在 Trunk 链路处被截断，同交换机内的 ARP 广播能看到，跨交换机看不到。",
        "lesson": "划 VLAN 是「三步」动作：本地创建 → 端口划分 → Trunk 放行。漏掉第三步时现象酷似「时通时不通」。",
        "learn": "第 04 章 以太网与交换技术",
    },
    {
        "no": 2,
        "title": "广播风暴：一根两端都插在交换机上的跳线",
        "tags": ["环路", "STP", "风暴抑制"],
        "symptom": "整个办公区时断时续，延迟飙到秒级，核心设备 CPU 打到 90%。",
        "timeline": [
            ("T+0m", "监控告警", "核心交换机 CPU 告警，多台终端反馈网络卡顿"),
            ("T+3m", "看流量", "show interfaces 发现某口 5 分钟输入速率高达 943Mbps"),
            ("T+8m", "看 MAC 表", "MAC 地址表被打满 4096 条，且大量表项指向同一个端口"),
            ("T+14m", "看生成树", "show spanning-tree 显示 TC（拓扑变更）计数每分钟上百次"),
            ("T+20m", "定位物理位置", "顺 MAC 漂移的端口追到机柜，发现一根跳线两端都插在本机"),
            ("T+25m", "紧急处置", "shutdown 该端口，网络在 30 秒内恢复"),
            ("T+60m", "加固", "接入端口统一配置 portfast + bpduguard，全局开启风暴抑制 5%"),
        ],
        "root_cause": "端口配了 portfast 但没配 BPDU Guard，等于把端口排除在 STP 之外，环路形成后广播帧无限循环。",
        "lesson": "PortFast 必须与 BPDU Guard 成对出现；只配前者不是优化，而是关掉了保护。",
        "learn": "第 04 章 以太网与交换技术",
    },
    {
        "no": 3,
        "title": "路由黑洞：汇总路由把流量引进了 NULL0",
        "tags": ["路由汇总", "黑洞", "OSPF"],
        "symptom": "某分公司无法访问总部数据中心，但访问互联网正常。",
        "timeline": [
            ("T+0m", "报障", "分公司反馈数据中心全部业务不通"),
            ("T+4m", "横向对比", "其他分公司访问正常 → 问题在本分公司或其上行链路"),
            ("T+10m", "看链路", "ping 运营商网关通 → 出口链路正常"),
            ("T+15m", "看路由", "show ip route <目的IP> 命中 198.51.192.0/18 via Null0"),
            ("T+20m", "查来源", "该汇总路由由上游 ABR 的 area range 下发，且含未启用的子网"),
            ("T+28m", "定位根因", "汇总范围覆盖了不存在的网段，本机生成丢弃路由，包在本地被丢"),
            ("T+45m", "修复", "收窄上游汇总范围至实际在用的网段，从下游逐个子网验证连通性"),
        ],
        "root_cause": "路由汇总的前提是「网段连续且都在用」；汇总了空网段就会产生本地丢包。",
        "lesson": "用 show ip route <目的IP> 而不是 show ip route —— 前者直接告诉你命中哪条。",
        "learn": "第 09 章 动态路由 RIP 与 OSPF",
    },
    {
        "no": 4,
        "title": "MTU 黑洞：小包通、大包死",
        "tags": ["MTU", "PMTUD", "隧道"],
        "symptom": "HTTPS 首页能打开，上传超过 ~1400 字节就卡死；ping 小包正常、大包超时。",
        "timeline": [
            ("T+0m", "报障", "文件上传失败，页面能打开但不能提交表单"),
            ("T+6m", "关键测试", "ping -s 1472 -M do 100% 丢包，ping -s 1400 正常 → 怀疑 MTU"),
            ("T+12m", "二分定位", "逐个包长测试：1360 OK、1370 FAIL → 路径 MTU 在 1380 附近"),
            ("T+18m", "抓包取证", "tcpdump 抓到 ICMP type 3 code 4：need to frag (mtu 1380)"),
            ("T+24m", "查为什么没自愈", "发现中间防火墙丢弃全部 ICMP，PMTUD 报文到不了发送方"),
            ("T+32m", "定位根因", "IPsec 隧道封装开销使可用 MTU 降到 1380，而 PMTUD 被 ICMP 策略阻断"),
            ("T+50m", "修复", "隧道接口配 tcp adjust-mss 1340，并放行路径上的 ICMP type 3 code 4"),
        ],
        "root_cause": "隧道封装抬高开销 + 防火墙封禁 ICMP，两条正确策略叠加出「黑洞」。",
        "lesson": "不要在防火墙上无脑封禁 ICMP；隧道两端必须显式配置 MSS 调整，不要只依赖 PMTUD。",
        "learn": "第 18 章 网络排障与抓包分析 / 第 20 章 网络虚拟化与云网络",
    },
    {
        "no": 5,
        "title": "ARP 欺骗：时通时断且找不到规律",
        "tags": ["ARP", "安全", "中间人"],
        "symptom": "财务部多台电脑上午 10 点起时通时断，重启能好一阵子又不行。",
        "timeline": [
            ("T+0m", "报障", "多人同时反映网络不稳定的现象"),
            ("T+8m", "观察缓存", "watch arp -n 发现网关 MAC 一分钟后从 ...11:22:33 变成 ...66:77:88"),
            ("T+15m", "抓包取证", "tcpdump arp 显示每秒多个主动 ARP 应答，源 MAC 固定"),
            ("T+22m", "锁定源头", "交换机 show mac address-table 定位到某个接入端口"),
            ("T+30m", "确认性质", "该端口下是一台被植入攻击程序的终端，在做网关伪造"),
            ("T+35m", "紧急处置", "shutdown 该端口，网关侧 ip neigh flush all 清缓存"),
            ("T+90m", "根治", "接入层启用 DHCP Snooping + IP Source Guard + 动态 ARP 检测"),
        ],
        "root_cause": "攻击者高频伪造网关的 ARP 应答，把受害主机的流量引到自己再转发或丢弃。",
        "lesson": "正常网络里主动 ARP 应答非常稀疏——它的频率异常就是最强的报警信号。",
        "learn": "第 06 章 IPv4 地址与子网划分 / 第 17 章 网络安全基础",
    },
    {
        "no": 6,
        "title": "双工不匹配：链路 up 却丢包 30%",
        "tags": ["物理层", "双工", "CRC"],
        "symptom": "服务器迁移后链路 up，但大文件传输只有 10MB/s，丢包率约 30%。",
        "timeline": [
            ("T+0m", "报障", "迁移后业务明显变慢，但系统显示网卡正常"),
            ("T+5m", "看统计", "ip -s link 显示 RX errors 一千两百多万，dropped 九千多"),
            ("T+10m", "看协商", "ethtool eth0 显示 Auto-negotiation: off（固定 1000M/Full）"),
            ("T+15m", "看对端", "交换机侧 show interfaces 是自动协商，且有大量 CRC 错包"),
            ("T+20m", "定位根因", "一端固定一端自协商，交换机猜成半双工，形成冲突与丢包"),
            ("T+25m", "修复", "服务端改回 autoneg on，双方向统计归零，速度恢复"),
            ("T+40m", "建基线", "把接口 errors/CRC 计数纳入日常巡检基线"),
        ],
        "root_cause": "自协商必须两端都开启；一端固定时对端会猜错双工模式。",
        "lesson": "ethtool 里出现 Auto-negotiation: off 就是一个必须先排除的危险信号。",
        "learn": "第 02 章 物理层与传输介质 / 第 04 章 以太网与交换技术",
    },
    {
        "no": 7,
        "title": "DNS 解析失败：内网域名被公网 DNS 负缓存",
        "tags": ["DNS", "负缓存", "配置"],
        "symptom": "内网系统偶发打不开，重试几次能成功；访问外网完全正常。",
        "timeline": [
            ("T+0m", "报障", "用户反馈内部系统「时好时坏」，重试后正常"),
            ("T+6m", "看配置", "scutil --dns 显示终端配了两个 DNS：内网 192.0.2.53 与公网 8.8.8.8"),
            ("T+12m", "分头验证", "dig @192.0.2.53 内网域名 → 正常返回；@8.8.8.8 → NXDOMAIN"),
            ("T+18m", "确认机制", "公网 DNS 的 NXDOMAIN 被负缓存，一段时间内解析全部直接失败"),
            ("T+22m", "排除干扰", "持续 100 次直连内网 DNS 测试，100% 成功 → 内网 DNS 本身没问题"),
            ("T+30m", "定位根因", "DHCP 同时下发了内外网两个 DNS，导致解析被公网服务器抢走"),
            ("T+45m", "修复", "DHCP 只下发内网 DNS，内网 DNS 上配置转发器指向公网"),
        ],
        "root_cause": "NXDOMAIN 会被负缓存，比超时更隐蔽——它让一段时间内的解析被「确定地判死」。",
        "lesson": "企业内网绝不要把公网 DNS 直接下发给终端；解析链必须通过内网 DNS 收敛。",
        "learn": "第 14 章 DNS 与 DHCP",
    },
    {
        "no": 8,
        "title": "TCP 半开与 CLOSE_WAIT 堆积",
        "tags": ["TCP", "应用缺陷", "资源耗尽"],
        "symptom": "Java 应用运行几天后越来越慢，最终无法建立新连接；重启即恢复。",
        "timeline": [
            ("T+0m", "报障", "应用完全不可用，重启后立即恢复"),
            ("T+4m", "看连接", "ss -tan 统计出 6821 个 CLOSE-WAIT，ESTAB 只有 312 个"),
            ("T+10m", "看文件描述符", "进程 fd 数 10214，ulimit -n 为 10240 → 已经到顶"),
            ("T+16m", "抓包还原", "对端先发 FIN，本端只回 ACK，始终没有自己的 FIN"),
            ("T+25m", "定位根因", "应用只在正常路径 close()，异常分支泄漏连接"),
            ("T+35m", "应急", "调高 fs.file-max 与 ulimit，争取修复时间"),
            ("T+1d", "修复", "改用 try-with-resources；连接池开启泄漏检测"),
        ],
        "root_cause": "CLOSE_WAIT 是「内核在等应用调用 close()」的状态——它永远是应用层问题。",
        "lesson": "CLOSE_WAIT 堆积查代码，TIME_WAIT 堆积调内核参数，两者不要搞混。",
        "learn": "第 12 章 TCP 协议详解",
    },
    {
        "no": 9,
        "title": "NAT 会话表耗尽：高峰期内网间歇性断网",
        "tags": ["NAT", "容量", "会话表"],
        "symptom": "办公网 500 余人，每天 14:00-16:00 部分用户网页打不开，非高峰正常。",
        "timeline": [
            ("T+0m", "报障", "高峰期多人反映网页打不开，刷新偶尔能通"),
            ("T+6m", "排除链路", "看接口错误计数与运营商链路，均正常，带宽用到 80% 未打满"),
            ("T+14m", "看 NAT", "show ip nat statistics 峰值 65400 会话，Miss 持续增长"),
            ("T+20m", "算容量", "3 个公网地址 × 64512 端口理论上够用，但短连接堆积占用端口"),
            ("T+28m", "找占用者", "统计会话表来源，发现少数终端各开了上万个连接"),
            ("T+40m", "定位根因", "公网地址池偏小 + 部分终端 P2P 行为，端口池被耗尽"),
            ("T+60m", "修复", "扩大地址池、把 TCP 老化缩到 300 秒、接入层限制异常连接"),
        ],
        "root_cause": "NAT 端口池耗尽时新连接建立不了 DNAT 映射，包被静默丢弃，表现为「超时」而非「拒绝」。",
        "lesson": "出口容量要按「并发会话数」而非「带宽」估算：经验值每用户 300~500 会话。",
        "learn": "第 17 章 网络安全基础",
    },
    {
        "no": 10,
        "title": "Wi-Fi 漫游掉线：走动时视频会议必然中断",
        "tags": ["WLAN", "漫游", "信道规划"],
        "symptom": "笔记本在办公区走动经过走廊时视频会议断 3~5 秒，坐着不动完全正常。",
        "timeline": [
            ("T+0m", "报障", "移动场景下视频会议周期性中断"),
            ("T+8m", "换设备验证", "换一台笔记本测试，现象一致 → 不是终端问题"),
            ("T+15m", "看信道", "控制器显示同楼层三个 AP 都使用信道 36，利用率 58~71%"),
            ("T+22m", "分析机制", "同频干扰压缩可用带宽，且终端粘在弱信号 AP 上"),
            ("T+30m", "看漫游", "show client detail 显示漫游原因为 Poor Signal Quality，切换耗时长"),
            ("T+38m", "定位根因", "信道未规划 + 漫游阈值过低 + 未启用 802.11r"),
            ("T+70m", "修复", "信道错开 36/44/52，提高漫游敏感度，启用 802.11r（目标 <50ms）"),
        ],
        "root_cause": "无线设计是三维的（覆盖 / 容量 / 干扰）；只看「信号满格」会漏掉后两者。",
        "lesson": "语音视频类业务必须上 802.11r 快速漫游，切换时间目标定在 50ms 以内。",
        "learn": "第 05 章 无线局域网 WLAN",
    },
    {
        "no": 11,
        "title": "DHCP 地址池耗尽：新设备拿不到 IP",
        "tags": ["DHCP", "地址规划", "MAC 随机化"],
        "symptom": "会议室新装 20 台设备全部显示 169.254.x.x，但该网口以前是正常的。",
        "timeline": [
            ("T+0m", "报障", "新设备无法联网，显示 APIPA 地址"),
            ("T+5m", "看服务", "DHCP 服务进程正常，日志无报错 → 不是服务挂了"),
            ("T+12m", "看池子", "show ip dhcp pool 显示 254/254 全部租出"),
            ("T+18m", "看占用者", "绑定表里大量为新 MAC，且租期是 7 天"),
            ("T+26m", "定位根因", "手机 / 笔记本的 MAC 随机化让同一设备反复申请新地址，长租期使地址无法回收"),
            ("T+35m", "修复", "租期缩到 4 小时，划清静态绑定与动态池，扩容子网"),
            ("T+50m", "加固", "监控池使用率，超过 80% 告警"),
        ],
        "root_cause": "MAC 随机化时代，地址需求不再是「设备数」，而是远高于设备数的「连接次数」。",
        "lesson": "地址池按设备数的 1.5~2 倍规划，租期按场景分级设置。",
        "learn": "第 14 章 DNS 与 DHCP",
    },
    {
        "no": 12,
        "title": "BGP 邻居震荡：跨运营商专线反复中断",
        "tags": ["BGP", "物理层", "监控"],
        "symptom": "与运营商的 BGP 邻居每十几分钟断开重连一次，业务靠备线兜住但有抖动。",
        "timeline": [
            ("T+0m", "告警", "BGP 邻居 Down/Up 告警反复出现"),
            ("T+5m", "看状态", "show ip bgp summary 显示 Up/Down 只有 4 分钟，PfxRcd 正常"),
            ("T+10m", "看日志", "Notification 的 code 为 4/0（hold time expired）→ 不是认证问题"),
            ("T+18m", "测链路", "ping -c 100 显示 3% 丢包，最大 RTT 892ms，抖动巨大"),
            ("T+25m", "查物理", "读光模块功率，发现光衰接近门限，误码导致随机丢包"),
            ("T+35m", "定位根因", "物理层质量问题 → KEEPALIVE 丢失 → Hold Timer 超时 → 邻居中断"),
            ("T+2h", "处置", "报修运营商；同时启用 BFD 让检测从秒级提速到毫秒级"),
        ],
        "root_cause": "BGP 邻居震荡的根因几乎总在物理层或底层 IGP，不在 BGP 参数上。",
        "lesson": "看到 hold time expired 就去查链路质量，别去调计时器——那只会把问题盖住。",
        "learn": "第 10 章 动态路由 IS-IS 与 BGP / 第 18 章 网络排障与抓包分析",
    },
    {
        "no": 13,
        "title": "链路聚合不生效：带宽没翻倍",
        "tags": ["链路聚合", "哈希", "容量"],
        "symptom": "服务器上行做了 4 口 LACP 聚合，但单线程测试仍只有 940Mbps。",
        "timeline": [
            ("T+0m", "验收失败", "期望 4Gbps，实测单流 940Mbps"),
            ("T+6m", "看聚合组", "show etherchannel summary 显示四个口都是 P（成员正常）"),
            ("T+12m", "看速率", "逐个成员口确认都是 1000M/Full，无异常"),
            ("T+18m", "多流测试", "iperf3 -P 8 达到 3.6Gbps → 说明聚合本身是好的"),
            ("T+25m", "看分布", "各成员口流量统计显示只有 2 个口有流量，分布严重不均"),
            ("T+32m", "定位根因", "聚合按「流」哈希，默认算法只看 MAC，单会话永远走同一个口"),
            ("T+50m", "优化", "哈希算法改为含 L4 端口的规格，观察分布改善"),
        ],
        "root_cause": "链路聚合解决的是「多会话总吞吐」，天然无法加速单条连接。",
        "lesson": "验收必须用多流测试（iperf3 -P 8）；单流测试只能证明「一个口跑满了」。",
        "learn": "第 04 章 以太网与交换技术",
    },
    {
        "no": 14,
        "title": "容器网络不通：跨节点 Pod 无法通信",
        "tags": ["K8s", "CNI", "路由同步"],
        "symptom": "同一 Deployment 分在不同节点的两个 Pod 互相 curl 超时，同节点内正常。",
        "timeline": [
            ("T+0m", "报障", "Service 间歇性 502，排查发现跨节点 Pod 不通"),
            ("T+6m", "分场景验证", "同节点 Pod 互 ping 正常，跨节点 100% 丢包"),
            ("T+12m", "看路由", "ip route | grep 10.244 发现缺少到 node2 Pod 网段的路由"),
            ("T+18m", "看节点", "kubectl get nodes 显示 node2 的 podCIDR 为 null"),
            ("T+24m", "看组件", "node2 上的 CNI DaemonSet Pod 处于 CrashLoopBackOff"),
            ("T+32m", "定位根因", "CNI 的 IPAM 配置错误导致该节点未分配网段、未宣告路由"),
            ("T+55m", "修复", "修正配置、补齐 podCIDR、重启 CNI 组件并验证端到端连通"),
        ],
        "root_cause": "跨节点 Pod 不通，九成是节点路由没同步——本节点的 cni0 网桥正常所以同节点不受影响。",
        "lesson": "容器排障第一句：ip route | grep <pod-cidr>；第二句：看 CNI 组件重启次数。",
        "learn": "第 20 章 网络虚拟化与云网络",
    },
]

DIM, BOLD, OK, WARN, END = "\033[2m", "\033[1m", "\033[32m", "\033[33m", "\033[0m"


def overview() -> None:
    print("=" * 92)
    print("  故障案例库 · 14 个真实场景")
    print("=" * 92)
    print()
    print(f"  {'#':>3}  {'标题':<44}{'标签':<26}")
    print("  " + "─" * 86)
    for c in CASES:
        tags = "/".join(c["tags"])
        title = c["title"]
        print(f"  {c['no']:>3}  {title:<44}{tags:<26}")
    print()
    print("  每个案例的排查过程都遵循同一条路径：")
    print("    现象 → 缩小范围 → 采集现场 → 形成假设 → 逐一验证 → 定位根因 → 修复 → 复盘")
    print()

    tag_count = {}
    for c in CASES:
        for t in c["tags"]:
            tag_count[t] = tag_count.get(t, 0) + 1
    top = sorted(tag_count.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    print("  高频标签：" + "、".join(f"{t}×{n}" for t, n in top))
    print()
    print("=" * 92)
    print("【小结】")
    print(f"  1. 14 个案例覆盖了从物理层（双工、光衰）到云网络（CNI、VXLAN）的全部层次，"
          f"共 {len(tag_count)} 类标签。")
    print("  2. 出现最多的根因类型是「配置遗漏」与「两端不一致」——"
          "这正是变更流程要解决的核心问题。")
    print("  3. 每个案例真正值钱的部分不是结论，而是「假设与验证」那一列——"
          "它展示的是如何用最小代价排除可能性。")
    print("  4. 详细重放某个案例：python3 case_replay.py 4   （1~14）")
    print("  5. 逐个重放全部案例：python3 case_replay.py all")


def replay(case: dict) -> None:
    print("=" * 92)
    print(f"  案例 {case['no']:02d} · {case['title']}")
    print(f"  标签：{' / '.join(case['tags'])}")
    print("=" * 92)
    print()
    print(f"  {BOLD}【现象】{END}{case['symptom']}")
    print()
    print(f"  {BOLD}【排查时间线】{END}")
    width = max(len(t) for t, _, _ in case["timeline"])
    for t, action, detail in case["timeline"]:
        mark = "▶" if action in ("关键一步", "抓包取证", "定位根因", "定位物理位置",
                                 "确认性质", "分场景验证", "看分布") else "·"
        print(f"    {mark} {t:<{width}}  {action:<10} {detail}")
    print()
    print(f"  {BOLD}【根因】{END}{case['root_cause']}")
    print()
    print(f"  {WARN}【教训】{END}{case['lesson']}")
    print()
    print(f"  {OK}【对应章节】{END}{case['learn']}")
    print()
    print("─" * 92)
    print(f"{BOLD}  如果是你，在下面这些时刻会怎么做？{END}")
    print("    · 报障后的第一个动作是什么？先采集什么证据，为什么？")
    print("    · 时间线里哪一步是「转折点」——从它开始才真正锁定了方向？")
    print("    · 如果当时跳过了这一步、直接去改配置，最坏的结果会是什么？")
    print("    · 这个故障在你的环境里发生的概率有多大？现在有什么措施能防住它？")


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        overview()
        return
    if argv[0] == "all":
        for i, case in enumerate(CASES):
            if i:
                print()
            replay(case)
        print()
        print("=" * 92)
        print("【小结】")
        print(f"  已依次重放全部 {len(CASES)} 个案例。"
              "建议把每个案例的「现象 + 根因」抄进自己的排障笔记，"
              "下次遇到类似症状时先想「这像哪个案例」。")
        return

    key = argv[0]
    if not key.isdigit() or not (1 <= int(key) <= len(CASES)):
        print(f"案例编号需在 1~{len(CASES)} 之间（或使用 all）。")
        print("用法：python3 case_replay.py 4   /   python3 case_replay.py all")
        return
    replay(CASES[int(key) - 1])


if __name__ == "__main__":
    main()
