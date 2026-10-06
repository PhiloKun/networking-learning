# 第 10 章 · 动态路由 IS-IS 与 BGP

> **一句话定位**：从企业网的 OSPF 走到运营商与大型数据中心的 IS-IS，再走到连接整个互联网的 BGP —— 讲清 TLV 编码、NET 地址、路径属性分类与 11 步选路，读完能读懂一条 BGP 路由「为什么是它被选中」。
> **前置知识**：第 09 章（RIP 与 OSPF） ｜ **难度**：★★★ ｜ **建议投入**：170 分钟

## 一、学习目标

1. 能说出 IS-IS 与 OSPF 在层次结构、地址表达、报文承载、扩展方式上的六项关键差异。
2. 能写出 NET（NSAP）的字段划分，并把 `49.0001.2030.0011.0001.00` 拆成 AFI、Area、System ID、NSEL。
3. 能解释 TLV 编码为什么让 IS-IS 可以「不改协议版本就持续演进」，并手工解析一串 TLV。
4. 能默写 BGP 四种报文类型与 6 个状态的迁移路径，并说明卡在 Active 与 OpenSent 分别意味着什么。
5. 能按「well-known / optional + transitive / non-transitive」给 BGP 路径属性分类，并说明每个属性的作用范围。
6. 能完整复述 BGP 选路 11 步的顺序与每一步的比较对象，判断给定属性下谁胜出，并算出 iBGP 全互联的会话数量、说明路由反射器与联盟如何把它降下来。

## 二、核心概念总览

```
                    ┌──────────────────────────────────────────────┐
                    │  IGP（域内）：把网络连通起来                  │
                    │   OSPF        │        IS-IS                  │
                    │  链路状态     │        链路状态                │
                    │  IP 协议 89   │        直接跑在二层           │
                    │  Area 两级    │        L1/L2 两级             │
                    │  固定报文格式 │        全部 TLV 化            │
                    └──────────────────┬───────────────────────────┘
                                       │ 互引路由（ redistribute / import-route ）
                    ┌──────────────────┴───────────────────────────┐
                    │  EGP（域间）：在自治系统之间按策略选路         │
                    │   BGP-4  —— TCP 179 —— 路径矢量               │
                    │   eBGP（AS 之间） / iBGP（AS 内部）            │
                    │   四报文：OPEN UPDATE KEEPALIVE NOTIFICATION   │
                    │   六状态：Idle→Connect→Active→OpenSent         │
                    │           →OpenConfirm→Established             │
                    │   十一选路：Weight→LocalPref→…→Cluster-List    │
                    └──────────────────────────────────────────────┘
```

IS-IS 与 OSPF 解决同一个问题（域内链路状态路由），只是「方言」不同；BGP 解决的是完全不同的问题（域间策略路由）。三者的分工是：**OSPF/IS-IS 负责把 AS 内部连通，BGP 负责告诉邻居「我这里有网段」，OSPF/IS-IS 再把 BGP 下一跳解析成可用的转发路径**。这也是为什么 BGP 邻居断开常常伴随 IGP 的波动 —— 它们通过递归耦合在一起。

## 三、机制详解

### 3.1 IS-IS 与 OSPF：同源不同形的两套链路状态

IS-IS 最初为 OSI 协议栈设计，后来通过 NLPID 扩展承载 IPv4/IPv6。它与 OSPF 的关键差异：

| 对比项 | OSPF | IS-IS |
|---|---|---|
| 承载方式 | 直接封装在 IP 上（协议号 89） | 直接跑在数据链路层，不依赖 IP |
| 层次名称 | Area 0（骨干）+ 非骨干区域 | Level-2（骨干）+ Level-1（区域） |
| 区域边界 | ABR 同时属于两个区域 | L1/L2 路由器，一个接口只属于一级 |
| 路由器标识 | Router-ID（独立于区域） | System ID（嵌在 NET 地址里） |
| 报文编码 | 固定字段 + 少量 TLV | 全部 TLV，扩展只需定义新 TLV |
| 度量 | Cost = 参考带宽 / 接口带宽 | narrow（6 位/接口，总 10 位，最大 1023）/ wide（24 位/接口，总 32 位） |
| 收敛速度 | 快 | 更快（邻居建立到 Full 也更快，网络类型更少） |
| 典型场景 | 企业网、数据中心叶脊 | 运营商骨干、大型数据中心 |

**层次模型**：L1 路由器只维护本区域拓扑，靠最近的 L1/L2 路由器（设置 Attached 位）的默认路由出区域；L2 路由器维护骨干拓扑；L1/L2 路由器同时属于两级，承担类似 ABR 的角色。

