# networking-learning · 网络工程完整知识体系

> 从物理层的比特到云上的 Overlay 网络：**23 章中文笔记 + 81 个零依赖可运行示例 + 五层自动校验**。
> 面向要做网络运维、网络开发、或准备 HCIA/HCIP/HCIE、CCNA/CCNP/CCIE 认证的人。
> 不讲名词解释，只讲**机制、数据、能验证的东西**。

---

## 这个仓库是什么

网络上关于网络工程的资料有两种极端：一种是「OSI 七层分别是物理层、数据链路层……」的名词罗列，
另一种是厂商配置手册。中间那一层——**为什么协议要这么设计、报文第几个字节是什么、
带宽和时延到底谁在拖后腿、抓包看到的现象对应哪个字段**——往往要靠踩坑才学得到。

这个仓库补的就是这一层。每章包含：

- **机制详解**：每个设计都回答「解决什么问题」，不只给结论
- **逐字段的报文解剖**：比特位、长度、默认值、可选值
- **可运行的验证脚本**：零第三方依赖，`python3 xxx.py` 直接跑，输出中文并带结论
- **工程实践与陷阱清单**：真会遇到的问题，含排查手法
- **带公式与代入过程的自测计算题**

---

## 知识地图

```
                    ┌─────────────────────────────────────────────┐
                    │  第 00 章 · 学习路线与知识地图（从这里开始）  │
                    └──────────────────────┬──────────────────────┘
                                           │
   ┌───────────────────────────────────────┼───────────────────────────────────────┐
   │                                       │                                       │
   ▼                                       ▼                                       ▼
【一】基础与分层                     【二】链路层与局域网                    【三】网络层
 01 网络概论与分层模型                03 数据链路层原理                     06 IPv4 地址与子网划分
 02 物理层与传输介质                  04 以太网与交换技术                   07 IPv6 与过渡技术
                                      05 无线局域网 WLAN                    08 路由基础与静态路由
                                                                            09 动态路由 RIP 与 OSPF
                                                                            10 动态路由 IS-IS 与 BGP
                                                                            11 网关冗余与组播
   ┌───────────────────────────────────────┼───────────────────────────────────────┐
   │                                       │                                       │
   ▼                                       ▼                                       ▼
【四】传输层                          【五】应用层                          【六】安全与工程实践
 12 TCP 协议详解                      14 DNS 与 DHCP                        17 网络安全基础
 13 UDP、QUIC 与套接字                15 HTTP 与 Web 协议栈                 18 网络排障与抓包分析
                                      16 运维类应用协议                     19 网络自动化与可编程网络
                                                                            20 网络虚拟化与云网络
   ┌───────────────────────────────────────┴───────────────────────────────────────┐
   ▼                                                                               ▼
 21 附录 A · 命令速查与工具手册                                  22 附录 B · 故障案例与排障决策树
```

**一句话主线**：全程跟着一个数据包走——从你在浏览器敲下回车，到它变成光纤上的光脉冲，
再变回屏幕上的字节。每一章都是这条路上的一个驿站。

---

## 章节总表

