# 附录 B · 故障案例与排障决策树

> **一句话定位**：14 个来自真实场景的故障案例，每个都按「现象 → 采集 → 假设 → 验证 → 根因 → 修复 → 复盘」
> 完整走一遍；再加两套可执行的排障决策树，把散落的协议知识变成可操作的流程。
> **前置知识**：[第 18 章](../18-网络排障与抓包分析/README.md) ｜ **难度**：★★☆ ｜ **建议投入**：8 小时

---

## 一、为什么排障比配置难

配置是**确定性**工作：给你拓扑和需求，答案唯一。排障是**搜索**工作：
现象固定，但根因可能在七层的任何一层，而且往往是「多个正确配置的组合失效」。

新手排障的典型路径是**猜**——猜 DHCP 有问题就去重启 DHCP，猜路由有问题就去加一条静态路由。
运气好碰对了，运气不好就是在上层叠更多的错误配置。

老手的路径是**收敛**：从现象里提取信息，把可能原因的集合一层层砍掉，直到只剩一个。

```
                新手：猜 ──▶ 改 ──▶ 不行 ──▶ 再猜 ──▶ 改 ──▶ 更乱
                                                    （现场被破坏）

                老手：现象 ──▶ 分层定位 ──▶ 形成假设 ──▶ 用最小代价验证
                                    ▲                          │
                                    └────────── 排除掉一半 ──────┘
                                          （现场始终保持可回溯）
```

本章的两个工具就是为「收敛」服务的：**决策树**告诉你下一个该查什么，
**案例库**用 14 个真实故障帮你建立模式和直觉。

> **读法建议**：不要从头读到尾。建议在学完[第 09 章](../09-动态路由RIP与OSPF/README.md)之后
> 先通读一遍案例标题和「现象」部分，带着«这种症状会是什么原因»的问题回去继续学协议，
> 学完[第 18 章](../18-网络排障与抓包分析/README.md)后再回来精读每个案例的「假设与验证」。

---

## 二、排障的两套决策树

### 2.1 自底向上（Bottom-Up）：适合「完全不通」

从物理层往上走，每层确认无误再进下一层。优点是不会漏掉基础问题，缺点是如果故障在上层，
前四层会白查一遍。

```
[开始] 完全不通
   │
   ├─ ① 接口是不是 UP？
   │     ip -br link show / show interfaces status
   │     ├─ DOWN ─▶ 查网线 / 光模块 / 对端端口 / PoE 供电
   │     └─ UP ──┐
   │              │
   ├─ ② 有没有收发包、有没有错包？
   │     ip -s link show eth0 / ethtool -S eth0
   │     ├─ 收 0 包 ─▶ 本端发不出去或对端没发（查 VLAN、STP 阻塞）
   │     ├─ 有 CRC 错包 ─▶ 物理层问题：线缆质量 / 光衰 / 双工不匹配
   │     └─ 收发正常 ─┐
   │                   │
   ├─ ③ 同网段能通吗？
   │     ping <同网段对端> + arp -a
   │     ├─ 不通 ─▶ 查 VLAN 划分 / 子网掩码 / ARP 是否解析到
   │     └─ 通 ──┐
   │              │
   ├─ ④ 网关能通吗？
   │     ping <网关> ; ip route get <目的IP>
   │     ├─ 不通 ─▶ 查网关地址配置 / ARP / VRRP 主备状态
   │     └─ 通 ──┐
   │              │
   ├─ ⑤ 路由存在吗？
   │     ip route / show ip route / traceroute
   │     ├─ 无路由 ─▶ 加路由 / 查路由协议邻居
   │     └─ 有路由 ─▶
   │              │
   ├─ ⑥ 能到目的地但业务不通？
   │     nc -zv <IP> <端口> ; telnet
   │     ├─ 端口不通 ─▶ 查防火墙 / ACL / NAT / 服务是否监听
   │     └─ 通 ─▶ 进应用层排查（DNS / 证书 / 应用日志）
   │
   └─ ⑦ 全层都正常但仍不通 ─▶ 查 MTU、非对称路由、策略路由、中间设备会话表
```

### 2.2 自顶向下（Top-Down）：适合「能通但不好用」

现象是「慢 / 时通时断 / 偶发失败」这类模糊问题时，从应用层往下找更有效。

```
[开始] 现象：慢 / 偶发失败 / 时通时断
   │
   ├─ ① 是所有人还是个别人？
   │     ├─ 个别人 ─▶ 看该终端：本机配置 / 网卡 / 无线信号 / 病毒
   │     └─ 所有人 ─┐
   │                │
   ├─ ② 是所有业务还是特定业务？
   │     ├─ 特定业务 ─▶ 看该业务的链路：DNS / 负载均衡 / 后端服务
   │     └─ 全部 ──┐
   │               │
   ├─ ③ 是一直不好还是偶发？
   │     ├─ 一直 ─▶ 查容量（带宽打满、会话数超限、CPU 高）
   │     └─ 偶发 ─┐
   │              │
   ├─ ④ 有规律吗？（时间点 / 触发条件 / 周期性）
   │     ├─ 定时出现 ─▶ 查定时任务、备份、同步、路由收敛、ARP 老化
   │     └─ 无规律 ─▶ 查环路、ARP 欺骗、广播风暴、链路抖动
   │
   └─ ⑤ 抓包定位
         统计重传率 / 乱序率 / 零窗口 / RTT 抖动 → 定位到具体层
```

### 2.3 两种情形下的首要动作

| 情形 | 首要动作 | 为什么 |
|------|---------|--------|
| 刚刚变更过（几分钟内出问题） | **先看变更记录、必要时回滚** | 90% 的故障和最近的变更有关，回滚是最快的验证手段 |
| 无变更、突然故障 | 看日志与告警、确认影响范围 | 缩小范围比急着动手更重要 |
| 反复出现、查不出原因 | 抓包 + 建立基线对比 | 别再用猜的，拿数据说话 |

---

## 三、故障案例库

### 案例 01 · 跨网段不通：Trunk 链路漏放了一个 VLAN

**现象**
研发区（VLAN 20）的终端能上网、能访问 VLAN 10 的服务器，
但访问同样在 VLAN 20 的打印机（接在另一台交换机上）超时。

**影响范围**：仅 VLAN 20，且仅限跨交换机的访问；同交换机内的 VLAN 20 主机互通正常。

**现场采集**