**NET（Network Entity Title）地址**：格式是 NSAP，`49.0001.2030.0011.0001.00` 拆开是：

1. `49` —— AFI（地址族标识），1 字节，49 表示本地管理（私用）。
2. `0001` —— Area ID，本区域号。
3. `2030.0011.0001` —— System ID，6 字节，全局唯一（等价于 OSPF 的 Router-ID）。
4. `00` —— N-SEL（N-Selector），1 字节，固定为 00，表示「走 IS-IS 路由」。

**TLV 编码**：每个 TLV 是 `类型(1 字节) | 长度(1 字节) | 值(长度字节)`。Hello 里常见 TLV 1（区域地址）、6（邻居）、129（支持的协议 NLPID，0xCC=IPv4、0x8E=IPv6）、132（接口 IP）、137（主机名）；LSP 里常见 TLV 22（扩展邻居可达性）、128/130（IP 可达性）、240（路由器能力，承载 Segment Routing）。新特性只需分配一个新 TLV 类型，老设备跳过不认识的类型即可，这是 IS-IS 生命周期极长的根本原因。

### 3.2 BGP 为什么要用路径矢量

域间路由面对的不是「最短路径」问题，而是**策略问题**：A 运营商可能不愿意给 B 运营商转发流量，C 运营商想把流量引导到成本更低的出口。距离矢量（跳数）和链路状态（全局拓扑）都无法表达「我不许你走这条路」。

于是 BGP 用**路径矢量（Path Vector）**：每条路由携带一个 **AS_PATH**（它经过的 AS 序列）。两个好处：

1. **天然防环**：收到的 AS_PATH 里若含自己的 AS 号，立即丢弃。
2. **可做策略**：AS_PATH 的长度、内容都可以作为选路与过滤依据。

BGP 邻居关系分两种：

- **eBGP（external BGP）**：位于不同 AS 之间。默认要求直连（TTL=1），通过 `neighbor x.x.x.x ebgp-multihop N` 可放宽到多跳；发送路由时修改 NEXT_HOP 为自己的接口地址，并把本地 AS 号 prepend 进 AS_PATH。
- **iBGP（internal BGP）**：位于同一 AS 内部。默认 TTL=255，不要求直连，但要求**全互联**（因为 iBGP 学来的路由不再转发给其它 iBGP 邻居），且不修改 AS_PATH、不修改 NEXT_HOP。

BGP 会话跑在 **TCP 179** 上（所以不需要自己实现可靠传输），路由器之间用 **BGP Router-ID** 标识（通常取环回地址）。

### 3.3 BGP 四种报文与状态机

**四种报文**：

- **OPEN**：建连后的第一个报文，协商 Version、My AS、Hold Time、BGP Identifier 与可选能力（MP-BGP / 4 字节 AS / Route Refresh）。
- **UPDATE**：宣告或撤销路由，由「撤销路由 + 路径属性 + NLRI」三段组成。
- **KEEPALIVE**：只有 19 字节公共头，没有正文，用来维持邻居。默认 Hold Time 180 秒，Keepalive 为 Hold/3 = 60 秒。
- **NOTIFICATION**：出错时发送并立即断开，携带错误码与子码（如 6/2 = 邻居不通、2/2 = Hold Time 不匹配）。

**状态机 6 态**：

```
Idle ──启动──> Connect ──TCP成功──> OpenSent ──收到OPEN──> OpenConfirm
  ↑               │                                            │
  │         TCP失败│                                    收到KEEPALIVE
  │               ↓                                            ↓
  └──错误/超时/收到NOTIFICATION─────────── Established <───────┘
      Active <──ConnectRetry(120s) 超时── (从 Connect 退下)
```

- 卡在 **Idle**：通常是没有到对端的路由，或邻居配置未生效。
- 卡在 **Active**：几乎等价于「TCP 179 不通」，对端没监听、ACL 拦截、路由不可达都会表现为这里。**用 `telnet <对端> 179` 立刻验证**。
- 卡在 **OpenSent**：版本或 AS 号不匹配、Router-ID 冲突。
- 卡在 **OpenConfirm**：认证失败或 Hold Time 不匹配。

### 3.4 路径属性分类与作用

路径属性按 RFC 4271 分为四类：

| 分类 | 含义 | 属性 |
|---|---|---|
| well-known mandatory | 必须识别、必须携带 | ORIGIN、AS_PATH、NEXT_HOP |
| well-known discretionary | 必须识别、可带可不带 | LOCAL_PREF、ATOMIC_AGGREGATE |
| optional transitive | 可不识别，但必须继续传递 | AGGREGATOR、COMMUNITY |
| optional non-transitive | 可不识别，且不继续传递 | MED（MULTI_EXIT_DISC） |

