# 附录 A · 命令速查与工具手册

> **一句话定位**：不按「命令叫什么」查表，按「我想做什么」查表——覆盖主机侧（Linux / macOS / Windows）
> 与设备侧（Cisco 风格 / 华为风格）双体系，外加协议号、端口、类型码、掩码等硬数据速查。
> **前置知识**：无 ｜ **难度**：★☆☆ ｜ **建议投入**：不用背，收藏成书签，随查随用

---

## 一、怎么用这份速查表

三种查法：

1. **按场景查**——第二节到第三节按「想看什么 / 想改什么」组织，这是最高频的用法。
2. **按故障查**——第十四节是「症状 → 首要命令」的反查表，排障时先看这里。
3. **按数据查**——第六节到第十三节是硬数据表（端口、协议号、类型码、保留地址、掩码），写文档和做题时查。

**三个使用原则**：

| 原则 | 说明 |
|------|------|
| 先看状态再改配置 | 任何变更前先 `show`/`display` 一次，留个「变更前基线」，出事了能对比 |
| 命令会忘很正常 | 记住「我要达到什么效果」+ 会用 `?`（Cisco）/ `Tab` 补全（华为），比背命令有用 |
| 同一件事至少会两种做法 | 主机侧和网络侧各一套；出了问题才能判断「是本机的问题还是网络的问题」 |

**标注约定**：`⚠ macOS 差异` 表示该命令在 macOS 上参数或行为不同；`▸ 设备侧` 表示需要登录设备执行。

---

## 二、主机侧命令总表

### 2.1 看接口与链路状态

```bash
# Linux —— 最常用
ip -br link show                 # 一眼看所有接口的 UP/DOWN 与 MAC
ip -s link show eth0             # 加 -s 看收发包、错包、丢包统计
ethtool eth0                     # 看协商速率/双工/光模块（双工不匹配必查）
ethtool -S eth0 | grep -i err    # 看底层错误计数（CRC 错、丢包）

# macOS
ifconfig -a                      # 接口列表（en0 通常是有线/无线）
networksetup -listallhardwareports   # 接口名与硬件对应关系
ifconfig en0 | grep media        # 看链路速率与双工

# Windows
ipconfig /all                    # 含 MAC、DHCP、DNS、租期
netsh interface show interface   # 接口状态清单
```

### 2.2 配置 IP 地址与路由（临时改，重启即失效）

```bash
# Linux
sudo ip addr add 192.0.2.10/24 dev eth0
sudo ip addr del 192.0.2.10/24 dev eth0
sudo ip link set eth0 up
sudo ip route add 198.51.100.0/24 via 192.0.2.1
sudo ip route del default

# macOS
sudo ifconfig en0 inet 192.0.2.10/24 alias
sudo route add -net 198.51.100.0/24 192.0.2.1
sudo route delete default

# Windows（管理员）
netsh interface ip set address "以太网" static 192.0.2.10 255.255.255.0 192.0.2.1
route add 198.51.100.0 mask 255.255.255.0 192.0.2.1
```

### 2.3 看路由表

```bash
ip route show                    # Linux：看默认网关、每条的 scope 与 metric
ip route get 192.0.2.80          # 【排障神器】直接问「去这个地址会走哪条路由、从哪个口出」
netstat -rn                      # macOS / Linux 通用
route -n get default             # macOS：看默认路由走哪个接口
route print                      # Windows
traceroute -n 192.0.2.80         # 顺带看路径（见 2.8）
```

`ip route get` 是排查「为什么走了这条路由」最直接的手段——它会把最长前缀匹配的结果、
出接口、源地址选择一次性告诉你：

```bash
$ ip route get 198.51.100.7
198.51.100.7 via 192.0.2.1 dev eth0 src 192.0.2.10 uid 1000
    cache
```

### 2.4 看 ARP / 邻居表

```bash
ip neigh show                    # Linux
arp -a                           # macOS / Linux / Windows 通用
ip neigh flush all               # Linux：清空 ARP 缓存（排查 ARP 欺骗时用）

# 看一个 IP 的 MAC 是不是在反复变（ARP 欺骗的典型特征）
watch -n 1 'ip neigh show 192.0.2.1'      # Linux
```

### 2.5 看连接与端口占用

```bash
ss -tulnp                        # Linux：t=tcp u=udp l=listen n=数字 p=进程
ss -tan state established        # 只看已建立的连接
ss -s                            # 连接数统计摘要（看 TIME_WAIT 堆积很有用）
lsof -i :8080                    # macOS / Linux：谁占用了 8080
netstat -ano                     # Windows：-o 显示 PID，再 tasklist 找进程

# 看各 TCP 状态的数量分布（排障必备）
ss -tan | awk '{print $1}' | sort | uniq -c | sort -rn | head
```

### 2.6 连通性测试

```bash
ping -c 4 192.0.2.1              # 基本连通性
ping -c 4 -s 1472 -M do 192.0.2.1   # Linux：不分片发 1472+28=1500 字节，测 MTU
ping -c 4 -s 1472 -D 192.0.2.1      # ⚠ macOS：-D 等价于 Linux 的 -M do
ping -6 -c 4 2001:db8::1            # IPv6
ping -I eth1 192.0.2.1              # 指定出接口
ping -c 4 fe80::1%eth0              # IPv6 链路本地地址必须带 %接口

nc -zv 192.0.2.80 443             # 测端口是否开放（TCP）
nc -zuv 192.0.2.80 53             # 测 UDP 端口（结果不如 TCP 可靠）
```

### 2.7 DNS 查询