```bash
# 在接入交换机上看该 VLAN 是否在 Trunk 上被放行
SW1# show interfaces trunk
Port        Mode   Encapsulation  Status        Native vlan
Gi0/24      on     802.1q         trunking      1

Port        Vlans allowed on trunk
Gi0/24      1,10,30,40                       ← 注意：没有 20

# 看 VLAN 是否存在、有哪些口属于它
SW1# show vlan brief
VLAN Name        Status    Ports
20   RD         active    Gi0/1, Gi0/2, Gi0/3    ← VLAN 20 存在，本地口正常
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 打印机自身故障 | 从同交换机的 PC ping 打印机 | **排除**——能通 |
| 2 | 打印机网关配错 | `show run` 看打印机所在口的网关（或直接看终端 ARP） | **排除**——网关与 PC 一致 |
| 3 | 中间 Trunk 未放行 VLAN 20 | `show interfaces trunk` | **确认**——allowed 列表里没有 20 |
| 4 | 是否被 STP 阻塞 | `show spanning-tree vlan 20` | 无该 VLAN 的实例，说明是放行问题而非生成树问题 |

**根因**
新划分 VLAN 20 时，只在接入交换机上创建了 VLAN 并把端口划了进去，
**忘记在级联的 Trunk 链路上放行**。VLAN 20 的广播域因此被截断在两台交换机内部——
同交换机内能看到彼此的 ARP 广播，跨交换机则完全不可见，所以表现为「时通时不通」的假象。

**修复步骤**

```bash
SW1(config)# interface GigabitEthernet0/24
SW1(config-if)# switchport trunk allowed vlan add 20
SW2(config)# interface GigabitEthernet0/24
SW2(config-if)# switchport trunk allowed vlan add 20
```

两端都要加。只加一端也会不通——因为 Trunk 的放行是**双向**的。

**复盘与预防**
1. 划 VLAN 的标准动作是「三步」：本机创建 → 端口划分 → **Trunk 放行**。把它做成检查单。
2. 上行 Trunk 建议用 `switchport trunk allowed vlan all` 或明确的完整列表，
   避免「新增 VLAN 忘了放行」这类漏项；若出于安全要求必须白名单，就在变更流程里加一步核对。
3. 监控上可以对「VLAN 内主机数量异常」告警——某个 VLAN 的主机数突然减半，往往就是链路被截断。

---

### 案例 02 · 广播风暴：一根多插的网线引发全网瘫痪

**现象**
中午 12 点开始，整个办公区网络时断时续，Ping 延迟从 1ms 飙升到 2000ms 以上，
部分终端完全无法访问。三层核心的 CPU 使用率打到 90%。

**影响范围**：整个二层打通的办公区，包括多个 VLAN（因为广播会在 Trunk 上泛洪，
且如果存在 VLAN 未隔离的配置，影响面更大）。

**现场采集**

```bash
# 看接口流量——正常情况下不应该有持续 90% 以上的广播流量
SW1# show interfaces GigabitEthernet0/1 | include rate
  5 minute input rate 943000000 bits/sec, 780000 packets/sec   ← 打满

# 看 MAC 地址表是否在同一端口上剧烈翻动（MAC 漂移的典型特征）
SW1# show mac address-table count
Dynamic Address Count: 4096        ← 表项被打满

SW1# show mac address-table | include Gi0/1
   1    0200.0000.000a    DYNAMIC     Gi0/1
   1    0200.0000.000b    DYNAMIC     Gi0/1
   ...                                ← 大量 MAC 都从同一个口学到
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 遭受 DDoS 攻击 | 抓包看流量特征 | **排除**——流量是二层广播，非 IP 攻击流量 |
| 2 | 存在二层环路 | `show spanning-tree` 看拓扑变化计数 | **确认**——TCN 计数每分钟上百次 |
| 3 | 某台设备双网卡同时接线 | 顺着 MAC 漂移的端口追查到物理接口 | **确认**——库里发现一根两端都插在交换机上的跳线 |

**根因**
施工人员在机柜里临时接了一根跳线，两端都插在同一台交换机的两个口上（未启用 STP 的边缘端口保护）。
STP 虽然理论上能阻塞其中一个端口，但该端口配置了 `portfast`（BPDU Guard 未启用），
导致它不做生成树参与，环路形成，广播帧在环里无限循环并被复制倍增。

**修复步骤**

```bash
# 紧急处置：拔掉那根跳线（或先 shutdown 端口止损）
SW1(config)# interface GigabitEthernet0/23
SW1(config-if)# shutdown

# 加固：边缘端口必须配 BPDU Guard，收到 BPDU 就 err-disable
SW1(config)# interface range GigabitEthernet0/1 - 22
SW1(config-if-range)# spanning-tree portfast
SW1(config-if-range)# spanning-tree bpduguard enable

# 全局开启风暴抑制作为兜底
SW1(config)# interface range GigabitEthernet0/1 - 24
SW1(config-if-range)# storm-control broadcast level 5
```

**复盘与预防**
1. **接入端口必须同时配 PortFast 和 BPDU Guard**。只配 PortFast 是把端口排除在 STP 之外，
   等于关掉了保护；加上 BPDU Guard 才能在收到 BPDU 时自动 err-disable 该端口。
2. 全局开风暴抑制（broadcast/multicast/unicast 各设 5% 左右）作为最后一道防线，
   哪怕配置有疏漏也不会全网瘫痪。
3. 对 `show spanning-tree` 的 TC（拓扑变更）计数做监控告警——它的异常增长是环路的最早信号。

---

### 案例 03 · 路由黑洞：汇总路由把流量引进了 NULL0

**现象**
某分公司（`198.51.100.0/24`、`198.51.101.0/24`）突然无法访问总部数据中心，
但分公司内部互通正常，访问互联网也正常。

**影响范围**：仅该分公司到数据中心的流量；其他分公司正常。

**现场采集**

```bash
# 在分公司出口路由器上看路由
R1# show ip route 198.51.200.10
Routing entry for 198.51.192.0/18
  Known via "ospf 1", distance 110, metric 20
  Routing Descriptor Blocks:
  * directly connected, via Null0        ← 黑洞在这里
      Route metric is 20, traffic share count is 1

R1# show ip route | include Null0
O    198.51.192.0/18 [110/20] via Null0    ← 一条汇总路由指向 Null0
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 数据中心侧故障 | 从其他分公司访问 | **排除**——正常 |
| 2 | 分公司出口链路故障 | `ping` 运营商网关 | **排除**——通 |
| 3 | 本地路由表异常 | `show ip route 目的IP` | **确认**——命中了一条 Null0 路由 |
| 4 | 为什么会生成这条黑洞 | 检查 OSPF 配置中的 `area range` | **确认**——上游做了区域间汇总，本机 `Null0` 是汇总的产物 |

**根因**
上游设备为了减少路由条目，在 ABR 上做了 `area 1 range 198.51.192.0 255.255.192.0`。
该网段内的明细路由并未全部存在（部分子网已下线），
而在本机侧因为**汇总路由的优先级计算**，出现了一条指向 `Null0` 的丢包路由，
本机发出的流量在本地就被丢弃，从未真正出去。

**修复步骤**

```bash
# 确认明细路由是否真的不可达
R1# show ip route 198.51.200.10 longer-prefixes   # 看是否有更长前缀

# 若确有明细路由但被汇总压制，检查是否配了 discard-route
R1(config)# router ospf 1
R1(config-router)# no discard-route internal     # 关闭内部丢弃路由（按厂商命令差异调整）

# 更常见的修复：核实上游汇总配置是否覆盖了不存在的网段，收窄汇总范围
```

**复盘与预防**
1. **汇总的前提是「网段连续且都在用」**。做汇总前必须核对地址规划表，
   把没启用的网段排除在汇总范围外。
2. 排障时 `show ip route <目的IP>` 比 `show ip route` 更有效——它直接告诉你命中哪条。
3. 变更汇总配置后，**必须从下游设备验证到每个子网的连通性**，不能只看上游路由变少了。

---

### 案例 04 · MTU 黑洞：小包通、大包死

**现象**
Web 服务器（HTTPS）可以正常建立连接（能打开页面首页），
但只要上传文件超过约 1400 字节就卡死。`ping` 小包正常，`ping` 大包超时。

**影响范围**：所有经这条路径（中间经过一条 IPsec 隧道）的 HTTPS 大流量传输。

**现场采集**

```bash
# 关键测试：带 DF 标志发大包
$ ping -c 2 -s 1472 -M do 198.51.100.7     # Linux
PING 198.51.100.7 (198.51.100.7) 1472(1500) bytes of data.
--- 198.51.100.7 ping statistics ---
2 packets transmitted, 0 received, 100% packet loss