关键属性作用范围：

- **AS_PATH**：防环 + 选路（短者优）。只在 eBGP 方向 prepend。
- **NEXT_HOP**：eBGP 方向改成自己的接口地址；iBGP 方向默认不改（因此 iBGP 必须保证下一跳可达，否则路由无效 —— 常见的 `next-hop-self` 就是为此）。
- **LOCAL_PREF**：只在 AS 内（iBGP）传播，**不能传给 eBGP 邻居**，默认 100。是「我要不要用这条出口」的总开关。
- **MED**：默认只传给相邻 AS，且**默认只在同一邻居 AS 的多条路径间比较**。是「请对方优先用哪个入口」的软建议。
- **ORIGIN**：路由来源，IGP(0) 优于 EGP(1) 优于 INCOMPLETE(2)。`network` 产生的是 IGP，`redistribute` 产生的是 INCOMPLETE。
- **COMMUNITY**：可选传递的标签，常用于打标记做批量策略（如 `no-export`、`no-advertise`）。
- **ATOMIC_AGGREGATE**：告知下游「这条是聚合路由，明细已丢弃」，用于避免环路与误导。

### 3.5 BGP 选路 11 步

严格按顺序执行，任何一步出现唯一最优立即结束：

| 步骤 | 规则 | 比较对象 | 方向 |
|---|---|---|---|
| 1 | Weight / Preferred-Value | Weight | 大者优；仅本机有效，不传邻居 |
| 2 | LOCAL_PREF | LocalPref | 大者优；AS 内传递，默认 100 |
| 3 | 本地始发 | 产生方式 | aggregate > network > import-route，优于学来的 |
| 4 | AS_PATH 长度 | AS_PATH | 短者优（AS_SET 计 1） |
| 5 | ORIGIN | Origin | IGP > EGP > INCOMPLETE |
| 6 | MED | MED | 小者优；默认只在同一邻居 AS 间比较 |
| 7 | eBGP 优于 iBGP | 邻居类型 | eBGP 优先 |
| 8 | IGP 度量 | 到 NEXT_HOP 的度量 | 小者优 |
| 9 | 路由年龄 | Age | 思科：同为 eBGP 取最早收到 |
| 10 | Router-ID | 对端 Router-ID | 小者优 |
| 11 | Cluster-List 长度 | Cluster-List | 短者优；再平局比对等体地址小者优 |

**厂商差异**：思科第 1 步叫 Weight，华为对应 Preferred-Value，两者都只在本地生效；思科把「路由年龄」放在 Router-ID 之前，华为不比较年龄，直接比较 Cluster-List、Router-ID、对等体地址。

### 3.6 路由反射器、联盟与聚合抑制

iBGP 要求全互联，n 台路由器需要 `n(n-1)/2` 条会话：4 台 = 6 条，10 台 = 45 条，100 台 = 4950 条。两种降规模方案：

- **路由反射器（Route Reflector, RR）**：把一台路由器设为反射中心，其它设备作为 Client 只与 RR 建会话。RR 把从 Client 学到的路由反射给其它 Client，用 **Cluster-List** 防环：反射时追加自己的 cluster-id，收到 Cluster-List 里已含自己 cluster-id 的路由就丢弃。
- **联盟（Confederation）**：把一个 AS 拆成多个子 AS（如 65001:1、65001:2），子 AS 之间像 eBGP、内部像 iBGP，用 **AS_CONFED_SEQUENCE** 防环，子 AS 信息在联盟边界被剥除，对外完全透明。

**路由聚合与抑制**：用 `aggregate-address`（思科）/ `aggregate`（华为）把明细聚合成一条前缀，避免路由表膨胀。但聚合会导致**明细丢失去向**，因此实际部署中常配合 `summary-only`（只发聚合不发明细）或 `suppress-map` / `unsuppress-map` 精细控制。**聚合点必须掌握完整明细**，否则会形成黑洞。

## 四、动手验证

### 4.1 `isis_tlv.py` —— 手工编码与解析 IS-IS Hello

```
运行: python3 isis_tlv.py
```

关键输出：

```
偏移    类型        长度    名称                        解码
19      1(0x01)     5       Area Addresses              区域地址个数=1，地址=49.0001
30      132(0x84)   4       IP Interface Address        接口地址=203.0.113.1
40      22(0x16)    16      Extended IS Reachability    2030.0011.0002.00 度量=10
```

从输出能看出：NET 的 Area 部分是 3 字节 `49 00 01`，TLV 区从偏移 19 开始逐个「类型|长度|值」推进。结论：IS-IS 报文就是「8 字节公共头 + PDU 专有字段 + 一串 TLV」，解析规则只有一条。