```bash
dig example.com                    # 完整答案（含 ANSWER/查询时间/TTL）
dig +short example.com             # 只要结果
dig @8.8.8.8 example.com           # 指定 DNS 服务器（对比不同服务器结果）
dig example.com MX                 # 查指定记录类型
dig +trace example.com             # 【学习神器】从根开始逐级迭代，看清解析链
dig -x 192.0.2.80                  # 反向解析（PTR）
dig +norecurse example.com         # 关闭递归（模拟迭代查询）
nslookup example.com               # 老工具，Windows 上也能用
host example.com                   # 最简输出
scutil --dns                       # ⚠ macOS：看本机 DNS 配置与解析顺序
```

### 2.8 路由追踪与路径分析

```bash
traceroute -n 192.0.2.80           # 逐跳（-n 不解析域名，快很多）
traceroute -T -p 443 192.0.2.80    # 用 TCP SYN 探测（穿过屏蔽 ICMP 的防火墙）
traceroute -I 192.0.2.80           # 用 ICMP 探测
tracert 192.0.2.80                 # Windows
mtr -n -c 100 192.0.2.80           # 【推荐】持续探测并统计每跳丢包率
mtr --tcp --port 443 -n 192.0.2.80 # mtr 的 TCP 模式
```

`mtr` 比 `traceroute` 更适合排障——它能看到**中间某跳的丢包率**，
从而区分「这一跳自己丢包」和「这一跳之后的路径丢包」：

```
$ mtr -n -c 20 198.51.100.7
HOST: pc1              Loss%   Snt   Last   Avg  Best  Wrst StDev
  1.|-- 192.0.2.1       0.0%    20    0.4   0.5   0.3   1.2   0.2
  2.|-- 203.0.113.9     0.0%    20    3.1   3.4   2.9   5.0   0.5
  3.|-- 203.0.113.10   35.0%    20    3.2   3.5   3.0   6.1   0.7   ← 自身限速，后续无丢包
  4.|-- 198.51.100.7    0.0%    20    4.8   5.0   4.5   9.2   0.8   ← 终点正常
```

### 2.9 吞吐与链路质量测试

```bash
# 服务端
iperf3 -s
# 客户端：TCP 上行 10 秒
iperf3 -c 192.0.2.80 -t 10
# UDP 打流（看丢包与抖动，测试 100Mbps）
iperf3 -c 192.0.2.80 -u -b 100M -t 10
# 反向（测下行）
iperf3 -c 192.0.2.80 -R
# 多流并发
iperf3 -c 192.0.2.80 -P 8
```

### 2.10 抓包

```bash
# 最常用的组合：不限流、数字显示、显示二层头、抓 20 个包
sudo tcpdump -i eth0 -nn -e -c 20

# 存成文件给 Wireshark 分析（-s 0 抓完整包长，务必加上）
sudo tcpdump -i eth0 -nn -s 0 -w /tmp/cap.pcap
sudo tcpdump -r /tmp/cap.pcap -nn -c 5     # 回读

# 只看某个会话、并打印十六进制 + ASCII
sudo tcpdump -i eth0 -nn -X 'host 192.0.2.80 and port 443'

# 只看 TCP 标志位为 SYN 的包（找建连失败）
sudo tcpdump -i eth0 -nn 'tcp[tcpflags] & tcp-syn != 0 and tcp[tcpflags] & tcp-ack == 0'

# 限流：只抓头 96 字节，减少落盘
sudo tcpdump -i eth0 -s 96 -w /tmp/heads.pcap
```

### 2.11 应用层验证

```bash
curl -v https://example.com            # 【排障神器】完整展示 TLS 握手与请求响应头
curl -I https://example.com            # 只看响应头（HEAD 请求）
curl -o /dev/null -s -w '%{http_code} %{time_total} %{time_connect}\n' https://example.com
curl --resolve example.com:443:192.0.2.80 https://example.com   # 绕过 DNS 直连指定 IP
curl -x http://127.0.0.1:8080 https://example.com                # 走代理（验证代理是否生效）
curl --http2 -v https://example.com    # 验证 HTTP/2 协商
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>&1 | head -30
openssl s_client -connect example.com:443 -tls1_3 -brief </dev/null
dig +short example.com                 # 确认 DNS 解析到哪个 IP（再与 curl 结果对照）
```

---

## 三、设备侧命令对照（Cisco / 华为）

### 3.1 基础查看

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 看接口 IP 与状态 | `show ip interface brief` | `display ip interface brief` |
| 看接口速率双工 | `show interfaces status` | `display interface brief` |
| 看接口详细统计 | `show interfaces GigabitEthernet0/1` | `display interface GigabitEthernet0/0/1` |
| 看版本与运行时间 | `show version` | `display version` |
| 看当前配置 | `show running-config` | `display current-configuration` |
| 看启动配置 | `show startup-config` | `display saved-configuration` |
| 保存配置 | `write memory` / `copy run start` | `save` |
| 看 MAC 地址表 | `show mac address-table` | `display mac-address` |
| 看设备日志 | `show logging` | `display logbuffer` |
| 进入配置模式 | `configure terminal` | `system-view` |
| 关闭域名解析提示 | `no ip domain-lookup` | `undo info-center enable` 或 `undo dns resolve` |

### 3.2 VLAN 与 Trunk

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 创建 VLAN | `vlan 10` → `name OFFICE` | `vlan 10` → `name OFFICE` |
| 看 VLAN 列表 | `show vlan brief` | `display vlan` |
| 接口划入 VLAN | `switchport mode access` + `switchport access vlan 10` | `port link-type access` + `port default vlan 10` |
| 配 Trunk | `switchport mode trunk` + `switchport trunk allowed vlan 10,20` | `port link-type trunk` + `port trunk allow-pass vlan 10 20` |
| 看 Trunk 状态 | `show interfaces trunk` | `display port vlan` |
| 改 PVID（native VLAN） | `switchport trunk native vlan 99` | `port trunk pvid vlan 99` |