$ ping -c 2 -s 1400 -M do 198.51.100.7
2 packets transmitted, 2 received, 0% packet loss, time 1001ms   ← 1400 能通

# 用不同包长二分定位实际的路径 MTU
$ for s in 1200 1300 1360 1370 1380 1400; do
>   ping -c 1 -s $s -M do -W 1 198.51.100.7 >/dev/null 2>&1 \
>     && echo "$s OK" || echo "$s FAIL"
> done
1200 OK
1300 OK
1360 OK
1370 FAIL        ← 分界点在 1360~1370 之间

# 抓包确认是否收到 ICMP type 3 code 4（需要分片但 DF 置位）
$ sudo tcpdump -i eth0 -nn 'icmp and icmp[0]=3 and icmp[1]=4'
12:01:33.221 IP 203.0.113.1 > 192.0.2.10: ICMP 203.0.113.1 unreachable - need to frag (mtu 1380), length 556
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 服务器侧限制上传大小 | 换其他路径访问 | **排除**——换网段后正常 |
| 2 | 中间链路 MTU 偏小 | 带 DF 的 ping 二分测试 | **确认**——路径 MTU 为 1380 |
| 3 | PMTUD 该自动生效为什么没生效 | 抓包看 ICMP type 3 code 4 | **确认**——ICMP 报文发出但被中间防火墙丢弃 |

**根因**
这条路径经过一条 IPsec 隧道，隧道封装（ESP + 新 IP 头）带来约 70~120 字节开销，
导致实际可用 MTU 只有 1380。理论上 PMTUD（路径 MTU 发现）会自动把 MSS 降到 1340，
但**中间的防火墙把 ICMP 全部丢弃了**，缓存的 ICMP「需要分片」报文到不了发送方，
发送方一直按 1500 的 MSS 发包，包就在隧道入口被丢弃。

**修复步骤**

```bash
# 临时验证手段：手工降低 MSS 看看是否恢复
R1(config)# interface Tunnel0
R1(config-if)# ip tcp adjust-mss 1340        # Cisco
# 华为：tcp adjust-mss 1340

# 服务器侧也可以临时把 MTU 调小验证
$ sudo ip link set eth0 mtu 1400

# 根治：放行路径上的 ICMP type 3 code 4（以及必要时的 type 11），
# 并确保隧道接口正确设置了 tcp-mss-adjust
```

**复盘与预防**
1. **不要在防火墙上无脑封禁所有 ICMP**。Type 3 Code 4（需要分片）、
   Type 11（超时）是网络自愈机制的一部分，封了就会制造 MTU 黑洞。
2. 任何隧道（IPsec / GRE / VXLAN）都必须在两端配置 MSS 调整，
   不要依赖 PMTUD 一定生效。具体开销计算见[第 20 章](../20-网络虚拟化与云网络/README.md)。
3. 把「带 DF 的 ping 二分测试」写进上线检查清单——这是验证路径 MTU 最快的办法。

---

### 案例 05 · ARP 欺骗：时通时断且找不到规律

**现象**
财务部多台电脑在上午 10 点左右开始「时通时断」，重启电脑能好一阵子，
但过一会儿又不行。访问内网服务器和互联网都受影响。

**影响范围**：同一个 VLAN 内多台终端，且位置分散（不同交换机端口）。

**现场采集**

```bash
# 连续观察网关的 MAC 是否在变化
$ watch -n 1 'arp -n | grep 192.0.2.1'
192.0.2.1  ether  02:00:00:11:22:33   C   eth0      ← 第一次
192.0.2.1  ether  02:00:00:66:77:88   C   eth0      ← 一分钟后变了！

# 抓包看 ARP 应答的频率（正常情况极少，因为缓存有 20 分钟生命周期）
$ sudo tcpdump -i eth0 -nn arp
10:03:12.331 ARP, Reply 192.0.2.1 is-at 02:00:00:66:77:88, length 46
10:03:13.102 ARP, Reply 192.0.2.1 is-at 02:00:00:66:77:88, length 46
10:03:13.887 ARP, Reply 192.0.2.1 is-at 02:00:00:66:77:88, length 46
...                                        ← 每秒多个主动应答，且源 MAC 是同一个
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 网关设备不稳定 | 从其他 VLAN 访问网关 | **排除**——其他 VLAN 稳定 |
| 2 | IP 地址冲突 | `arping` 检测 | **排除**——`arping` 只有网关一个应答者 |
| 3 | 存在 ARP 欺骗 | 观察 ARP 应答频率与源 MAC | **确认**——某个 MAC 主动高频应答网关 IP |
| 4 | 那个 MAC 是谁 | 在交换机上 `show mac address-table | include 6677.88` | **确认**——指向某个接入端口，端口下是一台被植入程序的终端 |

**根因**
某台终端中了局域网内的攻击程序，它会周期性地向网段内的所有主机发送伪造的 ARP 应答，
声称「网关 IP 对应的 MAC 是我」。受害主机更新缓存后，去往网关的流量全部发给攻击者，
攻击者再转发（或选择性丢弃），造成「时通时断」。这类攻击的目标通常是窃取凭据。

**修复步骤**

```bash
# 直接处置
SW1(config)# interface GigabitEthernet0/7
SW1(config-if)# shutdown              # 先隔离被感染的终端

# 网关侧清掉被污染的缓存
$ sudo ip neigh flush all

# 根治：接入层三件套
SW1(config)# ip dhcp snooping
SW1(config)# ip dhcp snooping vlan 20
SW1(config)# ip arp inspection vlan 20
SW1(config)# interface GigabitEthernet0/24
SW1(config-if)# ip arp inspection trust      # 只信任上行口

# 终端侧加固（可选）——静态 ARP 绑定
$ sudo ip neigh add 192.0.2.1 lladdr 02:00:00:11:22:33 dev eth0 nud permanent
```

**复盘与预防**
1. **接入层安全三件套**：DHCP Snooping（建立可信的 IP-MAC 绑定表）
   + IPSG（IP 源防护）+ DAI（动态 ARP 检测）。三者形成闭环，ARP 欺骗无法生效。
2. 终端侧也要管：装杀毒、禁止随意接入、用 802.1X 认证。
3. 监控「ARP 应答频率」这个指标——正常网络里主动 ARP 应答是非常稀疏的事件。

---

### 案例 06 · 双工不匹配：链路 up 但丢包 30%

**现象**
某台服务器迁移到新机柜后，与交换机的链路正常 up，但网络特别慢，
大文件传输速度只有 10MB/s，且丢包率约 30%。

**影响范围**：仅这一条链路。

**现场采集**

```bash
# 看接口统计——错包计数是判断物理层问题的关键
$ ip -s link show eth0
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    RX: bytes  packets  errors  dropped  overrun  mcast
    ...
    errors 12837421  dropped 9832         ← RX errors 异常高