### 4.2 `bgp_best_path.py` —— 11 步选路逐轮淘汰

```
运行: python3 bgp_best_path.py
```

关键输出（场景 1）：

```
步骤 2    LOCAL_PREF     → 淘汰 E(AS65004)=50 —— 不及 LocalPref 最大 = 100
步骤 4    AS_PATH 长度   → 淘汰 C(AS65002)=2 —— 不及 AS_PATH 最短 = 1
步骤 6    MED            → 跳过：候选来自不同邻居 AS (65001,65003)，按默认规则 MED 不参与比较
步骤 9    路由年龄        → 淘汰 A、B —— 不及 最早收到（年龄最大 = 200s）
>>> 最终胜出：D(AS65003)
```

脚本还跑了两个对照场景：把年龄拉平后决策点后移到第 10 步（Router-ID）；构造前 10 步全平、只有 Cluster-List 不同的输入，让第 11 步定胜负。结论：选路是严格的字典序，前面任何一步唯一就会终结整个流程。

### 4.3 `bgp_aspath.py` —— AS_PATH 防环与 iBGP 水平分割

```
运行: python3 bgp_aspath.py
```

关键输出：

```
eBGP 收到环路路由   65002 65003 65001   AS_PATH 中出现本地 AS 65001 → 判定环路，直接丢弃该路由
eBGP 收到正常路由   65002 65003 65004   接受，转发时 AS_PATH 变为 65001 65002 65003 65004
```

脚本随后推演了无 RR 时的 iBGP 水平分割（R2 从 R1 学到的路由不能再转给 R3）、RR 用 Cluster-List 防环，以及联盟用 AS_CONFED_SEQUENCE 防环。结论：AS_PATH 是 eBGP 的第一道闸门，Cluster-List 与 AS_CONFED_SEQUENCE 是 AS 内部的第二道。

### 4.4 `bgp_sm.py` —— 四种报文与状态机

```
运行: python3 bgp_sm.py
```

脚本用 `bytes` 手工拼出 OPEN 与 UPDATE 报文并解析回来：

```
字段                  长度        取值                      说明
Marker                16 字节     FF FF FF FF ...           全 1，接收方用它做同步校验
Length                2 字节      45                        含报文头的总长度，范围 19~4096
Type                  1 字节      1(OPEN)                   报文类型
属性    Flags     值长    名称                    含义
1       0x40      1       ORIGIN                  ...  值=0(IGP)
2       0x40      4       AS_PATH                 ...  值=AS_SEQUENCE 65002
3       0x40      4       NEXT_HOP                ...  值=203.0.113.2
```

结论：KEEPALIVE 只有 19 字节；UPDATE 的 NLRI 用「1 字节前缀长度 + 前缀字节」编码，198.51.100.0/24 只需 4 字节。

## 五、关键字段 / 报文格式解剖

### 5.1 IS-IS 公共头（8 字节）

| 字段 | 长度 | 作用 | 常见取值 |
|---|---|---|---|
| Discriminator | 1 字节 | 协议标识 | 0x83 固定 |
| Length Indicator | 1 字节 | 公共头长度 | 通常 8 |
| Version/Proto ID Ext | 1 字节 | 版本扩展 | 固定 1 |
| ID Length | 1 字节 | System ID 长度 | 通常 6 |
| R / PDU Type / Version | 1 字节 | R 位 + 5 位类型 + 2 位版本 | 15=L1 LAN Hello，20=L2 LSP |
| Version | 1 字节 | 协议版本 | 固定 1 |
| Reserved | 1 字节 | 保留 | 0 |
| Max Area Addresses | 1 字节 | 支持的区域地址上限 | 通常 3 |

### 5.2 BGP 报文头与 UPDATE 关键字段

| 字段 | 长度 | 作用 | 常见取值 |
|---|---|---|---|
| Marker | 16 字节 | 同步校验 | 全 0xFF |
| Length | 2 字节 | 报文总长 | 19~4096 |
| Type | 1 字节 | 报文类型 | 1=OPEN 2=UPDATE 3=NOTIFICATION 4=KEEPALIVE |
| Withdrawn Routes Length | 2 字节 | 撤销路由段长度 | 0 表示无撤销 |
| Total Path Attribute Len | 2 字节 | 属性段长度 | 可变 |
| Path Attributes | 变长 | 属性列表，每条含 Flags/Type/Length/Value | ORIGIN、AS_PATH 等 |
| NLRI | 变长 | 网络层可达信息 | 1 字节前缀长度 + 前缀 |

### 5.3 路径属性 Flags 位