**必须记住的收发规则**（[第 04 章](../04-以太网与交换技术/README.md)详解）：

| 端口类型 | 收到无标签帧 | 收到有标签帧 | 发出时 |
|---------|------------|------------|--------|
| Access | 打上 PVID 标签，转发 | 标签 = PVID 则收，否则丢弃 | **剥掉**标签发出 |
| Trunk | 打上 PVID 标签（Native VLAN） | 在允许列表内则收，否则丢弃 | 允许列表内且 ≠ PVID 则**带标签**发；= PVID 则剥标签发 |

### 3.3 STP

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 看生成树状态 | `show spanning-tree` | `display stp brief` |
| 看详细拓扑 | `show spanning-tree detail` | `display stp` |
| 指定根桥 | `spanning-tree vlan 10 root primary` | `stp root primary` |
| 改优先级 | `spanning-tree vlan 10 priority 4096` | `stp priority 4096` |
| 改端口开销 | `spanning-tree vlan 10 cost 100` | `stp cost 100` |
| 边缘端口（接终端） | `spanning-tree portfast` | `stp edged-port enable` |
| 开启 RSTP | `spanning-tree mode rapid-pvst` | `stp mode rstp` |

### 3.4 链路聚合

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 创建聚合组 | `interface Port-channel 1` | `interface Eth-Trunk 1` |
| 加入成员口 | 成员口下 `channel-group 1 mode active` | 成员口下 `eth-trunk 1` |
| 看聚合状态 | `show etherchannel summary` | `display eth-trunk 1` |
| 配 LACP 模式 | `mode active`（主动）/ `mode passive` | `mode lacp-static` |
| 改哈希算法 | `port-channel load-balance src-dst-ip` | `load-balance src-dst-ip` |

> ⚠ 同一聚合组内成员口的**速率、双工、VLAN 配置必须一致**，否则成员口会被踢出组（表现为带宽不升反降）。

### 3.5 静态路由与 OSPF

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 配静态路由 | `ip route 198.51.100.0 255.255.255.0 192.0.2.1` | `ip route-static 198.51.100.0 24 192.0.2.1` |
| 配默认路由 | `ip route 0.0.0.0 0.0.0.0 192.0.2.1` | `ip route-static 0.0.0.0 0 192.0.2.1` |
| 浮动静态路由 | `ip route ... 192.0.2.1 200`（管理距离 200） | `ip route-static ... preference 200` |
| 指向 null0 丢弃 | `ip route 198.51.100.0 255.255.255.0 null0` | `ip route-static 198.51.100.0 24 NULL0` |
| 看路由表 | `show ip route` | `display ip routing-table` |
| 只看 OSPF 路由 | `show ip route ospf` | `display ospf routing` |
| 开 OSPF 进程 | `router ospf 1` | `ospf 1 router-id 1.1.1.1` |
| 通告网段 | `network 192.0.2.0 0.0.0.255 area 0` | `area 0` → `network 192.0.2.0 0.0.0.255` |
| 看邻居 | `show ip ospf neighbor` | `display ospf peer brief` |
| 看接口开销 | `show ip ospf interface` | `display ospf interface` |
| 看链路状态库 | `show ip ospf database` | `display ospf lsdb` |
| 改参考带宽 | `auto-cost reference-bandwidth 10000` | `bandwidth-reference 10000` |
| 改接口开销 | `ip ospf cost 10` | `ospf cost 10` |
| 区域类型 | `area 1 stub` / `area 1 nssa` | `area 1` → `stub` / `nssa` |

### 3.6 BGP

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 建邻居 | `neighbor 203.0.113.1 remote-as 65001` | `peer 203.0.113.1 as-number 65001` |
| 指定更新源 | `neighbor 203.0.113.1 update-source Loopback0` | `peer 203.0.113.1 connect-interface Loopback0` |
| 多跳 | `neighbor 203.0.113.1 ebgp-multihop 2` | `peer 203.0.113.1 ebgp-max-hop 2` |
| 通告网段 | `network 192.0.2.0 mask 255.255.255.0` | `network 192.0.2.0 24` |
| 看邻居状态 | `show ip bgp summary` | `display bgp peer` |
| 看 BGP 表 | `show ip bgp` | `display bgp routing-table` |
| 看某前缀详情 | `show ip bgp 192.0.2.0/24` | `display bgp routing-table 192.0.2.0` |
| 改 LOCAL_PREF | `bgp default local-preference 200` / route-map | `default local-preference 200` |
| 改 MED | `set metric 50`（route-map） | `apply cost 50`（route-policy） |
| 路由反射器 | `neighbor x route-reflector-client` | `peer x reflect-client` |
| 重置邻居 | `clear ip bgp 203.0.113.1 soft` | `refresh bgp all import` |

**BGP 邻居卡在 Active 状态的排查顺序**：① `ping` 邻居地址通不通 →
② `telnet 邻居 179` 端口通不通（ACL 是否放过）→ ③ `update-source` 是否配对 →
④ eBGP 默认 TTL=1，跨设备是否配了 `multihop`。

### 3.7 ACL 与 NAT

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 标准 ACL | `access-list 10 permit 192.0.2.0 0.0.0.255` | `acl 2000` → `rule permit source 192.0.2.0 0.0.0.255` |
| 扩展 ACL | `access-list 100 deny tcp any host 192.0.2.80 eq 23` | `acl 3000` → `rule deny tcp destination 192.0.2.80 0 destination-port eq 23` |
| 应用到接口 | `ip access-group 100 in` | `traffic-filter inbound acl 3000` |
| 看 ACL | `show access-lists` | `display acl all` |
| 静态 NAT | `ip nat inside source static 192.0.2.10 203.0.113.10` | `nat static global 203.0.113.10 inside 192.0.2.10` |
| PAT（端口复用） | `ip nat inside source list 10 interface Gi0/0 overload` | `nat outbound 2000` |
| 指定内外接口 | `ip nat inside` / `ip nat outside` | `nat inside` / `nat outside` |
| 看 NAT 会话表 | `show ip nat translations` | `display nat session all` |
| 清 NAT 会话 | `clear ip nat translation *` | `reset nat session all` |