$ sudo ethtool eth0
Settings for eth0:
    Speed: 1000Mb/s
    Duplex: Full                            ← 本端是全双工
    Auto-negotiation: off                   ← 但自动协商被关了！
    Link detected: yes

# 交换机侧
SW1# show interfaces GigabitEthernet0/12
  GigabitEthernet0/12 is up, line protocol is up
  ...
  MTU 1500 bytes, BW 1000000 Kbit/sec
  Full-duplex, 1000Mb/s                  ← 交换机侧也是全双工
  ...
      1234567 input errors, 890123 CRC    ← 大量 CRC 错误与输入错误
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 网线质量差 | 换一根跳线 | **排除**——无改善 |
| 2 | 服务器网卡故障 | 换一块网卡 | **排除**——无改善 |
| 3 | 端口速率/双工协商异常 | `ethtool` 与 `show interfaces` | **确认**——服务端关闭了自动协商而交换机侧是自协商 |

**根因**
服务器侧网卡驱动被手工设成了固定 1000M/全双工，而交换机侧仍是自动协商。
硬件自协商（Auto-Negotiation）需要**两端都开启**才能正确交换双工能力；
一端固定、一端自协商时，交换机侧会「猜」成半双工（因为无法通过 FLP 脉冲协商），
结果就是经典的「一端全双工、一端半双工」，造成冲突与丢包。

**修复步骤**

```bash
# 服务端改回自动协商（推荐）
$ sudo ethtool -s eth0 autoneg on
$ sudo ethtool eth0 | grep -E 'Speed|Duplex|Auto'

# 或者两端都强制固定（不推荐，除非对端设备不支持自协商）
$ sudo ethtool -s eth0 speed 1000 duplex full autoneg off
SW1(config)# interface GigabitEthernet0/12
SW1(config-if)# speed 1000
SW1(config-if)# duplex full
```

**复盘与预防**
1. **默认永远用自动协商**。只有在极老的设备上才对两端同时强制固定，绝不能只固定一端。
2. `show interfaces` 里的 `input errors` 和 `CRC` 计数是物理层故障的第一信号，
   上线后应该立即记录基线值，之后对比。
3. `ethtool` 的 `Auto-negotiation: off` 是一个极易被忽略的危险信号。

---

### 案例 07 · DNS 解析失败：内网域名偶发解析不了

**现象**
内网用户访问内部系统（`erp.corp.example`）时，偶尔需要通过「重试几次」才能打开，
而访问外网（如 `www.example.com`）完全正常。重试后成功，但过一会儿又失败。

**影响范围**：所有内网终端，偶发。

**现场采集**

```bash
# 看本机配了几个 DNS 服务器
$ scutil --dns | grep nameserver          # macOS
  nameserver[0] : 192.0.2.53              # 内网 DNS
  nameserver[1] : 8.8.8.8                 # 公网 DNS ← 问题在这

# 直接分别测试两个服务器
$ dig @192.0.2.53 erp.corp.example +short
198.51.100.20                              ← 内网 DNS 能解析

$ dig @8.8.8.8 erp.corp.example +short
                                           ← 公网 DNS 什么都返回不了

$ dig @8.8.8.8 erp.corp.example
;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 43210   ← 而且是 NXDOMAIN 不是超时
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 内网 DNS 服务器不稳定 | 持续 `dig @192.0.2.53` 测试 100 次 | **排除**——100% 成功 |
| 2 | 应用系统本身慢 | 直接用 IP 访问 | **排除**——秒开 |
| 3 | 终端配置了多个 DNS，解析被公网 DNS 抢走 | `scutil --dns` + 分别 `dig` | **确认**——公网 DNS 返回 NXDOMAIN |

**根因**
终端通过 DHCP 拿到了两个 DNS：内网 DNS（先）和公网 DNS（后）。
当内网 DNS 稍慢或返回慢时，解析器会**并发或顺延**查询第二个服务器；
公网 DNS 对内网域名返回 `NXDOMAIN`（不存在），并且这个「不存在」的结果
会按照 TTL 被**负缓存**，于是接下来一段时间内所有这个域名的解析都直接失败——
直到缓存过期，重试才成功。

**修复步骤**

```bash
# 方案一（推荐）：DHCP 只下发内网 DNS；内网 DNS 上配置转发器指向公网 DNS
SW1(config)# ip dhcp pool OFFICE
SW1(config-dhcp)# no dns-server 8.8.8.8
SW1(config-dhcp)# dns-server 192.0.2.53 192.0.2.54

# 内网 DNS 侧（BIND 示例）配置转发
# /etc/named.conf
#   zone "corp.example" { type master; file "corp.example.zone"; };
#   forwarders { 8.8.8.8; 1.1.1.1; };
#   forward only;

# 方案二：用明确的内网域名后缀 + 条件转发，避免走公网 DNS
#   zone "corp.example" { type forward; forwarders { 192.0.2.53; }; };
```

**复盘与预防**
1. **企业内网绝不应该把公网 DNS 直接下发给终端**。正确架构是：
   终端只配内网 DNS，内网 DNS 负责转发公网查询——这样内网域名的解析完全可控。
2. 排查 DNS 问题时，`dig @指定服务器` 是最有效的对比手段——它能明确告诉你
   「是哪个服务器给了错误答案」，而不是笼统地「DNS 有问题」。
3. 注意区分 `NXDOMAIN`（明确不存在，会被负缓存）和超时（会重试）——前者危害更大。

---

### 案例 08 · TCP 半开与 CLOSE_WAIT 堆积

**现象**
某 Java 应用运行几天后响应变慢，最终完全无法建立新连接。
重启应用后立即恢复，几天后重现。

**影响范围**：单个应用服务，但会导致整条业务链不可用。

**现场采集**

```bash
# 看连接状态分布——这是排障最关键的一步
$ ss -tan | awk 'NR>1 {print $1}' | sort | uniq -c | sort -rn
   6821 CLOSE-WAIT        ← 异常：数量巨大
    312 ESTAB
     48 TIME-WAIT
     12 LISTEN

# 看这些 CLOSE_WAIT 指向谁
$ ss -tan state close-wait | head -5
Recv-Q Send-Q  Local Address:Port   Peer Address:Port
0      0       192.0.2.10:8080      198.51.100.7:51234
0      0       192.0.2.10:8080      198.51.100.8:51002
...

# 看进程的文件描述符数量
$ ls /proc/12345/fd | wc -l
10214                                    ← 接近 ulimit -n 的上限
$ ulimit -n
10240                                    ← 到顶了，所以新连接建不了
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 遭受连接洪水攻击 | 看来源 IP 分布 | **排除**——都是正常业务方 IP |
| 2 | 服务端主动断开连接 | 抓包看谁先发 FIN | **排除/确认**——是**对端先发 FIN**，本端回了 ACK 但从未发自己的 FIN |
| 3 | 应用代码没关闭连接 | 检查连接池配置与代码 | **确认**——下游响应异常时未在 finally 中 close |

**根因**
对端（下游服务）超时主动关闭连接（发 FIN），本端内核回复 ACK——
此时连接进入 `CLOSE_WAIT`，**等着应用层调用 `close()`**。
但应用的代码只在正常路径上关闭连接，一旦下游返回异常就走到了异常分支，
连接对象既没被关闭也没被复用，永久停留在 `CLOSE_WAIT`。
日积月累耗尽文件描述符，最终 `accept()` 失败，服务彻底不可用。