| 位 | 名称 | 含义 |
|---|---|---|
| 0x80 | Optional | 1=可选属性，0=well-known |
| 0x40 | Transitive | 1=允许传递给其它 AS，0=禁止传递 |
| 0x20 | Partial | 1=对端未识别但已部分传递 |
| 0x10 | Extended Length | 1=长度字段为 2 字节 |

常见组合：0x40 = well-known 传递；0x80 = optional 不传递（MED）；0xC0 = optional 传递（COMMUNITY、AGGREGATOR）。

### 5.4 常用 AS 号段与端口

| 项 | 取值 |
|---|---|
| BGP 端口 | TCP 179 |
| 公网 2 字节 AS | 1 ~ 64511 |
| 私用 2 字节 AS | 64512 ~ 65534 |
| 保留 | 0（RFC 7607）、23456（AS_TRANS）、65535 |
| 私用 4 字节 AS | 4200000000 ~ 4294967294 |
| 默认 Hold Time | 180 秒（Keepalive = 60 秒 = Hold/3） |
| ConnectRetry | 120 秒 |

## 六、易混概念对比

| 概念 A | 概念 B | 核心区别 | 典型场景 |
|---|---|---|---|
| IGP（OSPF/IS-IS） | EGP（BGP） | IGP 求域内最短路径，EGP 做域间策略选路 | 企业内网 vs 多出口/多运营商 |
| eBGP | iBGP | 跨 AS（TTL=1、改 AS_PATH 与 NEXT_HOP）vs 同 AS（TTL=255、不改） | 出口互联 vs AS 内传递 |
| LOCAL_PREF | MED | LocalPref 是「我对出口的偏好」，只在 AS 内；MED 是「请对方选我哪个入口」 | 多出口选路 vs 多入口引导 |
| ORIGIN 值 IGP | ORIGIN 值 INCOMPLETE | network 产生 IGP；redistribute 产生 INCOMPLETE | 选路第 5 步的依据 |
| L1 | L2 | L1 只维护本区域、靠默认路由出区；L2 维护骨干 | IS-IS 的两级层次 |
| narrow 度量 | wide 度量 | narrow 6 位/接口、总 10 位（≤1023）；wide 24 位/接口、总 32 位 | 老设备 vs 现代网络 |
| 路由反射器 | 联盟 | RR 用一台设备做反射中心；联盟把 AS 拆成子 AS | 替代 iBGP 全互联的两种方案 |

## 七、工程实践与最佳实践

1. **iBGP 一律用环回地址建邻居，并提前打通环回路由**。原因：物理链路抖动不会中断 BGP 会话，环回不会 down；但前提是 IGP 已收敛，否则会话起不来。
2. **iBGP 邻居必须配 `next-hop-self`（或保证下一跳可达）**。原因：eBGP 学来的路由下一跳是外部接口地址，iBGP 默认不修改该下一跳，若 AS 内没有到该地址的路由，路由会因递归失败而无效。
3. **LOCAL_PREF 用来做出口选路，MED 只在对端配合时限用**。原因：LocalPref 在自己 AS 内生效、语义可控；MED 是「建议」，对端完全可以忽略（默认只在同一邻居 AS 间比较）。
4. **eBGP 邻居默认 TTL=1，跨跳必须显式开 `ebgp-multihop`**。原因：这是 BGP 的直连性检查，防止误配导致跨多跳形成隐蔽环路。
5. **AS_PATH 是防环的第一道闸门，不要用 `allowas-in` 绕过**。原因：`allowas-in` 允许 AS_PATH 含本 AS 号，会直接打开环路风险，只在特定备份场景使用并做好路由过滤。
6. **AS 内规模超过 4~5 台就上路由反射器**。原因：全互联会话数按 n(n-1)/2 增长，10 台就 45 条会话，配置与排障成本急剧上升。
7. **RR 建议配置冗余（双 RR）并设置相同 cluster-id**。原因：单 RR 是单点，双 RR 之间是 iBGP 非客户机关系，相同 cluster-id 可避免反射环路。
8. **聚合务必确认明细完整，必要时用 `summary-only` + `unsuppress-map`**。原因：聚合会把不连续/缺失的明细合并成一条，若明细不全就会产生黑洞。
9. **IS-IS 上生产前把度量类型统一为 wide**。原因：narrow 总度量上限 1023，大网中容易溢出导致路径不可用；wide 支持 32 位，且能承载 TE 与 SR 扩展。
10. **IS-IS 的 NET 中 System ID 必须全网唯一**。原因：System ID 等价于 Router-ID，重复会导致 LSP 被覆盖、拓扑错乱。
11. **BGP 变更务必先做准备与回滚方案**。原因：一条错误的 AS_PATH 过滤或 LOCAL_PREF 会瞬间把整网流量引向单点，影响面是「全局」级别的。
12. **监控 BGP 邻居的 Established 时长与前缀数量抖动**。原因：邻居频繁 Flapping 或前缀数骤变，是链路质量、策略误配或路由泄漏的先兆。