### 3.8 VRRP / HSRP

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 配 VRRP | `vrrp 10 ip 192.0.2.1` | `vrrp vrid 10 virtual-ip 192.0.2.1` |
| 改优先级 | `vrrp 10 priority 120` | `vrrp vrid 10 priority 120` |
| 抢占 | `vrrp 10 preempt` | `vrrp vrid 10 preempt-mode`（默认开） |
| 看状态 | `show vrrp` | `display vrrp` |
| HSRP（思科专有） | `standby 10 ip 192.0.2.1` + `standby 10 priority 120` | 不支持，用 VRRP |

### 3.9 DHCP 与 DNS

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 开 DHCP 池 | `ip dhcp pool OFFICE` | `ip pool OFFICE` |
| 配网段 | `network 192.0.2.0 255.255.255.0` | `network 192.0.2.0 mask 24` |
| 配网关 | `default-router 192.0.2.1` | `gateway-list 192.0.2.1` |
| 配 DNS | `dns-server 192.0.2.53` | `dns-list 192.0.2.53` |
| 排除地址 | `ip dhcp excluded-address 192.0.2.1 192.0.2.20` | `excluded-ip-address 192.0.2.1 192.0.2.20` |
| 看分配情况 | `show ip dhcp binding` | `display ip pool` |
| 开中继 | `ip helper-address 198.51.100.10` | `dhcp select relay` + `dhcp relay server-ip 198.51.100.10` |
| 开 DHCP Snooping | `ip dhcp snooping` | `dhcp snooping enable` |

### 3.10 排障常用

| 想做什么 | Cisco 风格 | 华为风格 |
|---------|-----------|---------|
| 跟踪路由 | `traceroute 192.0.2.80` | `tracert 192.0.2.80` |
| 调试（慎用） | `debug ip packet detail` | `terminal monitor` + `terminal debugging` + `debugging ip packet` |
| 关调试 | `undebug all` / `no debug all` | `undo debugging all` |
| 抓包（部分平台） | `monitor capture ...` | `capture-packet interface ... ` |
| 看 CPU 占用 | `show processes cpu sorted` | `display cpu-usage` |
| 看接口错误计数 | `show interfaces counters errors` | `display interface | include error` |

> ⚠ **`debug` 类命令在生产的核心设备上禁止随意使用**——它会把包送到 CPU 处理，可能直接打满 CPU 造成业务中断。
> 需要抓包请优先用镜像口 + 外部抓包设备。

---

## 四、Wireshark 显示过滤器速查

显示过滤器用于**过滤已抓到的包**（语法与 tcpdump 的捕获过滤器完全不同，别搞混）：

| 目的 | 显示过滤器写法 |
|------|--------------|
| 某个 IP 相关 | `ip.addr == 192.0.2.80` |
| 源 / 目的 | `ip.src == 192.0.2.80` ｜ `ip.dst == 198.51.100.7` |
| 某网段 | `ip.addr == 192.0.2.0/24` |
| 某端口 | `tcp.port == 443` |
| 端口范围 | `tcp.port >= 1 and tcp.port <= 1024` |
| TCP 建连请求 | `tcp.flags.syn == 1 and tcp.flags.ack == 0` |
| TCP 握手全部包 | `tcp.flags.syn == 1` |
| TCP 复位 | `tcp.flags.reset == 1` |
| 重传 | `tcp.analysis.retransmission` |
| 快速重传 | `tcp.analysis.fast_retransmission` |
| 重复 ACK | `tcp.analysis.duplicate_ack` |
| 零窗口 | `tcp.analysis.zero_window` |
| 乱序 | `tcp.analysis.out_of_order` |
| 窗口更新 | `tcp.analysis.window_update` |
| 任何 TCP 异常 | `tcp.analysis.flags` |
| HTTP 请求 | `http.request` |
| GET 请求 | `http.request.method == "GET"` |
| 4xx / 5xx 响应 | `http.response.code >= 400` |
| 某 Host | `http.host contains "example"` |
| DNS 查询 | `dns.qry.name contains "example.com"` |
| DNS 失败 | `dns.flags.rcode == 3`（NXDOMAIN） |
| ICMP 不可达 | `icmp.type == 3` |
| ICMP 超时 | `icmp.type == 11` |
| ARP 请求 / 应答 | `arp.opcode == 1` ｜ `arp.opcode == 2` |
| ARP 重复应答（欺骗特征） | `arp.opcode == 2 and arp.src.proto_ipv4 == 192.0.2.1` |
| 某 MAC | `eth.addr == 02:00:00:00:00:0a` |
| 广播帧 | `eth.dst == ff:ff:ff:ff:ff:ff` |
| VLAN 标签 | `vlan.id == 10` |
| DHCP 交互 | `bootp` |
| TLS 握手 | `tls.handshake.type == 1`（ClientHello） |
| IPv6 邻居发现 | `icmpv6.type == 135 or icmpv6.type == 136` |
| 排除某方向 | `!ip.src == 192.0.2.80` |
| 组合条件 | `ip.addr == 192.0.2.80 and tcp.port == 443 and tcp.flags.syn == 1` |

**「跟着 TCP 流走」**：右键任意 TCP 包 → `Follow` → `TCP Stream`，把一次会话的完整双向数据拼起来。
分析 HTTP、SMTP、MySQL 这类文本协议时这是最快的手段。