**修复步骤**

```bash
# 应急：把文件描述符上限调高（治标）
$ sudo sysctl -w fs.file-max=2097152
$ ulimit -n 65535

# 更快的应急：重启应用（但要注意，这只是把倒计时重置）
```

真正的修复在应用侧：

```java
// 错误写法：异常路径漏掉了关闭
Connection conn = pool.getConnection();
try {
    conn.execute(sql);
    conn.close();
} catch (SQLException e) {
    log.error("执行失败", e);      // 连接泄漏了
}

// 正确写法：finally 保证归还/关闭
try (Connection conn = pool.getConnection()) {   // try-with-resources
    conn.execute(sql);
} catch (SQLException e) {
    log.error("执行失败", e);
}
```

**复盘与预防**
1. **`CLOSE_WAIT` 是应用层的问题，不是网络的问题**。看到它堆积就去查代码，
   别去调 TCP 参数（`TIME_WAIT` 才是可以通过内核参数调整的）。
2. 监控上必须加：`ss -tan state close-wait | wc -l` 与文件描述符使用率。
   两者都在达到阈值前给出预警。
3. 连接池必须配置「借出超时」与「最大连接数」，并开启泄漏检测
   （如 HikariCP 的 `leakDetectionThreshold`）。

---

### 案例 09 · NAT 会话表耗尽：内网用户间歇性「断网」

**现象**
办公网 500 多人，下午高峰期（14:00—16:00）部分用户网页打不开，
表现为「一直转圈最后超时」；刷新几次偶尔能打开。非高峰期完全正常。

**影响范围**：全体用户，但只有高峰期、且是间歇性的。

**现场采集**

```bash
# 出口路由器上看 NAT 会话数
R1# show ip nat statistics
Total active translations: 63842 (1200 static, 62642 dynamic)
Peak translations: 65400, occurred 00:00:12 ago
Outside interfaces: GigabitEthernet0/0
Inside interfaces: GigabitEthernet0/1
Hits: 128374621  Misses: 1874               ← Miss 持续增长

# 看端口利用情况
R1# show ip nat translations | count
Number of lines which match regexp = 63842

# 可用公网地址与端口上限：
#   3 个公网地址 × 64512 个可用端口 = 193,536 —— 理论够用
#   但短连接大量堆积 TIME_WAIT 占用端口，实际可用数远低于理论值
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 运营商链路故障 | 看接口错误计数与告警 | **排除**——链路正常 |
| 2 | 出口带宽打满 | 看接口速率 | **部分确认**——带宽用到 80%，但未打满 |
| 3 | NAT 会话/端口耗尽 | `show ip nat statistics` | **确认**——峰值达 65400，Miss 增长 |
| 4 | 谁占用了大量会话 | 看会话表的前几大来源 | **确认**——某几台机器各开了上万个连接（P2P 下载） |

**根因**
两个因素叠加：① 内网有终端在跑 P2P 或大量短连接应用，占用大量 NAT 端口；
② 出口只配了 3 个公网地址，端口池在高并发下被耗尽，新连接无法建立 DNAT 映射，
表现为「超时」而不是「拒绝」（因为丢在映射阶段，没有 RST 返回）。

**修复步骤**

```bash
# 应急：扩大公网地址池，并把 TCP 会话老化时间缩短
R1(config)# ip nat pool PUBLIC 203.0.113.10 203.0.113.20 netmask 255.255.255.0
R1(config)# ip nat inside source list 10 pool PUBLIC overload
R1(config)# ip nat translation tcp-timeout 300      # 默认 86400，缩到 5 分钟

# 治理：找出异常终端
R1# show ip nat translations | awk '{print $5}' | sort | uniq -c | sort -rn | head
# 或者在交换机上统计各端口的会话数

# 在接入层限制每端口的连接数
SW1(config)# interface GigabitEthernet0/5
SW1(config-if)# storm-control broadcast level 2
```

**复盘与预防**
1. 出口设计时要按「并发会话数」而不是「带宽」来估算 NAT 规模。
   经验值：每用户高峰 300~500 个并发会话。500 人 → 15 万~25 万会话。
2. 上线**连接数监控**：NAT 会话数占端口池的比例超过 70% 就告警。
3. 缩短 NAT 的老化时间（尤其对 TCP），并在终端侧限制 P2P / 异常连接行为。

---

### 案例 10 · Wi-Fi 漫游掉线：走动时视频会议必然中断

**现象**
员工拿着笔记本在办公区走动时，视频会议每次经过走廊就断 3~5 秒，
固定坐在工位上则完全正常。

**影响范围**：无线用户，仅在跨 AP 移动时。

**现场采集**

```bash
# 看终端的漫游记录（macOS）
$ log show --predicate 'subsystem == "com.apple.wifi"' --last 10m | grep -i roam

# 从无线控制器看 AP 分布与信道
WLC# show ap summary
AP Name    IP           Channel   Clients   Noise(dBm)   Util(%)
AP-3F-01   192.0.2.21   36        18        -92          62          ← 2.4G？信道利用率过高
AP-3F-02   192.0.2.22   36        22        -90          58          ← 与上一个同信道！
AP-3F-03   192.0.2.23   11        25        -88          71          ← 2.4G 拥挤

# 看是否有漫游相关的日志
WLC# show client detail <MAC>
  Client Roam Count: 47
  Client Last Roam: 2 minutes ago
  Client Roam Reason: Poor Signal Quality
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 终端无线网卡故障 | 换一台笔记本测试 | **排除**——同样现象 |
| 2 | 信号覆盖不足 | 看各 AP 的信号强度 | **部分确认**——走廊区域信号弱 |
| 3 | 相邻 AP 同信道互相干扰 | 看信道规划 | **确认**——同楼层多个 AP 都用信道 36 |
| 4 | 漫游阈值设置不合理 | 看漫游参数 | **确认**——只能在信号极差时才触发漫游，且切换耗时长 |

**根因**
三个问题叠加：① 同一区域多个 AP 使用相同信道（36），造成同频干扰，
终端实际可用带宽被压缩，并出现丢包；② 漫游触发阈值过低（如 -75dBm 才漫游），
终端一直「粘」在弱信号的 AP 上直到几乎失联才切换；
③ 漫游过程包含完整的 802.11 认证与 4 次握手，未启用快速漫游（802.11r），
导致切换耗时长，视频会议就断在这几秒里。

**修复步骤**

```bash
# 1. 信道重新规划：相邻 AP 必须错开（5G 用 36/44/52/60/100/108… 非重叠）
WLC# config ap channel 36 AP-3F-01
WLC# config ap channel 44 AP-3F-02
WLC# config ap channel 52 AP-3F-03
WLC# config 802.11a channel global auto        # 或交给自动信道选择

# 2. 提高漫游敏感度（让终端更早切换到信号更好的 AP）
WLC# config advanced 802.11a client roaming aggressive

# 3. 启用 802.11r 快速漫游（FT），把切换时间从数百毫秒压到 50ms 以内
WLC# config wlan security ft enable 1

# 4. 补盲：走廊区域增加 AP 或调整现有 AP 的天线与功率
```

**复盘与预防**
1. 无线网络的设计是**三维**的：覆盖（信号强度）、容量（并发用户数）、干扰（信道规划），
   三者缺一不可。只看「信号满格」是不够的。