## 八、常见陷阱清单

| # | 现象 | 根因 | 排查 / 规避 |
|---|------|------|-------------|
| 1 | BGP 邻居长期卡在 Active | TCP 179 不通：对端没监听、ACL 拦、路由不可达 | `telnet <对端> 179`；检查 `display bgp peer` 状态与 ACL |
| 2 | 邻居卡在 OpenSent | 两端 AS 号不匹配、版本不同或 Router-ID 冲突 | 核对 `peer` 配置中的 AS 号与 BGP Router-ID |
| 3 | 邻居卡在 OpenConfirm | 认证失败或 Hold Time 不匹配（一端 0 一端非 0） | 核对密码、`timer keepalive/hold` |
| 4 | 邻居 Established 但学不到路由 | 地址族未使能、路由策略过滤、下一跳不可达 | 查 `address-family` 是否激活、filter-policy 与 NEXT_HOP 递归 |
| 5 | 只能单向学路由 | 一侧配了 outbound 过滤或 `next-hop-self` 缺失 | 两侧对比 `display bgp routing-table peer ... advertised` |
| 6 | iBGP 学到的路由下一跳不可达 | iBGP 默认不改 NEXT_HOP，AS 内无到该地址的路由 | 在边界路由器配 `next-hop-self`，或把下一跳网段引入 IGP |
| 7 | 明明有更短路径却走了长路径 | 上游的 LOCAL_PREF 或 Weight 更高，先于 AS_PATH 生效 | 逐步核对 11 步，重点看 Weight/LocalPref |
| 8 | MED 设了却不生效 | 默认只在「同一邻居 AS」的多条路径间比较 MED | 确认对端来自同一 AS；跨 AS 需 `always-compare-med` |
| 9 | 新加的高优先级出口不生效 | Weight/LocalPref 已决定，与链路优劣无关 | 改 LocalPref（AS 内生效）而不是改链路带宽 |
| 10 | iBGP 全互联会话数爆炸 | n(n-1)/2 增长，10 台即 45 条 | 部署路由反射器或联盟 |
| 11 | 路由反射后出现环路 | Cluster-List 未生效或 cluster-id 配错 | 确认 RR 反射时追加 cluster-id，且全网 cluster-id 规划清晰 |
| 12 | 聚合后出现黑洞 | 聚合点缺失部分明细，或明细下一跳不一致 | 聚合前核对明细完整；用 `suppress-map`/`unsuppress-map` 精细控制 |
| 13 | IS-IS 邻居起不来 | 两端 Level 不匹配、NET 区域号不同、MTU 不一致 | 核对 `is-level`、NET 的区域部分、接口 MTU |
| 14 | IS-IS 学到路由但 Ping 不通 | narrow 度量溢出（>1023）导致路径被弃用 | 改用 wide 度量并在接口上配 `isis metric` |
| 15 | 改 BGP 策略后整网流量异常 | 一条错误的 LOCAL_PREF/AS_PATH 过滤影响全局 | 变更前用小范围 peer 验证，配好回滚脚本 |

## 九、自测练习

1. 把 NET `49.0001.2030.0011.0001.00` 拆成 AFI、Area ID、System ID、N-SEL 四部分，并说明各自作用。
2. **计算题**：某 AS 内部有 12 台路由器需要建立 iBGP 全互联，需要多少条会话？若改为 1 台 RR + 11 台客户端呢？
3. **计算题**：BGP 默认 Hold Time 为 180 秒，Keepalive 应为多少秒？若把 Hold Time 改为 90 秒，Keepalive 变成多少？
4. **计算题**：BGP 的 Marker 是 16 字节全 1，Length 2 字节，Type 1 字节，问 KEEPALIVE 报文总长多少字节？一个携带 1 条 /24 前缀、含 ORIGIN/AS_PATH/NEXT_HOP 三条属性的 UPDATE 报文，若不考虑路径属性长度开销，NLRI 部分至少几字节？
5. 一个 TLV 的类型是 22，长度字段为 0x10，那么它的「值」占多少字节？整个 TLV 占多少字节？
6. **排障题**：两台路由器 BGP 邻居卡在 Active，请给出至少三条可能原因与逐步验证方法。
7. **排障题**：BGP 邻居已 Established，但内网主机访问对端网段不通，怎么查？
8. 为什么 iBGP 需要全互联，而 eBGP 不需要？
9. 为什么 LOCAL_PREF 不能传给 eBGP 邻居，而 MED 可以传给相邻 AS？
10. 路由反射器为什么能打破水平分割而不产生环路？
11. **计算题**：给定 3 条候选路由（Weight 都是 0，LocalPref 都是 100，AS_PATH 长度均为 2，Origin 都是 IGP，来自同一邻居 AS，MED 分别为 30/10/20），选路到第几步结束？胜出者的 MED 是多少？
12. IS-IS 的 narrow 与 wide 度量在字段宽度与上限上有什么区别？为什么大网更推荐 wide？