| 章 | 标题 | 核心内容 | 难度 | 笔记 | 示例 |
|:--:|------|---------|:----:|:----:|:----:|
| [00](00-学习路线与知识地图/README.md) | 学习路线与知识地图 | 依赖图、三条路线、实验环境搭建、学习方法 | ★☆☆ | 12 KB | 1 |
| **一、基础与分层** | | | | | |
| [01](01-网络概论与分层模型/README.md) | 网络概论与分层模型 | 交换方式、OSI/TCP-IP 模型、封装解封装、性能指标 | ★☆☆ | 27 KB | 3 |
| [02](02-物理层与传输介质/README.md) | 物理层与传输介质 | 介质选型、线序、编码调制、奈氏与香农、信道复用 | ★★☆ | 27 KB | 4 |
| **二、数据链路层与局域网** | | | | | |
| [03](03-数据链路层原理/README.md) | 数据链路层原理 | 成帧、CRC、海明码、停等/GBN/SR、PPP | ★★☆ | 25 KB | 4 |
| [04](04-以太网与交换技术/README.md) | 以太网与交换技术 | 802.3 帧、MAC 学习、VLAN、STP、链路聚合 | ★★☆ | 31 KB | 4 |
| [05](05-无线局域网WLAN/README.md) | 无线局域网 WLAN | 802.11 家族、CSMA/CA、漫游、WPA2/WPA3 | ★★☆ | 29 KB | 4 |
| **三、网络层** | | | | | |
| [06](06-IPv4地址与子网划分/README.md) | IPv4 地址与子网划分 | 掩码、子网划分、VLSM、CIDR 聚合、ARP | ★★☆ | 31 KB | 4 |
| [07](07-IPv6与过渡技术/README.md) | IPv6 与过渡技术 | 地址格式、NDP、SLAAC、双栈与 NAT64 | ★★☆ | 29 KB | 4 |
| [08](08-路由基础与静态路由/README.md) | 路由基础与静态路由 | 路由表、最长前缀匹配、浮动静态、环路与 TTL | ★★☆ | 31 KB | 3 |
| [09](09-动态路由RIP与OSPF/README.md) | 动态路由 RIP 与 OSPF | 距离矢量、计数到无穷、OSPF 状态机/LSA/SPF | ★★★ | 30 KB | 4 |
| [10](10-动态路由IS-IS与BGP/README.md) | 动态路由 IS-IS 与 BGP | TLV、路径属性、BGP 选路 11 步、RR 与联盟 | ★★★ | 32 KB | 4 |
| [11](11-网关冗余与组播/README.md) | 网关冗余与组播 | VRRP/HSRP、IGMP、组播 MAC 映射、PIM-SM | ★★★ | 31 KB | 3 |
| **四、传输层** | | | | | |
| [12](12-TCP协议详解/README.md) | TCP 协议详解 | 首部与选项、状态机、滑动窗口、拥塞控制、RTO | ★★★ | 35 KB | 4 |
| [13](13-UDP-QUIC与套接字/README.md) | UDP、QUIC 与套接字 | 伪首部校验和、可靠 UDP、QUIC 0-RTT、IO 多路复用 | ★★☆ | 32 KB | 4 |
| **五、应用层** | | | | | |
| [14](14-DNS与DHCP/README.md) | DNS 与 DHCP | 报文格式与压缩指针、递归/迭代、DORA、中继 | ★★☆ | 29 KB | 3 |
| [15](15-HTTP与Web协议栈/README.md) | HTTP 与 Web 协议栈 | HTTP/1.1→3、chunked、缓存、TLS 1.3 握手 | ★★☆ | 32 KB | 4 |
| [16](16-运维类应用协议/README.md) | 运维类应用协议 | SMTP/POP3/IMAP、FTP 双连接、NTP、SNMP BER | ★★☆ | 28 KB | 4 |
| **六、安全与工程实践** | | | | | |
| [17](17-网络安全基础/README.md) | 网络安全基础 | 攻击原理、ACL、防火墙、NAT、IPsec、802.1X | ★★★ | 33 KB | 4 |
| [18](18-网络排障与抓包分析/README.md) | 网络排障与抓包分析 | 分层方法论、pcap 解析、BPF、MTU 黑洞 | ★★★ | 27 KB | 4 |
| [19](19-网络自动化与可编程网络/README.md) | 网络自动化与可编程网络 | NETCONF/YANG、配置审计、遥测、意图校验 | ★★★ | 29 KB | 4 |
| [20](20-网络虚拟化与云网络/README.md) | 网络虚拟化与云网络 | VXLAN/EVPN、Overlay MTU、K8s 网络、云 VPC | ★★★ | 32 KB | 4 |
| **附录** | | | | | |
| [21](21-附录A-命令速查与工具手册/README.md) | 附录 A · 命令速查与工具手册 | 主机侧/设备侧命令、过滤器、端口与协议号速查 | ★☆☆ | 参考 | 2 |
| [22](22-附录B-故障案例与排障决策树/README.md) | 附录 B · 故障案例与排障决策树 | 14 个真实故障案例、两套决策树、10 个常见错误 | ★★☆ | 参考 | 2 |

> 难度 ★ 表示概念密度，不代表重要性。所有主线的建议投入见 [第 00 章](00-学习路线与知识地图/README.md)。

---

## 快速开始

不需要装任何东西——所有示例只用 Python 标准库。**唯一要求：Python 3.9+。**

```bash
git clone https://github.com/PhiloKun/networking-learning.git
cd networking-learning

# 跑一章看看（以子网划分为例）
cd 06-IPv4地址与子网划分
python3 ipcalc.py                # 默认演示 192.0.2.130/26
python3 ipcalc.py 10.1.2.3/22    # 也可以传自己的地址
python3 vlsm_splitter.py         # VLSM 划分器

# 回仓库根目录，跑全量自检
cd ..
python3 verify.py
```

### 常用自检命令

```bash
python3 verify.py                # 全部检查（结构/体量/语法/运行/整洁）
python3 verify.py 12 13          # 只检查第 12、13 章
python3 verify.py --syntax       # 只做语法检查（最快）
python3 verify.py --quiet        # 只打印失败项与汇总
```

`verify.py` 会做五层校验，任何一层不过都会返回非 0：

| 层 | 检查内容 |
|:--:|---------|
| 结构 | 23 个章节目录齐全，每章有 `README.md` |
| 体量 | 笔记字节数达标、示例脚本数量达标、README 里引用的 `.py` 真实存在 |
| 语法 | UTF-8 无 BOM，通过 `compile()` |
| 运行 | 逐脚本运行：退出码为 0、输出无 `Traceback`、30 秒内退出 |
| 整洁 | 运行后仓库无残留文件 |