2. 语音 / 视频类业务对漫游时间敏感，必须上 802.11r 并把目标定在 **50ms 以内**。
3. 定期做**信道利用率扫描**——利用率超过 50% 就该考虑优化或增加 AP。
4. 用手机 App（如 Wi-Fi 分析仪）实际走一遍办公区，画出信号热力图，比看配置更直观。

---

### 案例 11 · DHCP 地址池耗尽：新接入的设备拿不到 IP

**现象**
某会议室新装的 20 台设备全部拿不到 IP，显示 `169.254.x.x`（APIPA 地址）。
但会议室的网口以前是正常的。

**影响范围**：单个 VLAN 内的新设备。

**现场采集**

```bash
# 看地址池使用情况
R1# show ip dhcp pool MEETING
Pool MEETING:
 Utilization mark (high/low)    : 100 / 0
 Subnet size (first/next)       : 0 / 0
 Total addresses                : 254
 Leased addresses               : 254        ← 满了
 Pending event                  : none
 1 subnet is currently in the pool :
 Current index        IP address range               Leased/Excluded/Total
 192.0.2.0            192.0.2.1 - 192.0.2.254       254 / 0 / 254      ← 全部租出

# 看谁在用
R1# show ip dhcp binding | head -20
IP address       Client-ID/Hardware address     Lease expiration   Type
192.0.2.11       0100.0c29.ab12                Sep 20 2026 10:03  Automatic
...
# 统计各 MAC 前缀的占用
R1# show ip dhcp binding | awk '{print $2}' | cut -c1-8 | sort | uniq -c | sort -rn | head
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | DHCP 服务故障 | 看进程与日志 | **排除**——服务正常，只是没地址可发 |
| 2 | 中继配置丢失 | `show run interface` 看 helper-address | **排除**——配置在 |
| 3 | 地址池耗尽 | `show ip dhcp pool` | **确认**——254/254 全部租出 |
| 4 | 为什么耗尽 | 看占用者的 MAC 与租期 | **确认**——大量绑定来自 MAC 随机化的设备，且租期设成了 7 天 |

**根因**
两个原因叠加：① 租期设得过长（7 天），设备离开会议室后地址仍被占用很久；
② 现代手机 / 笔记本默认开启 **MAC 地址随机化**，同一台设备每次连接会申请新地址，
短时间内就把地址池刷满。21 个网口的会议室配了 254 个地址，看起来绰绰有余，实际上远远不够。

**修复步骤**

```bash
# 1. 缩短租期（会议室类场景设 2~8 小时）
R1(config)# ip dhcp pool MEETING
R1(config-dhcp)# lease 0 4 0            # 0 天 4 小时 0 分

# 2. 清理无用的绑定记录（谨慎操作）
R1# clear ip dhcp binding *

# 3. 扩大地址池（换更大的子网，如 /23）
R1(config)# no ip dhcp pool MEETING
R1(config)# ip dhcp pool MEETING
R1(config-dhcp)# network 192.0.2.0 255.255.254.0

# 4. 若需保留稳定地址给打印/门禁等设备，用静态绑定 + 排除段
R1(config)# ip dhcp excluded-address 192.0.2.1 192.0.2.50
R1(config)# ip dhcp pool PRINTER
R1(config-dhcp)# host 192.0.2.20 255.255.255.0
R1(config-dhcp)# hardware-address 0200.0000.000a
```

**复盘与预防**
1. **地址池容量要按「设备数 × 1.5~2 倍」规划**，MAC 随机化时代的实际需求远高于设备数。
2. 租期按场景区分：办公区 8 小时、会议室 2~4 小时、访客 1~2 小时、固定设备静态绑定。
3. 监控 DHCP 池使用率，超过 80% 告警——等到 100% 就已经有用户受影响了。

---

### 案例 12 · BGP 邻居震荡：跨运营商专线反复中断

**现象**
与运营商的 BGP 邻居每十几分钟断开重连一次，断开期间备线自动接管（业务不中断），
但日志里大量告警，切换时业务有抖动。

**影响范围**：总出口，影响了业务稳定性与告警噪音。

**现场采集**

```bash
R1# show ip bgp summary
Neighbor        V    AS  MsgRcvd MsgSent  TblVer  InQ OutQ Up/Down   State/PfxRcd
203.0.113.1     4 65001  18420   18435     1201    0    0 00:04:32  1024
                                                       ↑ 只有 4 分钟，说明刚重启过

R1# show log | include BGP
%BGP-5-ADJCHANGE: neighbor 203.0.113.1 Down BGP Notification sent
%BGP-3-NOTIFICATION: sent to neighbor 203.0.113.1 4/0 (hold time expired) 0 bytes
%BGP-5-ADJCHANGE: neighbor 203.0.113.1 Up
                                ↑ 关键：4/0 = hold time expired

# 什么原因导致 hold timer 超时？看链路质量
$ ping -c 100 -i 0.2 203.0.113.1 | tail -3
100 packets transmitted, 97 received, 3% packet loss, time 20000ms
rtt min/avg/max/mdev = 12.3/45.8/892.1/120.4 ms
                  ↑ 抖动巨大，最大 892ms
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | 对端设备重启 | 看对端日志 | **排除**——对端无重启记录 |
| 2 | BGP 认证配置错误 | 看 notification 的 code | **排除**——code 是 hold time expired，不是认证失败 |
| 3 | 底层链路质量差导致保活丢失 | 长时间 ping / mtr | **确认**——3% 丢包 + 抖动高达 892ms |
| 4 | 丢包原因 | 查运营商侧与物理链路 | **确认**——专线的光衰接近门限，误码导致随机丢包 |

**根因**
物理层质量问题（光衰接近门限）导致随机丢包，BGP 的 KEEPALIVE 报文丢失后
Hold Timer（默认 180 秒）超时，邻居中断。恢复后重新建立邻居、重新收敛，
如此循环形成震荡。

**修复步骤**

```bash
# 1. 报修运营商，检查光路衰减（根本解法）
#    同时在本端记录证据：光功率、误码计数
$ sudo ethtool -m eth0                      # 读光模块的收发光功率
R1# show interfaces GigabitEthernet0/0 transceiver | include optical

# 2. 缓解：适当延长 BGP 计时器，避免偶发丢包直接导致邻居中断
R1(config)# router bgp 65002
R1(config-router)# neighbor 203.0.113.1 timers 10 30
#                                      Keepalive=10s Hold=30s   ← 更快感知，但不解决震荡

# 3. 更好的做法：启用 BFD，把故障检测从"秒级"提到"毫秒级"，
#    让流量在邻居真正中断前就切走
R1(config)# neighbor 203.0.113.1 fall-over bfd
R1(config)# bfd interval 300 min_rx 300 multiplier 3

# 4. 若是链路质量不可控，考虑路由阻尼（防止反复通告影响其他 AS）
R1(config)# bgp dampening 15 750 2000 60
```

**复盘与预防**
1. **BGP 邻居震荡的根因几乎总在物理层或底层 IGP**，不要在 BGP 参数上找答案。
   Notification code `4/0` 明确指向 hold time expired，就该去看链路质量。