**过滤器按钮的颜色判定法**（学习新过滤器时很好用）：在 Wireshark 过滤器栏输入时，
**绿色**=语法正确、**红色**=语法错误、**黄色**=语法对但可能不匹配任何字段。

---

## 五、tcpdump 捕获过滤器（BPF）速查

捕获过滤器在**抓包时就过滤**（省性能、省磁盘），语法是 BPF：

| 目的 | 写法 |
|------|------|
| 某主机 | `host 192.0.2.80` |
| 源 / 目的 | `src 192.0.2.80` ｜ `dst 198.51.100.7` |
| 网段 | `net 192.0.2.0/24` ｜ `net 192.0.2.0 mask 255.255.255.0` |
| 端口 | `port 443` ｜ `portrange 1-1024` |
| 排除端口 | `not port 22` |
| 协议 | `tcp` ｜ `udp` ｜ `icmp` ｜ `icmp6` ｜ `arp` |
| 只抓 SYN | `tcp[tcpflags] & tcp-syn != 0` |
| 只抓 SYN 且非 ACK | `tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn` |
| 只抓 RST | `tcp[tcpflags] & tcp-rst != 0` |
| 只抓 FIN | `tcp[tcpflags] & tcp-fin != 0` |
| 组合 | `host 192.0.2.80 and tcp port 443 and not src net 192.0.2.0/24` |
| 包长范围 | `greater 1000` ｜ `less 64` |
| 含某字节内容的 HTTP GET | `tcp port 80 and tcp[((tcp[12] & 0xf0) >> 2):4] = 0x47455420` |

常用输出参数组合：

```bash
-nn          # 不做任何名字解析（最快，最不容易误解）
-e           # 打印二层头部（看 MAC）
-X           # 十六进制 + ASCII（看报文内容）
-A           # 只打印 ASCII（看 HTTP 文本很方便）
-s 0         # 抓完整包长（默认只抓 262144 字节，其实够；但有些平台默认较短）
-c 100       # 抓够 100 个包就停
-i any       # 抓所有接口（Linux 支持）
-w file.pcap # 落盘
-r file.pcap # 回读
-l           # 行缓冲，配合 grep 实时过滤
```

---

## 六、IANA 常用端口与服务表

| 端口 | 协议 | 服务 | 说明与安全提示 |
|:----:|:----:|------|--------------|
| 20 / 21 | TCP | FTP 数据 / 控制 | 明文传输，**生产环境禁用，改用 SFTP** |
| 22 | TCP | SSH | 远程管理首选；建议改默认端口 + 禁密码登录用密钥 |
| 23 | TCP | Telnet | 全明文，**必须禁用** |
| 25 | TCP | SMTP | 服务器间投递；多数云商封禁出站 25 端口防垃圾邮件 |
| 53 | TCP/UDP | DNS | UDP 用于查询，TCP 用于大响应与区域传送 |
| 67 / 68 | UDP | DHCP 服务端 / 客户端 | 广播交互；需配合 DHCP Snooping 防伪造 |
| 69 | UDP | TFTP | 无认证，仅用于设备引导与固件升级 |
| 80 | TCP | HTTP | 明文 |
| 110 | TCP | POP3 | 明文，改用 995 (POP3S) |
| 123 | UDP | NTP | 可被用于反射放大攻击，需 ACL 限制 |
| 135 / 137 / 138 / 139 | TCP/UDP | RPC / NetBIOS | Windows 老协议，**跨网段应封禁** |
| 143 | TCP | IMAP | 明文，改用 993 |
| 161 / 162 | UDP | SNMP / SNMP Trap | v1/v2c 的 community 明文，**用 v3** |
| 179 | TCP | BGP | 邻居间建连，需 ACL 只放行对端 |
| 389 / 636 | TCP | LDAP / LDAPS | 目录服务 |
| 443 | TCP | HTTPS | TLS 加密的 HTTP |
| 445 | TCP | SMB | **永恒之蓝等漏洞的入口，跨网段必须封禁** |
| 465 / 587 | TCP | SMTPS / Submission | 587 是客户端提交的标准端口，走 STARTTLS |
| 500 / 4500 | UDP | IKE / IPSec NAT-T | VPN 协商与封装 |
| 514 | UDP | Syslog | 明文，可被伪造 |
| 520 | UDP | RIP | 距离矢量路由协议 |
| 636 | TCP | LDAPS | 加密的 LDAP |
| 993 / 995 | TCP | IMAPS / POP3S | 加密的 IMAP / POP3 |
| 1194 | UDP | OpenVPN | 常见 VPN 端口 |
| 1433 | TCP | MS SQL Server | 数据库，**严禁暴露公网** |
| 1521 | TCP | Oracle | 同上 |
| 1723 | TCP | PPTP | 已不安全，弃用 |
| 1812 / 1813 | UDP | RADIUS 认证 / 计费 | 802.1X 的后端 |
| 2049 | TCP/UDP | NFS | 需配合 IP 白名单 |
| 3306 | TCP | MySQL | 严禁暴露公网 |
| 3389 | TCP | RDP | 远程桌面，**暴露公网是勒索病毒的主要入口** |
| 4789 | UDP | VXLAN | Overlay 隧道目的端口 |
| 5060 / 5061 | TCP/UDP | SIP / SIP-TLS | VoIP 信令 |
| 5432 | TCP | PostgreSQL | 严禁暴露公网 |
| 5900 | TCP | VNC | 明文远程桌面，需隧道 |
| 6379 | TCP | Redis | 默认无认证，**暴露即被挖矿** |
| 8080 / 8443 | TCP | HTTP / HTTPS 备选 | 应用常用替代端口 |
| 9200 | TCP | Elasticsearch | 默认无认证，需内网隔离 |
| 11211 | UDP/TCP | Memcached | 无认证，**反射放大攻击的主力** |
| 27017 | TCP | MongoDB | 默认无认证，**暴露即被勒索** |