---

## 示例索引（按章）

| 章 | 示例脚本 |
|:--:|---------|
| 00 | `learning_path_planner.py` |
| 01 | `osi_layers_demo.py` · `delay_budget.py` · `layer_mapping.py` |
| 02 | `line_encoding.py` · `shannon_nyquist.py` · `medium_delay.py` · `multiplexing_demo.py` |
| 03 | `crc_calc.py` · `hamming_code.py` · `arq_simulator.py` · `framing_demo.py` |
| 04 | `mac_learning_switch.py` · `vlan_tag.py` · `stp_election.py` · `lag_hash.py` |
| 05 | `csma_ca_sim.py` · `wifi_standard_table.py` · `wpa_psk_derive.py` · `roaming_timeline.py` |
| 06 | `ipcalc.py` · `vlsm_splitter.py` · `cidr_aggregate.py` · `arp_sim.py` |
| 07 | `ipv6_format.py` · `ipv6_subnet.py` · `eui64_gen.py` · `transition_demo.py` |
| 08 | `route_lookup.py` · `static_route_gen.py` · `loop_and_ttl.py` |
| 09 | `rip_convergence.py` · `ospf_cost_spf.py` · `ospf_lsa_types.py` · `dr_bdr_election.py` |
| 10 | `isis_tlv.py` · `bgp_best_path.py` · `bgp_aspath.py` · `bgp_sm.py` |
| 11 | `vrrp_election.py` · `multicast_mapping.py` · `multicast_tree.py` |
| 12 | `tcp_header_lab.py` · `tcp_state_machine.py` · `tcp_congestion.py` · `tcp_rto.py` |
| 13 | `udp_checksum.py` · `udp_echo_local.py` · `reliable_udp.py` · `quic_vs_tcp.py` |
| 14 | `dns_wire_format.py` · `dns_resolve_path.py` · `dhcp_dora.py` |
| 15 | `http_message.py` · `http_cache.py` · `tls13_handshake.py` · `local_http_server.py` |
| 16 | `smtp_session.py` · `ftp_modes.py` · `ntp_offset.py` · `snmp_ber.py` |
| 17 | `acl_engine.py` · `nat_session.py` · `ipsec_packet.py` · `attack_model.py` |
| 18 | `pcap_parse.py` · `bpf_filter.py` · `traceroute_model.py` · `mtu_mss.py` |
| 19 | `netconf_yang.py` · `config_diff.py` · `telemetry_vs_poll.py` · `intent_check.py` |
| 20 | `vxlan_encap.py` · `overlay_mtu.py` · `k8s_service_path.py` · `cni_ipam.py` |
| 21 | `port_service_lookup.py` · `cheatsheet_audit.py` |
| 22 | `decision_tree.py` · `case_replay.py` |

---

## 仓库约定

**统一的演示数据**（全仓库共用，便于跨章对照）：

| 用途 | 取值 |
|------|------|
| 办公网段 | `192.0.2.0/24` |
| 对外服务网段 | `198.51.100.0/24` |
| 骨干链路网段 | `203.0.113.0/24` |
| IPv6 前缀 | `2001:db8::/32` |
| 设备命名 | 交换机 `SW1/SW2`，路由器 `R1/R2/R3`，主机 `PC1/PC2` |

`192.0.2.0/24`、`198.51.100.0/24`、`203.0.113.0/24` 是 RFC 5737 保留的文档专用网段，
`2001:db8::/32` 是 RFC 3849 保留的文档专用 IPv6 前缀——用它们做教学不会误伤真实地址。

**示例脚本的硬规矩**：零第三方依赖 · 单文件自包含 · 不联网 · 不读标准输入 ·
3 秒内跑完 · 输出中文并带「小结」· 需要落盘只用 `tempfile` · 攻击类演示只做建模不发真实流量。

---

## 配套仓库

同系列的学习仓库：

| 仓库 | 内容 |
|------|------|
| [python-learning](https://github.com/PhiloKun/python-learning) | Python 完整知识体系：22 章笔记 + 96 个示例 |
| [c-learning](https://github.com/PhiloKun/c-learning) | C 语言完整知识体系：22 章笔记 + 70 个示例，全量 ASan/UBSan 验证 |
| [cpp-learning](https://github.com/PhiloKun/cpp-learning) | 从零到现代 C++：20 章笔记 + 40 个示例 |
| [rust-learning](https://github.com/PhiloKun/rust-learning) | Rust 学习笔记 |

---

## 许可

笔记与代码均可自由使用、修改、分发（MIT）。引用的 RFC/IEEE 文档版权归各自组织所有。

发现内容错误或有更好的讲法，欢迎提 Issue。