<details>
<summary>参考答案</summary>

1. `49` 是 AFI（地址族标识，1 字节，49 表示本地管理私用地址）；`0001` 是 Area ID（区域号，同区域才能建 L1 邻接）；`2030.0011.0001` 是 System ID（6 字节，路由器唯一标识，等价 OSPF 的 Router-ID）；`00` 是 N-SEL（固定 00，表示走 IS-IS 路由）。

2. 全互联会话数 = `n × (n-1) / 2 = 12 × 11 / 2 = 66` 条。改成 1 台 RR + 11 台客户端后，每台客户端只需与 RR 建 1 条会话，共 11 条；若再加一台冗余 RR，则为 11 + 11 = 22 条（两台 RR 之间再建 1 条 iBGP，共 23 条）。

3. Keepalive = Hold Time / 3。Hold 180 秒 → Keepalive = `180 / 3 = 60` 秒。Hold 90 秒 → Keepalive = `90 / 3 = 30` 秒。注意两端 Hold Time 取较小值，Keepalive 也相应取较小值对应的 1/3。

4. KEEPALIVE 报文长度 = `16（Marker）+ 2（Length）+ 1（Type）= 19` 字节。NLRI 部分为 `1 字节前缀长度 + 3 字节前缀（/24 补齐到 3 字节）= 4` 字节。注意 UPDATE 消息实际长度还要加上 Withdrawn Routes Length（2 字节）、Total Path Attribute Length（2 字节）以及三个属性的 Flags+Type+Length+Value。

5. 长度字段 0x10 = 16，表示「值」占 16 字节；整个 TLV = `类型 1 + 长度 1 + 值 16 = 18` 字节。若长度超过 255，需改用 2 字节长度的扩展格式（Type 255）。

6. 卡在 Active 意味着 TCP 179 没连上。可能原因与验证：① 对端没监听 179 —— `telnet <对端IP> 179` 或 `nc -vz <IP> 179`，不通即证明；② 中间 ACL/防火墙拦截 —— 检查沿途 `show access-lists` 是否放行 TCP 179，注意 eBGP 默认 TTL=1，跨设备会被丢弃；③ 到对端没有路由 —— `ping <对端环回>` 与 `show ip route <对端>`；④ 对端配置的 peer 地址写错 —— 两端对比 `show run | section router bgp`。逐步做，先解决 TCP 层，再看 BGP 参数。

7. 邻居 Established 只代表控制面通了。查：① `show ip bgp` 看该前缀是否存在、是否带 `*>`（valid + best）；② 若只有 `*` 没有 `>`，说明没被选为最优或下一跳不可达；③ 检查 NEXT_HOP 能否递归解析（`show ip route <next-hop>`）—— iBGP 常见问题是下一跳是外部地址而 AS 内没有路由；④ 检查转发面是否被 ACL/策略路由改向；⑤ 用 `traceroute` 看数据实际走到哪一跳断了。

8. iBGP 的水平分割规定「从 iBGP 邻居学来的路由，不再转发给其它 iBGP 邻居」，目的是防止 AS 内出现环路（因为 AS_PATH 在 iBGP 方向不变化，无法用它防环）。既然不转发，要保证所有 iBGP 路由器都拿到完整路由，就只能两两直连，即全互联。eBGP 之间不同 AS，AS_PATH 每过一跳都会 prepend 本地 AS，天然防环，因此不需要全互联，且跨 AS 全互联也不现实。

9. LOCAL_PREF 表达的是「本 AS 内部对出口的偏好」，它是本 AS 的本地决策量，传给外部 AS 没有意义，还会泄漏内部策略，因此规定只在 iBGP 内传播（收到 eBGP 的 LOCAL_PREF 要丢弃）。MED 表达的是「请你优先从我这个 AS 的哪个入口进来」，是给相邻 AS 看的建议，所以允许传给相邻 AS；但默认只在同一邻居 AS 的多条路径间比较，避免被更远的 AS 影响。