---

## 七、IP 协议号（Protocol Number）表

IP 首部的「协议」字段（8 位）决定载荷交给谁处理：

| 号 | 协议 | 典型场景 |
|:--:|------|---------|
| 0 | HOPOPT | IPv6 逐跳选项 |
| 1 | ICMP | ping、traceroute、错误报告 |
| 2 | IGMP | 组播组成员管理 |
| 4 | IP-in-IP | 简单隧道 |
| 6 | **TCP** | 面向连接的可靠传输 |
| 17 | **UDP** | 无连接传输 |
| 41 | IPv6 | 6in4 隧道封装的是 IPv6 载荷 |
| 47 | GRE | 通用路由封装，VXLAN 之外的常见隧道 |
| 50 | ESP | IPSec 加密载荷（ICMP 不可达时看这个数） |
| 51 | AH | IPSec 认证头 |
| 58 | ICMPv6 | IPv6 的 ICMP（含 NDP） |
| 88 | EIGRP | 思科专有路由协议 |
| 89 | **OSPF** | OSPF 直接封装在 IP 上，不走 TCP/UDP |
| 103 | PIM | 组播路由协议 |
| 112 | **VRRP** | 虚拟路由冗余协议 |
| 115 | L2TP | 二层隧道 |
| 132 | SCTP | 流控制传输协议（信令网常用） |

> **考试与面试高频点**：OSPF（89）和 VRRP（112）都是**直接封装在 IP 之上**的，不在 TCP/UDP 里；
> 而 RIP（520/UDP）、BGP（179/TCP）、DHCP（67-68/UDP）都有传输层头。这个差异常被拿来出题。

---

## 八、ICMP 类型与代码表

| 类型 | 名称 | 常见代码 | 说明 |
|:----:|------|---------|------|
| 0 | Echo Reply | 0 | ping 的应答 |
| 3 | Destination Unreachable | 0=网络不可达<br>1=主机不可达<br>2=协议不可达<br>3=端口不可达<br>4=需要分片但 DF 置位<br>13=管理过滤 | **排障最常看的报文** |
| 5 | Redirect | 0~3 | 路由器告诉主机换网关，常被用于攻击，应关闭 |
| 8 | Echo Request | 0 | ping 的请求 |
| 9 / 10 | Router Advertisement / Solicitation | 0 | 发现路由器 |
| 11 | Time Exceeded | 0=TTL 超时<br>1=分片重组超时 | **traceroute 就靠这个** |
| 12 | Parameter Problem | 0=指针指示错误 | 首部字段有问题 |
| 13 / 14 | Timestamp Request / Reply | 0 | 已少用 |

**ICMPv6 关键类型**（NDP 的基础）：

| 类型 | 名称 | 作用 |
|:----:|------|------|
| 1 | Destination Unreachable | 不可达 |
| 2 | Packet Too Big | **PMTUD 靠它工作**，通告链路 MTU |
| 3 | Time Exceeded | TTL 超时 |
| 4 | Parameter Problem | 参数错误 |
| 128 / 129 | Echo Request / Reply | ping6 |
| 133 / 134 | Router Solicitation / Advertisement | 主机请求 / 路由器通告，SLAAC 的来源 |
| 135 / 136 | Neighbor Solicitation / Advertisement | **取代 ARP** 的地址解析 |
| 137 | Redirect | 重定向 |

> **ICMP type 3 code 4**（需要分片但 DF 置位）是 MTU 黑洞的直接证据——
> 在 Wireshark 里看到它，就说明路径上某段 MTU 小于本地发出的包长。
> 详见[第 18 章](../18-网络排障与抓包分析/README.md)。

---

## 九、IPv4 保留与私有地址表

| 网段 | 名称 | 用途 | 可否用于公网 |
|------|------|------|:-----------:|
| `0.0.0.0/8` | 本网络 | 源地址，表示「本机」；`0.0.0.0` 表示任意地址 | ❌ |
| `10.0.0.0/8` | 私有地址 A 类 | 企业内网 | ❌ |
| `100.64.0.0/10` | CGNAT | 运营商级 NAT 的地址 | ❌ |
| `127.0.0.0/8` | 回环 | `127.0.0.1` 是本机 | ❌ |
| `169.254.0.0/16` | 链路本地 | DHCP 拿不到地址时自动配置（APIPA） | ❌ |
| `172.16.0.0/12` | 私有地址 B 类 | 即 `172.16.0.0` ~ `172.31.255.255` | ❌ |
| `192.0.0.0/24` | IETF 协议分配 | 特殊用途 | ❌ |
| `192.0.2.0/24` | **TEST-NET-1** | 文档与教学示例（本仓库全用它） | ❌ |
| `192.88.99.0/24` | 6to4 中继 | 已废弃 | ❌ |
| `192.168.0.0/16` | 私有地址 C 类 | 家用与小型办公 | ❌ |
| `198.18.0.0/15` | 基准测试 | 网络设备性能测试 | ❌ |
| `198.51.100.0/24` | **TEST-NET-2** | 文档与教学示例 | ❌ |
| `203.0.113.0/24` | **TEST-NET-3** | 文档与教学示例 | ❌ |
| `224.0.0.0/4` | 组播 | D 类，见[第 11 章](../11-网关冗余与组播/README.md) | 特殊 |
| `240.0.0.0/4` | 保留（原 E 类） | 除 `255.255.255.255` 外全部保留 | ❌ |
| `255.255.255.255/32` | 受限广播 | 只在本网段广播 | ❌ |

**常用组播地址**：