2. 关键链路要开 **BFD**——它比 BGP 的保活机制快得多，能在 1 秒内检测到故障。
3. 长期监控链路质量指标（丢包率、抖动、光功率），在达到告警阈值前处理。
4. 别乱用小 Keepalive/Hold 计时器——太短会因偶发抖动频繁中断，反而更不稳。

---

### 案例 13 · 链路聚合不生效：带宽没翻倍反而更差

**现象**
为提升服务器上行带宽，把 4 个千兆口做了链路聚合（LACP），
但实测 `iperf3` 单线程速度仍然只有 940Mbps，没有翻倍。

**影响范围**：单条服务器链路。

**现场采集**

```bash
# 确认聚合组确实起来了
SW1# show etherchannel summary
Group  Port-channel  Protocol  Ports
1      Po1(SU)         LACP      Gi0/1(P) Gi0/2(P) Gi0/3(P) Gi0/4(P)     ← 四个口都正常

# 服务器侧确认
$ cat /proc/net/bonding/bond0 | grep -E 'Bonding Mode|MII Status|Slave Interface'
Bonding Mode: IEEE 802.3ad Dynamic link aggregation
MII Status: up
Slave Interface: eth1  ... MII Status: up
Slave Interface: eth2  ... MII Status: up
Slave Interface: eth3  ... MII Status: up
Slave Interface: eth4  ... MII Status: up

# 关键：看单条会话实际走了哪个成员口
$ cat /proc/net/bonding/bond0 | grep -A2 'Slave Interface: eth1'
Slave Interface: eth1
MII Status: up
...
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | LACP 没协商成功 | 看聚合组状态 | **排除**——4 个口都是 P（在组内） |
| 2 | 其中某个口协商速率不对 | 逐个口看速率 | **排除**——都是 1000M/Full |
| 3 | 哈希算法导致单会话走单口 | 多线程并发测试 | **确认**——`iperf3 -P 8` 达到 3.6Gbps |
| 4 | 是否有个别链路空转 | 看各成员口的流量统计 | **确认**——只有 2 个口有流量 |

**根因**
链路聚合（无论 LACP 还是静态）的负载分担都是**按流（flow）哈希**，不是按包轮询。
默认哈希算法（如「源 MAC」或「源+目的 MAC」）对于「单客户端 ↔ 单服务器」的场景，
四个成员口算出来的哈希值**完全相同**，所以这条会话永远只走一个口——
带宽上限就是一个千兆口的速度。这是链路聚合最容易被误解的地方。

**修复步骤**

```bash
# 换成更细粒度的哈希算法（加入 L3/L4 信息，让不同会话分散）
SW1(config)# port-channel load-balance src-dst-ip-l4port
# 华为：load-balance src-dst-ip-l4port
# Linux bond：xmit_hash_policy layer3+4

# 服务器侧同步修改
$ echo 'layer3+4' | sudo tee /sys/class/net/bond0/bonding/xmit_hash_policy

# 验证：单会话仍走单口（这是正常的），但多会话会分散
$ iperf3 -c 192.0.2.80            # 单流：~940Mbps  ← 符合预期
$ iperf3 -c 192.0.2.80 -P 8       # 8 流：~3.6Gbps   ← 并行才用满
```

**复盘与预防**
1. **链路聚合不等于「单条连接变快」**，它解决的是「多会话总吞吐」。
   需要单条连接跑满多口带宽的场景，只能靠多路径（如 ECMP + 多流）或更高速率的单口。
2. 部署后用**多流测试**验证（`iperf3 -P 8`），单流测试只能验证「有没有跑满一个口」。
3. 不对称的会话要特别留意：客户端多而服务器单一时，哈希容易倾斜——
   这种情况优先选带 L4 端口的哈希算法。

---

### 案例 14 · 容器网络不通：跨节点 Pod 无法通信

**现象**
K8s 集群中，同一个 Deployment 的两个副本分布在不同节点，
互相 `curl` 对方 Pod IP 超时；同一节点内的 Pod 互相访问正常。

**影响范围**：跨节点的 Pod 间通信；Service 访问也因此间歇失败（取决于流量落到哪个 Pod）。

**现场采集**

```bash
# 1. 确认 Pod 状态与分布
$ kubectl get pods -o wide
NAME                    READY   STATUS    IP           NODE
web-7d4b8f9c5-2xk9p     1/1     Running   10.244.1.15  node1
web-7d4b8f9c5-9fzq2     1/1     Running   10.244.2.8   node2

# 2. 在同节点内测试（正常）
$ kubectl exec web-7d4b8f9c5-2xk9p -- ping -c 2 10.244.1.20
2 packets transmitted, 2 received, 0% packet loss          ← 同节点 OK

# 3. 跨节点测试（异常）
$ kubectl exec web-7d4b8f9c5-2xk9p -- ping -c 2 10.244.2.8
2 packets transmitted, 0 received, 100% packet loss

# 4. 看节点上的路由
$ ip route | grep 10.244
10.244.1.0/24 via 10.244.1.0 dev cni0 proto kernel scope link src 10.244.1.1
10.244.2.0/24 via 192.0.2.22 dev eth0                      ← node1 上到 node2 的 Pod 网段路由

# 5. 在 node2 上确认它有没有宣告自己的 Pod 网段
$ kubectl get nodes -o json | jq '.items[] | {name: .metadata.name, podCIDR: .spec.podCIDR}'
{ "name": "node1", "podCIDR": "10.244.1.0/24" }
{ "name": "node2", "podCIDR": null }              ← node2 没有分配 podCIDR！
```

**假设与验证**

| # | 假设 | 验证方法 | 结果 |
|:-:|------|---------|------|
| 1 | CNI 插件异常 | `kubectl get pods -n kube-system` 看 daemonset | **确认**——node2 上的 CNI Pod 处于 CrashLoopBackOff |
| 2 | 节点间物理网络不通 | `ping` 节点 IP | **排除**——节点互通正常 |
| 3 | 节点路由未同步 | 看各节点的路由表 | **确认**——node2 未宣告自己的 Pod 网段 |
| 4 | 为什么 CNI Pod 挂了 | 看 CNI Pod 日志 | **确认**——节点 IPAM 地址池配置错误，反复重启 |

**根因**
node2 上的 CNI 组件因为 IPAM 配置错误一直重启，导致该节点既没有分配 `podCIDR`，
也没有向其他节点宣告自己的 Pod 网段。于是其他节点上根本没有到 `10.244.2.0/24` 的路由，
发往该节点上 Pod 的流量直接被丢弃——表现为跨节点不通，而同节点内因为走本地的 `cni0` 网桥，完全正常。

**修复步骤**

```bash
# 1. 先看 CNI 组件日志定位真正原因
$ kubectl -n kube-system logs <cni-pod-name-on-node2> --tail=50
# 日志里通常能看到 "failed to allocate podCIDR" 或 IPAM 相关错误

# 2. 修正节点的 podCIDR（视 CNI 方案而定）
$ kubectl patch node node2 -p '{"spec":{"podCIDR":"10.244.2.0/24"}}'

# 3. 重启该节点的 CNI 组件，让它重新宣告路由
$ kubectl -n kube-system delete pod <cni-pod-name-on-node2>
$ kubectl -n kube-system delete pod <cni-pod-on-node2>

# 4. 验证路由是否已同步（在 node1 上看）
$ ip route | grep 10.244
10.244.2.0/24 via 192.0.2.22 dev eth0                      ← 出现了