10. RR 反射路由时，会在 **Cluster-List** 属性里追加自己的 cluster-id。任何路由器（包括 RR 自己）收到一条 Cluster-List 中已包含自己 cluster-id 的路由时，就判定为反射环路并丢弃。这样 RR 既能把 Client 的路由反射给其它 Client（打破水平分割），又不会让路由无限绕圈。

11. 前 5 步：Weight 全平（第 1 步平局）→ LocalPref 全平（第 2 步平局）→ 无本地始发（第 3 步平局）→ AS_PATH 长度都是 2（第 4 步平局）→ Origin 都是 IGP（第 5 步平局）。第 6 步 MED：三条来自**同一邻居 AS**，故 MED 生效，取最小者，`min(30, 10, 20) = 10`。选路在第 6 步结束，胜出者 MED = 10。

12. narrow 度量：每个接口的度量 6 位（0~63），整条路径的总度量 10 位（最大 1023）。wide 度量：每个接口的度量 24 位（0~16777215），总度量 32 位。大网推荐 wide 的原因：① narrow 的 1023 上限在大型网络中很容易被累加超过，超限的路径会被判定不可用；② wide 能承载更大的度量值与流量工程（TE）扩展；③ Segment Routing 等新特性依赖 wide 度量格式。

</details>

## 十、命令与配置速查

| 用途 | 思科（Cisco IOS） | 华为（VRP） | 主机侧 |
|---|---|---|---|
| 查看 BGP 邻居 | `show ip bgp summary` | `display bgp peer` | — |
| 查看 BGP 路由 | `show ip bgp` | `display bgp routing-table` | — |
| 查看某前缀的所有路径 | `show ip bgp 198.51.100.0/24` | `display bgp routing-table 198.51.100.0` | — |
| 查看对端收发的路由 | `show ip bgp neighbors x.x.x.x routes` | `display bgp routing-table peer x.x.x.x advertised-routes` | — |
| 重置 BGP 会话 | `clear ip bgp x.x.x.x` | `reset bgp x.x.x.x` | — |
| 软重置（不拆邻居） | `clear ip bgp x.x.x.x soft in` | `refresh bgp x.x.x.x import` | — |
| 查看 IS-IS 邻居 | `show isis neighbors` | `display isis peer` | — |
| 查看 IS-IS LSDB | `show isis database` | `display isis lsdb` | — |
| 查看 IS-IS 路由 | `show isis route` | `display isis route` | — |
| 配置 eBGP | `router bgp 65001` / `neighbor 203.0.113.2 remote-as 65002` | `bgp 65001` / `peer 203.0.113.2 as-number 65002` | — |
| 配置 iBGP 下一跳自省 | `neighbor x.x.x.x next-hop-self` | `peer x.x.x.x next-hop-local` | — |
| 设置 LOCAL_PREF | `bgp default local-preference 200` / `set local-preference 200` | `default local-preference 200` | — |
| 设置 MED | `set metric 50`（route-map） | `apply cost 50`（route-policy） | — |
| 配置路由反射器 | `neighbor x.x.x.x route-reflector-client` | `peer x.x.x.x reflect-client` | — |
| 清除 IP 前缀（IS-IS） | `router isis` / `net 49.0001.2030.0011.0001.00` | `isis 1` / `network-entity 49.0001.2030.0011.0001.00` | — |
| 测 BGP 端口连通性 | — | — | `nc -vz 203.0.113.2 179` |
| 抓 BGP 包 | — | — | `tcpdump -i eth0 tcp port 179 -nn` |

## 十一、本章示例索引

| 文件 | 一句话说明 | 运行 |
|------|-----------|------|
| `isis_tlv.py` | IS-IS Hello PDU 的公共头 + TLV 手工编码与解析，含 NET 地址结构与常考 TLV 一览 | `python3 isis_tlv.py` |
| `bgp_best_path.py` | BGP 选路 11 步逐条应用，三个场景演示决策点落在第 9/10/11 步 | `python3 bgp_best_path.py` |
| `bgp_aspath.py` | AS_PATH 防环、iBGP 水平分割、路由反射器 Cluster-List 防环与联盟对照 | `python3 bgp_aspath.py` |
| `bgp_sm.py` | BGP OPEN/UPDATE 报文手工构造与解析、四类报文对照、6 状态迁移与排障要点 | `python3 bgp_sm.py` |

---

⬅️ 上一章：[第 09 章 动态路由 RIP 与 OSPF](../09-动态路由RIP与OSPF/README.md) ｜ ➡️ 下一章：[第 11 章 网关冗余与组播](../11-网关冗余与组播/README.md) ｜ 🏠 [返回总目录](../README.md)