| 地址 | 含义 |
|------|------|
| `224.0.0.1` | 本网段所有主机 |
| `224.0.0.2` | 本网段所有路由器 |
| `224.0.0.5` / `224.0.0.6` | OSPF 的 AllSPFRouters / AllDRouters |
| `224.0.0.9` / `224.0.0.10` | RIPv2 / EIGRP |
| `224.0.0.13` | PIM 路由器 |
| `224.0.1.1` | NTP |

---

## 十、IPv6 地址类型与保留前缀表

| 前缀 | 类型 | 说明 |
|------|------|------|
| `::1/128` | 回环 | 等价于 IPv4 的 127.0.0.1 |
| `::/128` | 未指定 | 地址未配置时使用（类似 0.0.0.0） |
| `::ffff:0:0/96` | IPv4 映射 | 双栈栈内部的 IPv4 表示 |
| `64:ff9b::/96` | NAT64 | 用于 IPv4-IPv6 转换 |
| `2000::/3` | 全球单播 GUA | 公网可路由地址，目前实际只用到 `2000::/4` 附近 |
| `2001:db8::/32` | **文档专用** | 本仓库全部示例用它（RFC 3849） |
| `fc00::/7` | 唯一本地 ULA | 内网地址，类似 IPv4 私有地址 |
| `fe80::/10` | 链路本地 LLA | 每个接口自动生成，只能在本地链路使用 |
| `ff00::/8` | 组播 | 取代 IPv4 的广播 |
| `ff02::1` / `ff02::2` | 所有节点 / 所有路由器 | 链路本地范围 |
| `ff02::1:ff00:0/104` | 请求节点组播 | NS 报文发往的目的地址，由目标地址低 24 位构成 |

---

## 十一、双绞线线序与线缆类型表

**T568B**（最常用，国内工程标准）：

| 线序 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|:----:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 颜色 | 白橙 | 橙 | 白绿 | 蓝 | 白蓝 | 绿 | 白棕 | 棕 |

**T568A**：

| 线序 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|:----:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 颜色 | 白绿 | 绿 | 白橙 | 蓝 | 白蓝 | 橙 | 白棕 | 棕 |

**线缆类型**：

| 类型 | 两端线序 | 用途 |
|------|---------|------|
| 直通线 | 两端同为 B（或同为 A） | 不同类设备互联：PC↔交换机、交换机↔路由器 |
| 交叉线 | 一端 A、一端 B | 同类设备互联：PC↔PC、交换机↔交换机、路由器↔路由器 |
| 全反线（Console 线） | 一端 1-8，另一端 8-1 | 电脑连设备 Console 口做配置 |

> **现代实践**：千兆及以上（1000BASE-T）网卡普遍支持 **Auto MDI/MDIX**，
> 会自动识别并翻转线序，所以直通线可以通用——**但考试仍会考这个区别**。
> 另外千兆以太网 8 芯**全部用于收发**（每对双向），百兆只用 1、2、3、6 四芯。

**双绞线类别**：

| 类别 | 带宽 | 典型速率 | 最大距离 |
|------|:----:|---------|:--------:|
| Cat5 | 100 MHz | 100 Mbps | 100 m |
| Cat5e | 100 MHz | 1 Gbps | 100 m |
| Cat6 | 250 MHz | 1 Gbps（10 Gbps ≤ 55 m） | 100 m |
| Cat6a | 500 MHz | 10 Gbps | 100 m |
| Cat7 | 600 MHz | 10 Gbps | 100 m（需屏蔽） |
| Cat8 | 2000 MHz | 25/40 Gbps | 30 m |

---

## 十二、子网掩码速查表

| 前缀 | 掩码 | 通配符掩码 | 地址总数 | 可用主机数 | 主机位 |
|:----:|------|-----------|:--------:|:----------:|:------:|
| /8 | 255.0.0.0 | 0.255.255.255 | 16,777,216 | 16,777,214 | 24 |
| /9 | 255.128.0.0 | 0.127.255.255 | 8,388,608 | 8,388,606 | 23 |
| /10 | 255.192.0.0 | 0.63.255.255 | 4,194,304 | 4,194,302 | 22 |
| /11 | 255.224.0.0 | 0.31.255.255 | 2,097,152 | 2,097,150 | 21 |
| /12 | 255.240.0.0 | 0.15.255.255 | 1,048,576 | 1,048,574 | 20 |
| /13 | 255.248.0.0 | 0.7.255.255 | 524,288 | 524,286 | 19 |
| /14 | 255.252.0.0 | 0.3.255.255 | 262,144 | 262,142 | 18 |
| /15 | 255.254.0.0 | 0.1.255.255 | 131,072 | 131,070 | 17 |
| /16 | 255.255.0.0 | 0.0.255.255 | 65,536 | 65,534 | 16 |
| /17 | 255.255.128.0 | 0.0.127.255 | 32,768 | 32,766 | 15 |
| /18 | 255.255.192.0 | 0.0.63.255 | 16,384 | 16,382 | 14 |
| /19 | 255.255.224.0 | 0.0.31.255 | 8,192 | 8,190 | 13 |
| /20 | 255.255.240.0 | 0.0.15.255 | 4,096 | 4,094 | 12 |
| /21 | 255.255.248.0 | 0.0.7.255 | 2,048 | 2,046 | 11 |
| /22 | 255.255.252.0 | 0.0.3.255 | 1,024 | 1,022 | 10 |
| /23 | 255.255.254.0 | 0.0.1.255 | 512 | 510 | 9 |
| /24 | 255.255.255.0 | 0.0.0.255 | 256 | 254 | 8 |
| /25 | 255.255.255.128 | 0.0.0.127 | 128 | 126 | 7 |
| /26 | 255.255.255.192 | 0.0.0.63 | 64 | 62 | 6 |
| /27 | 255.255.255.224 | 0.0.0.31 | 32 | 30 | 5 |
| /28 | 255.255.255.240 | 0.0.0.15 | 16 | 14 | 4 |
| /29 | 255.255.255.248 | 0.0.0.7 | 8 | 6 | 3 |
| /30 | 255.255.255.252 | 0.0.0.3 | 4 | 2 | 2 |
| /31 | 255.255.255.254 | 0.0.0.1 | 2 | 2（点对点链路专用，RFC 3021） | 1 |
| /32 | 255.255.255.255 | 0.0.0.0 | 1 | 1（单主机路由） | 0 |