# 5. 端到端验证
$ kubectl exec web-7d4b8f9c5-2xk9p -- ping -c 3 10.244.2.8
3 packets transmitted, 3 received, 0% packet loss          ← 恢复
```

**复盘与预防**
1. **容器网络问题先看「节点路由表」**——跨节点不通，九成是路由没同步。
   `ip route | grep <pod-cidr>` 一眼就能看出来。
2. 部署集群时给每个节点分配固定且连续的 Pod CIDR 段，并保持连续以便聚合。
   规划要点见[第 20 章](../20-网络虚拟化与云网络/README.md)。
3. 监控 CNI 组件的重启次数——它的 CrashLoopBackOff 是集群网络故障的最强信号。
4. 上线前必做的「集群网络体检」：跨节点 Pod 互通、Service 访问、DNS 解析、外网出口，
   四项都过才算验收完成。

---

## 四、症状 → 可能原因 → 首要排查命令

| 症状 | 可能原因（按概率排序） | 首要命令 |
|------|---------------------|---------|
| 完全不通 | 接口 down ｜ VLAN 未放行 ｜ 缺路由 ｜ 防火墙 | `ip -br link show` → `ping 网关` |
| 跨网段不通、同网段通 | 缺默认路由 ｜ 掩码错误 ｜ 网关不可达 | `ip route get <目的IP>` |
| 小包通、大包不通 | **MTU 黑洞** ｜ PMTUD 失效 ｜ 分片被丢 | `ping -s 1472 -M do` + 抓 `icmp[0]=3 and icmp[1]=4` |
| 时通时断、无规律 | **ARP 欺骗** ｜ 环路 ｜ 链路抖动 ｜ IP 冲突 | `arp -a` 反复看 + `mtr -c 100` |
| 周期性地断 | 定时任务 ｜ ARP 老化 ｜ 路由重收敛 ｜ 备份任务占满带宽 | 对比故障时间点与任务计划 |
| 慢但不丢包 | 带宽打满 ｜ 队列拥塞 ｜ 绕路 ｜ 应用层慢 | `mtr` 看哪一跳 RTT 突增 + `iperf3` |
| 丢包率高 | 物理层误码 ｜ 双工不匹配 ｜ 拥塞 | `ethtool -S eth0` 看 CRC 错包 |
| ping 通但服务不能用 | 端口未监听 ｜ 防火墙 ｜ ACL ｜ 服务绑定错误地址 | `nc -zv <IP> <端口>` + `ss -tulnp` |
| 域名解析失败 | DNS 配置 ｜ 负缓存 ｜ 权威服务器故障 | `dig @<服务器> <域名>` 对比 |
| 大量连接堆积 | CLOSE_WAIT（应用）｜ TIME_WAIT（短连接）｜ SYN_RECV（攻击） | `ss -tan \| awk '{print $1}' \| sort \| uniq -c` |
| 新连接建不上 | 端口耗尽 ｜ 会话表满 ｜ 文件描述符耗尽 | `show ip nat statistics` + `ulimit -n` |
| 拿不到 IP | 地址池耗尽 ｜ 中继丢失 ｜ Snooping 误拦 | `show ip dhcp pool` + 抓 DORA |
| 无线频繁掉线 | 信号弱 ｜ 同信道干扰 ｜ 漫游阈值 ｜ 容量不足 | 看信道利用率与漫游日志 |
| 邻居震荡 | 物理层丢包 ｜ 计时器过短 ｜ 认证/ACL 抖动 | 看 Notification 的 code 含义 |
| 带宽不聚合 | 哈希算法 ｜ 单会话 ｜ 成员口配置不一致 | `iperf3 -P 8` 多流测试 |

---

## 五、排障时最容易犯的 10 个错误

| # | 错误 | 正确的做法 |
|:-:|------|-----------|
| 1 | **上来就重启**。重启让「现场」消失，问题会在别处复现，且你永远不知道根因 | 先采集证据（配置备份、日志、抓包），再动手 |
| 2 | **不问「最近改了什么」**。90% 的故障与最近的变更相关 | 第一句话就问变更记录，必要时先回滚再分析 |
| 3 | **只查一端**。看到本端正常就认为对端正常 | 两端配置都看，尤其是 MTU、双工、VLAN 放行这类需要两端一致的项 |
| 4 | **迷信 ping**。ping 通只说明 ICMP 能过，不代表业务正常 | 用 `nc -zv` 测端口、用业务工具端到端验证 |
| 5 | **忽略「时间维度」**。一直不好和时通时断，根因完全不同 | 先确定是「持续」还是「间歇」，是「定时」还是「随机」 |
| 6 | **一次改多个变量**。改完好了也不知道是哪个起的作用，下次还会踩 | 一次只改一个，改完立即验证 |
| 7 | **只看 L3，不看 L2**。很多「路由问题」其实是 VLAN/MAC/STP 问题 | 自底向上：接口 → VLAN → ARP → 路由 |
| 8 | **在生产上无限制 debug/抓包**。可能直接打满 CPU 造成业务中断 | 用镜像口 + 外部抓包；`debug` 必须用 ACL 精确过滤并设时限 |
| 9 | **不记录现场**。改完就忘，无法复盘，同类问题还会再来 | 保留配置备份、抓包文件、命令输出，写进故障单 |
| 10 | **假设自己记得的拓扑是对的**。凭记忆判断「这里应该是通的」 | 每一条路径都用命令验证，不靠记忆 |

### 一个可复用的排障记录模板

```markdown
## 故障单 #20261006-001

**现象**：（一句话说清用户看到什么）
**首次发现时间** / **恢复时间** / **影响时长**：
**影响范围**：（哪些用户、哪些业务、哪些地域）

**变更关联**：故障前 24 小时内的变更记录 —— 有 / 无

**现场采集**（改动前必须完成）：
  - 配置备份：<路径 / 命令>
  - 抓包文件：<路径>
  - 关键命令输出：<粘贴>

**假设与验证**：
  | # | 假设 | 验证方法 | 结果 |

**根因**：（能解释所有现象的那一个原因；如果解释不了全部，说明还没找到根因）

**修复动作**：（命令 / 配置变更，含验证结果）

**复盘**：
  - 直接原因：
  - 根本原因：（流程/设计层面的）
  - 改进措施与责任人：
  - 是否需要补充监控 / 告警 / 检查单：
```

---

## 六、本章示例索引

| 文件 | 一句话说明 | 运行 |
|------|-----------|------|
| `decision_tree.py` | 可运行的排障决策树，按答案分支走到结论，不带参数时自动遍历全部路径 | `python3 decision_tree.py down` |
| `case_replay.py` | 14 个案例的时间线重放，逐条打印证据、假设与结论 | `python3 case_replay.py 4` |

```bash
python3 decision_tree.py                    # 遍历全部决策路径
python3 decision_tree.py down               # 从「完全不通」开始推理
python3 decision_tree.py slow               # 从「慢 / 偶发失败」开始推理
python3 case_replay.py                      # 重放全部 14 个案例的摘要
python3 case_replay.py 4                    # 只看案例 04（MTU 黑洞）
```

---

⬅️ 上一章：[附录 A · 命令速查与工具手册](../21-附录A-命令速查与工具手册/README.md) ｜ 🏠 [返回总目录](../README.md)