**心算口诀**：记住「**8 位一组，掩码值就是 256 减去这一组的地址数**」。
/26 的第四组掩码 = 256 − 64 = 192；/27 = 256 − 32 = 224。
实际使用时要算「子网步长」：步长 = 256 − 掩码值。比如 /26 的步长是 64，
所以网段边界落在 .0 / .64 / .128 / .192——这比背公式快得多。

更多子网划分练习见[第 06 章](../06-IPv4地址与子网划分/README.md)，或用脚本验证：

```bash
cd ../06-IPv4地址与子网划分
python3 ipcalc.py 192.0.2.130/26
```

---

## 十三、以太网类型字段（EtherType）表

以太网帧头部的「类型」字段（2 字节）标识上层协议：

| 值 | 协议 | 说明 |
|------|------|------|
| `0x0800` | IPv4 | 最常见 |
| `0x0806` | ARP | 地址解析 |
| `0x8035` | RARP | 反向地址解析（已淘汰） |
| `0x8100` | 802.1Q | VLAN 标签（单层） |
| `0x88A8` | 802.1ad | QinQ 外层标签（S-Tag） |
| `0x86DD` | IPv6 | IPv6 流量 |
| `0x8847` | MPLS 单播 | MPLS 标签 |
| `0x8848` | MPLS 组播 | MPLS 组播标签 |
| `0x8863` | PPPoE Discovery | 发现阶段 |
| `0x8864` | PPPoE Session | 会话阶段 |
| `0x88CC` | LLDP | 链路层发现协议 |
| `0x888E` | EAPOL | 802.1X 认证 |

---

## 十四、常见故障与首要命令对照表

| 症状 | 首要排查命令 | 优先怀疑 |
|------|------------|---------|
| 完全不通 | `ip -br link show` → `ping 网关` | 物理层：接口 down、网线、光模块 |
| 同网段通、跨网段不通 | `ip route show` / `ip route get <目的IP>` | 缺默认路由、掩码配错、网关不通 |
| ping 通 IP 但域名不通 | `dig @8.8.8.8 域名` → `cat /etc/resolv.conf` | DNS 服务器配置错误 |
| 大包不通、小包能通 | `ping -s 1472 -M do` | MTU 黑洞、PMTUD 失效（见第 18 章） |
| 时通时断 | `arp -a` 反复看 / `mtr` 持续探测 | ARP 欺骗、IP 冲突、环路 |
| 丢包率高 | `mtr -c 100` + `ethtool -S 接口` | 链路误码、CRC 错包、双工不匹配 |
| 延迟高但没丢包 | `mtr` 看每跳 RTT 突增点 | 队列拥塞、绕路 |
| 网速只有预期一半 | `iperf3 -c` 单流 vs `-P 8` 多流 | 单会话哈希到一条链路、双工不匹配 |
| 交换机端口灯狂闪 | `show interfaces counters errors` | 环路引发的广播风暴 |
| 连不上某个端口 | `nc -zv <IP> <端口>` → `ss -tulnp` | 服务未监听、防火墙拦截 |
| TCP 建连成功但很快断开 | `ss -tan` 看状态 + 抓包看 RST | ACL 拦截后续包、服务端主动拒绝 |
| 大量 CLOSE_WAIT | `ss -tan state close-wait` | 应用没调用 close()，程序 bug |
| 大量 TIME_WAIT | `ss -s` | 短连接过多，考虑连接池或 SO_REUSEADDR |
| 连接建立慢（秒级） | 抓包看握手是否有 1s/3s 延迟 | DNS 超时重试、SYN 重传 |
| VLAN 间不通 | `show vlan brief` / `show interfaces trunk` | Trunk 未放行该 VLAN、PVID 不一致 |
| 无线频繁掉线 | 看 AP 日志与漫游记录 | 信号弱、信道干扰、漫游阈值设置不当 |
| 拿不到 DHCP 地址 | 抓包看是否有 DISCOVER/OFFER | 地址池耗尽、中继未配、Snooping 误拦 |
| BGP 邻居起不来 | `show ip bgp summary` + `telnet 邻居 179` | 路由不可达、ACL 拦 179、TTL 问题 |
| OSPF 邻居卡在 ExStart | `show ip ospf neighbor` | **MTU 不一致**（经典原因）、Router-ID 冲突 |

---

## 十五、本章示例索引

| 文件 | 一句话说明 | 运行 |
|------|-----------|------|
| `port_service_lookup.py` | 端口 / 服务 / 协议查询工具，内置 120+ 条对照表 | `python3 port_service_lookup.py 443` |
| `cheatsheet_audit.py` | 校验本速查表的完整性：每个小节是否都有命令块 | `python3 cheatsheet_audit.py` |

```bash
python3 port_service_lookup.py                # 打印完整对照表
python3 port_service_lookup.py 445            # 按端口号查
python3 port_service_lookup.py bgp            # 按服务名查
python3 cheatsheet_audit.py                   # 审计速查表覆盖率
```

---

⬅️ 上一章：[第 20 章 · 网络虚拟化与云网络](../20-网络虚拟化与云网络/README.md) ｜ ➡️ 下一章：[附录 B · 故障案例与排障决策树](../22-附录B-故障案例与排障决策树/README.md) ｜ 🏠 [返回总目录](../README.md)
