# 第 05 章 · 无线局域网 WLAN

> **一句话定位**：把「无线」这层看不见的介质讲成可计算、可规划、可排障的工程对象——从 802.11 的帧、信道、速率表，到 CSMA/CA 竞争、密钥派生、漫游时间预算，读完能独立完成一个小型 WLAN 的信道规划与故障定位。
> **前置知识**：第 04 章 以太网与交换技术（VLAN / 802.1Q / MAC 学习） ｜ **难度**：★★☆ ｜ **建议投入**：120 分钟

## 一、学习目标

1. 能说出 802.11 a/b/g/n/ac/ax/be 各自的频段、最大信道宽度、最大空间流与理论峰值速率，并解释速率提升来自哪三个维度。
2. 能算出 EIRP（dBm）、自由空间路损 FSPL，并判断某配置是否超出 2.4G / 5G 的发射功率限值。
3. 会画出 CSMA/CA 的 DIFS + 退避 + SIFS + ACK 时序，并说明 RTS/CTS 为什么能解决隐藏终端。
4. 能复述 WPA2-PSK 的密钥链 `口令 + SSID → PMK → PTK`，并说清 4 次握手每一步交换了什么。
5. 能拆解一次漫游的时间线，在 50ms 语音预算下给出 802.11k/r/v、PMKSA 缓存的优化组合。
6. 能根据现场干扰与覆盖数据，在 2.4G 的 1/6/11 与 5G 的非重叠信道间做信道规划。

## 二、核心概念总览

```
        ┌─────────────────────────── ESS（扩展服务集，一个 SSID）───────────────────────────┐
        │                                                                                  │
        │   ┌─────────┐        ┌─────────┐        ┌─────────┐                              │
        │   │  AP1    │        │  AP2    │        │  AP3    │     ← 同一 SSID / 不同 BSSID  │
        │   │BSSID:.0A│        │BSSID:.0B│        │BSSID:.0C│        同一 VLAN（二层漫游）  │
        │   └────┬────┘        └────┬────┘        └────┬────┘                              │
        │        │                  │                  │                                    │
        │      BSS1                BSS2               BSS3   ← 基本服务集（一个 AP 的覆盖）  │
        │    ┌───┴───┐          ┌───┴───┐          ┌───┴───┐                                │
        │    │ STA1  │          │ STA2  │          │ STA3  │  ← 站点：手机/笔记本/传感器     │
        │    └───────┘          └───────┘          └───────┘                                │
        └──────────────────────────────┬───────────────────────────────────────────────────┘
                                       │ 有线侧（DS 分布式系统 = 交换机 + AC）
                              ┌────────┴────────┐
                              │  AC（无线控制器）│  ← 统一管配置 / 漫游 / 802.1X 转发
                              └─────────────────┘

  介质访问（共享空气）                    安全（从明文到 SAE）
  ┌──────────────────────────────┐      ┌────────────────────────────────────┐
  │ DIFS → 随机退避 → 发送 → SIFS │      │ WEP(已废) → WPA/TKIP → WPA2/CCMP   │
  │ → ACK；冲突则 CW 翻倍重试     │      │ → WPA3/SAE；企业侧 802.1X+EAP      │
  └──────────────────────────────┘      └────────────────────────────────────┘
```

上图中，**STA 与 AP 之间构成一个 BSS**，AP 的 MAC 就是 BSSID；多个同 SSID 的 BSS 组成 **ESS**，STA 在 ESS 内换 AP 就叫漫游。空口是**共享介质**，所有 STA 抢同一个信道，因此 MAC 层必须用 **CSMA/CA** 而非有线以太网的 CSMA/CD。安全链条从口令一路派生到真正加密数据帧的 TK，中间任何一环错（口令、SSID、缓存）都表现为「连不上或频繁掉线」。AP 上联到交换机、由 **AC** 统一管理，则把「无线」接回了第 04 章的 VLAN / Trunk 世界。

## 三、机制详解

### 3.1 802.11 家族与速率三要素

理论峰值速率由三个维度相乘决定：

```
速率 = 信道带宽 × 空间流数 × 每符号比特数（调制阶数） × 编码率
```

逐代演进的实际取值：

| 标准 | 频段 | 最大信道宽 | 空间流 | 调制 | 理论峰值 |
|---|---|---|---|---|---|
| 802.11b | 2.4G | 20MHz | 1 | CCK | 11 Mbps |
| 802.11g | 2.4G | 20MHz | 1 | 64-QAM OFDM | 54 Mbps |
| 802.11n (Wi-Fi 4) | 2.4/5G | 40MHz | 4 | 64-QAM MIMO | 600 Mbps |
| 802.11ac (Wi-Fi 5) | 5G | 160MHz | 8 | 256-QAM MU-MIMO | 6933 Mbps |
| 802.11ax (Wi-Fi 6) | 2.4/5/6G | 160MHz | 8 | 1024-QAM OFDMA | 9607.8 Mbps |
| 802.11be (Wi-Fi 7) | 2.4/5/6G | 320MHz | 16 | 4096-QAM MLO | 46120 Mbps |

**802.11n 的 600Mbps 怎么来的**：4 空间流 × 40MHz × 每子载波 5/6 编码率 × 64-QAM(6 bit/符号) × 短保护间隔 400ns。注意 **MU-MIMO**（多用户 MIMO）在 802.11ac 只支持下行，802.11ax 才支持上下行；**OFDMA**（正交频分多址）把信道切成资源单元（Resource Unit, RU），可同时服务多个用户，是 Wi-Fi 6 提升密集场景吞吐的关键。

### 3.2 频段与信道划分

2.4GHz 每个信道宽 20MHz，但中心频率只间隔 5MHz，所以相邻信道必然重叠。中心频率公式：

```
f(MHz) = 2412 + 5 × (信道号 − 1)
```

信道 1 = 2412MHz，信道 6 = 2437MHz，信道 11 = 2462MHz。1/6/11 两两相距 25MHz > 20MHz，**互不重叠，是 2.4G 唯一的密集部署方案**。5GHz 信道间隔 20MHz，全部不重叠；中心频率 `f = 5000 + 5×信道号` MHz，如信道 36 = 5180MHz、信道 149 = 5745MHz。6GHz 新增 59 个 20MHz 信道，且要求 WPA3 才能使用。

### 3.3 CSMA/CA：DIFS、退避与竞争窗口

有线以太网能「边发边听、冲突就退」（CSMA/CD），无线做不到——STA 自己的发射信号会淹没接收，无法边发边检测。因此 802.11 改成**先避让再发送**（Collision Avoidance）：

1. 信道空闲且持续 **DIFS** 时间后，进入退避计时。
2. 从 `[0, CW]` 中随机取一个整数作为退避时隙数，每个空闲时隙减 1。
3. 退避计数归零才发送；若途中检测到信道忙，冻结计数，等下一个 DIFS 再继续。
4. 发送完成后等 **SIFS**（比 DIFS 短，保证能抢在别人前面），接收方回 **ACK**。
5. 收到 ACK = 成功，**CW 复位到 CWmin**；超时未收到 = 冲突，**CW 翻倍** `CW = 2×CW + 1`，直到 CWmax。

802.11b 的实测参数：SIFS = 10μs，时隙 = 20μs，DIFS = 50μs（= SIFS + 2×时隙），CWmin = 31，CWmax = 1023。802.11a/g/n/ac 是 OFDM：SIFS = 16μs，时隙 = 9μs，DIFS = 34μs。

**RTS/CTS 与隐藏终端**：A 和 C 都能和 AP 通，但 A、C 互相听不到（隐藏终端），同时发就会在 AP 处撞车。解决方法是 A 先发 **RTS**（Request to Send，20 字节），AP 回 **CTS**（Clear to Send，14 字节），C 能听到 AP 的 CTS，读到其中的 Duration 字段就把自己的 **NAV**（Network Allocation Vector，网络分配矢量）设为该时长、主动闭嘴。代价是每帧多了 RTS+CTS+SIFS 的开销，所以只对大帧或高冲突场景开启。

### 3.4 组网要素：BSS / ESS / SSID / BSSID 与漫游

- **BSS**（Basic Service Set）：一个 AP 及其关联的 STA，是无线的最小单元。
- **BSSID**：AP 射频口的 MAC 地址，唯一标识一个 BSS，抓包时看到的 `wlan.bssid` 就是它。
- **SSID**：网络名，最长 32 字节，就是用户看到的 Wi-Fi 名字；同一 ESS 内所有 AP 的 SSID 相同。
- **ESS**（Extended Service Set）：多个 BSS 用同一个 SSID 连成一片，STA 可以在其中漫游。

**漫游分两层**：切换前后 IP 不变、网关不变，叫**二层漫游**（同 VLAN）；跨 VLAN/子网时 STA 的 IP 会变或需要把流量隧道回原网关，叫**三层漫游**。工程上「漫游掉线」十有八九是跨子网后 DHCP 重来导致秒级中断，而非无线侧问题。

### 3.5 无线安全：从 WEP 到 WPA3

**WEP 为什么废了**：24 位 IV 空间只有 2²⁴，高流量下几小时就耗尽并复用；RC4 的弱密钥加上线性 CRC-32 完整性校验，攻击者能在几分钟内恢复密钥。**WEP 不是「弱」，是「破」**。

**WPA2-PSK 的密钥链**：

```
PMK = PBKDF2-HMAC-SHA1(Passphrase, SSID, 4096 轮, 256 bit)
PTK = PRF-384(PMK, "Pairwise key expansion",
              Min(AA,SPA) || Max(AA,SPA) || Min(ANonce,SNonce) || Max(ANonce,SNonce))
PTK = KCK(16B) + KEK(16B) + TK(16B)      # CCMP 下共 48 字节
```

- **PMK**（Pairwise Master Key）：由口令和 SSID 派生，口令变了或 SSID 变了，PMK 完全不同。
- **PTK**（Pairwise Transient Key）：每次连接都不一样，因为 ANonce/SNonce 随 4 次握手刷新。KCK 算 MIC，KEK 解握手数据，TK 加密数据帧。

**4 次握手（EAPOL-Key）**：
1. AP → STA：发 **ANonce**（随机数）。
2. STA → AP：发 **SNonce** + **MIC**，双方此时都能算出同样的 PTK。
3. AP → STA：发加密的 **GTK**（组密钥，用于广播/组播解密）+ MIC。
4. STA → AP：回 MIC 确认，安装密钥，链路进入加密状态。

**WPA3 的 SAE**：把 PSK 的「口令直接当盐」换成 **SAE**（Simultaneous Authentication of Equals，对等实体同时认证，基于 Dragonfly 握手），实现前向保密——即使口令事后泄露，也解不开此前抓到的流量；并内置抗离线字典攻击。**企业级**则用 **802.1X + EAP**：STA（Supplicant）— AP（Authenticator）— RADIUS 服务器（Authentication Server），RADIUS 走 UDP 1812/1813。

### 3.6 天线与信号强度：dBm / dBi / EIRP / RSSI

```
EIRP(dBm) = 发射功率(dBm) + 天线增益(dBi) − 馈线损耗(dB)
P(dBm) = 10 × log10( P(mW) / 1mW )        # 20dBm=100mW, 23dBm≈200mW, 27dBm≈500mW
```

中国 2.4GHz 的 EIRP 限值 100mW（20dBm），5.15–5.35GHz 与 5.725–5.85GHz 为 200mW（23dBm，室内）。**RSSI**（Received Signal Strength Indicator）是接收电平，常见判据：−30dBm 极佳、−67dBm 是语音/视频下限、−70dBm 一般数据可用、−80dBm 边缘、−90dBm 基本掉线。**SNR**（信噪比）≥ 25dB 才算良好。

自由空间路损（Free Space Path Loss, FSPL）：

```
FSPL(dB) = 32.44 + 20·log10( d(km) ) + 20·log10( f(MHz) )
```

2.4G 信道 6（2437MHz）在 10m 处：`FSPL = 32.44 + 20·log10(0.01) + 20·log10(2437) = 32.44 − 40 + 67.74 = 60.18 dB`。

### 3.7 信道规划与干扰

- **同频干扰**（Co-Channel Interference, CCI）：相邻 AP 用同一信道且覆盖重叠，等于把冲突域扩大，吞吐骤降。
- **邻频干扰**（Adjacent Channel Interference, ACI）：如 2.4G 用信道 1 和 3，两者频谱重叠，比同频更糟（因为无法用 CSMA 正确避让）。
- **非 Wi-Fi 干扰源**：微波炉（2.45GHz）、蓝牙、无绳电话、无线摄像头。用频谱分析或 `Wi-Fi 分析仪` 看底噪，正常底噪约 −95dBm，底噪升到 −85dBm 说明有干扰。
- **规划原则**：2.4G 只排 1/6/11；高密度场景优先 5G/6G；AP 发射功率不宜全开，否则会「越区覆盖」把远端 STA 拉进来、拉低整网速率。

## 四、动手验证

本章 4 个脚本全部零依赖、单文件、不联网，在章节目录下直接 `python3 <脚本名>` 运行。

**1) `csma_ca_sim.py` → 演示 CSMA/CA 竞争与冲突率**

```
$ python3 csma_ca_sim.py
参数: 时隙 20us | SIFS 10us | DIFS 50us | CWmin 31 | CWmax 1023
帧: 载荷 1500 字节 @ 11.0Mbps，占空 1282.9us（其中前导+PLCP 192us，占 15.0%）
零冲突理论上限（无退避）：8.19 Mbps = 物理速率的 74.5%
站数 | 总时长(ms) | 冲突次数 | 冲突率 | 有效吞吐(Mbps) | 速率效率
  1  |     17.60 |     0.0 |   0.0% |          6.82 |    62.0%
  8  |    134.86 |     6.7 |   7.7% |          7.12 |    64.7%
 16  |    284.17 |    25.1 |  13.5% |          6.76 |    61.4%
>>> 结论：站数从 1 增到 16，冲突率单调上升、有效吞吐不再是物理速率 11Mbps。
```

**结论**：即使零冲突，前导+PLCP 的 192μs 固定开销也把 11Mbps 压到 8.18Mbps；站数增加后冲突让吞吐进一步下降，说明**无线是共享介质，容量按并发数摊薄**。

**2) `wifi_standard_table.py` → 各代标准与开销占比**

```
标准                 理论峰值(Mbps)  实测(Mbps)  实测占比  开销占比
802.11ac (Wi-Fi 5)      6933.0        3813.2       55%       45%
802.11ax (Wi-Fi 6)      9607.8        5764.7       60%       40%
```

**结论**：理论峰值里 40%~50% 是前导、IFS、ACK、退避等协议开销；规划容量按「实测 ≈ 理论 × 0.6」估算。

**3) `wpa_psk_derive.py` → PMK / PTK 派生**

```
PMK (256 bit) = ba38ccaf71ac7b09cce425a8a7e636f08d7e3068ab0f44012eba32d0948555f9
PTK (384 bit) = 5f9c70d3400b2c44...ad1a4a4
  ├─ KCK (16B) = ...   ← 用于计算 4 次握手的 MIC
  ├─ KEK (16B) = ...   ← 用于解密握手报文里的 WPA Key Data
  └─ TK  (16B) = ...   ← 真正加密数据帧的 CCMP 会话密钥
  单次 PMK 计算 = 4096 轮 × 2 次 HMAC × 2 次 SHA-1 压缩 = 16384 次压缩
>>> 结论：4096 轮不增加算法强度，只是把单次尝试的成本放大 4096 倍。
```

**结论**：PBKDF2 的 4096 轮只是抬高离线暴破成本；真正防线是口令熵、关闭 WPS、企业网用 802.1X。

**4) `roaming_timeline.py` → 漫游时间线**

```
合计：乐观 1307ms / 典型 1315ms / 悲观 1336ms  →  超出 50ms 预算   （传统 Passive Scan）
合计：乐观 106ms / 典型 402ms / 悲观 524ms    →  超出 50ms 预算   （Active Scan + PMKSA）
合计：乐观 11ms / 典型 30ms / 悲观 70ms       →  满足 50ms 预算   （802.11r FT）
```

**结论**：被动扫描单是扫 13 个信道就要 1300ms；只有 802.11r 快速切换把典型值压到 30ms 才满足语音要求。

## 五、关键字段 / 报文格式解剖

**802.11 MAC 帧头（24 字节基础部分 + 可选字段）**

| 字段 | 长度 | 作用 | 常见取值 |
|---|---|---|---|
| Frame Control · Protocol Version | 2 bit | 协议版本 | 0（至今仍是 0） |
| Frame Control · Type | 2 bit | 帧大类 | 0 管理 / 1 控制 / 2 数据 |
| Frame Control · Subtype | 4 bit | 帧子类型 | 管理 8=Beacon、11=Auth、0=Assoc Req；控制 11=RTS、12=CTS、13=ACK |
| Frame Control · ToDS / FromDS | 1+1 bit | 是否经 DS 转发 | STA→AP：ToDS=1；AP→STA：FromDS=1 |
| Frame Control · Protected | 1 bit | 载荷是否加密 | 1 = 已加密（WPA2 后固定为 1） |
| Duration | 2 字节 | 占用信道时长（μs） | CTS/RTS 用它设置 NAV |
| Address 1 | 6 字节 | 接收方 MAC | — |
| Address 2 | 6 字节 | 发送方 MAC | — |
| Address 3 | 6 字节 | BSSID 或源/目的 | — |
| Sequence Control | 2 字节 | 12 位序号 + 4 位分片号 | 重传时序号不变，分片号递增 |
| Frame Body | 0–2304 字节 | 载荷（上层数据） | — |
| FCS | 4 字节 | CRC-32 校验 | 与以太网同多项式 |

**EAPOL-Key 帧（4 次握手载体）**

| 字段 | 长度 | 作用 | 常见取值 |
|---|---|---|---|
| Descriptor Type | 1 字节 | 密钥描述类型 | 2 = RSN（WPA2） |
| Key Information | 2 字节 | 版本/类型/Install/ACK/MIC/Secure/Encrypted 等标志 | Msg1: 0x008A，Msg2: 0x010A，Msg3: 0x13CA，Msg4: 0x030A |
| Key Length | 2 字节 | 密钥长度 | 16（CCMP） |
| Replay Counter | 8 字节 | 防重放 | 每帧递增 |
| Key Nonce | 32 字节 | ANonce 或 SNonce | 随机 |
| Key MIC | 16 字节 | 完整性校验（KCK 计算） | Msg1 中为全 0 |
| Key Data Length | 2 字节 | 后随 Key Data 长度 | Msg3 携带加密的 GTK |

## 六、易混概念对比

| 概念 A | 概念 B | 核心区别 | 典型场景 |
|---|---|---|---|
| SSID | BSSID | SSID 是网络名字符串，BSSID 是 AP 射频 MAC | 同一个 SSID 下多个 AP 各有一个 BSSID |
| 隐藏终端 | 暴露终端 | 前者「听不到但会撞车」，后者「听得到但不该让」 | A-C 互不可见撞在 AP 处 / B 因听到无关传输而空等 |
| CSMA/CD | CSMA/CA | 有线「先发后检测冲突」，无线「先避让再发」 | 以太网 vs 802.11 |
| 二层漫游 | 三层漫游 | 前者切 AP 后 IP 不变（同 VLAN），后者跨子网需隧道回原网关 | 同一楼层 vs 跨楼栋/跨园区 |
| WPA2-PSK | WPA2-Enterprise | 前者共享口令派生 PMK，后者每人证书/账号走 802.1X 动态派生 | 家庭 / 小型办公 vs 企业园区 |
| 同频干扰 | 邻频干扰 | CCI 是同信道重叠，ACI 是相邻信道频谱重叠（更糟，无法用 CSMA 避让） | 2.4G 用 1/6/11 vs 2.4G 用 1/3/5 |

## 七、工程实践与最佳实践

1. **2.4G 只排 1/6/11**：因为只有这三个中心频率间隔 ≥25MHz、频谱不重叠；混用其它信道会制造邻频干扰，比同频更难排查。
2. **高密度场景把 5G 作为主用频段**：5G 有 13 个不重叠 20MHz 信道（中国可用 36–64 与 149–165），可用信道多、干扰源少，能显著降低 CCI 概率。
3. **AP 发射功率与信道宽度要统一规划，不要全开**：功率越大覆盖越大，但会把远端低速率 STA 拉进来拖慢整网；建议 2.4G 降功率、5G 开 40/80MHz 并做功率对齐。
4. **语音/漫游场景必须开 802.11k/11r/11v**：11k 给邻居列表、11r 做快速切换、11v 由网络侧引导，三者缺一，典型漫游时间从 30ms 涨到 400ms 以上。
5. **同 ESS 的 AP 放同一 VLAN 或做三层漫游**：跨子网后 STA 要重跑 DHCP，几十毫秒的切换会变成几秒中断，用户感知为「掉线」。
6. **关闭 WPS、禁用 WEP/TKIP**：WPS 的 PIN 模式存在暴力破解，TKIP 已被 802.11i 淘汰；合规要求用 WPA2-CCMP 或 WPA3-SAE。
7. **企业网用 802.1X 而非共享 PSK**：PSK 一旦泄露全网沦陷且无法追责；802.1X 可做到一人一密、离职即吊销。
8. **部署前做站点勘测（Site Survey）**：用 RSSI 热力图确认覆盖，用频谱分析确认底噪；底噪升到 −85dBm 说明有非 Wi-Fi 干扰源。
9. **Beacon 间隔设 100ms、DTIM 设 1~3**：Beacon 太长会拖慢扫描，DTIM 太大影响省电终端的下行时延，语音终端建议 DTIM=1。
10. **限制低速率（如关闭 1/2/5.5/11 Mbps 基础速率）**：低速率帧占用空口时间长，会放大「一个慢客户端拖慢全 BSS」的效应。
11. **6GHz（Wi-Fi 6E/7）必须启用 WPA3**：法规要求 6GHz 用 WPA3 才允许工作，且 6GHz 无历史终端干扰，是新部署的首选。
12. **漫游阈值不要靠 RSSI 硬切**：客户端各自实现不同，网络侧应通过 11v BSS Transition 引导，而非依赖信号门限强制踢下线。

## 八、常见陷阱清单

| # | 现象 | 根因 | 排查 / 规避 |
|---|------|------|-------------|
| 1 | 2.4G 很慢但信号满格 | 邻居 AP 同频重叠，CCI 导致退避频繁 | 用 Wi-Fi 分析仪看信道占用，改到 1/6/11 中占用最低的 |
| 2 | 只有某几个位置网速骤降 | 邻频干扰（用了 1 和 3） | 固定只用 1/6/11，不要「自动选信道」跨重叠 |
| 3 | 语音通话切换 AP 时断续 1~2 秒 | 跨子网漫游 + DHCP 重来 | AP 划同 VLAN，或做三层漫游把流量隧道回原网关 |
| 4 | 大量重传、吞吐上不去 | 隐藏终端（STA 之间互相听不到） | 开 RTS/CTS 阈值或降低 AP 功率减少越区覆盖 |
| 5 | 抓包看到 4 次握手在第 2 步失败 | 口令或 SSID 不匹配，MIC 校验失败 | 核对 PSK 与 SSID 大小写/空格；确认不是 WPA3-only 而 STA 只支持 WPA2 |
| 6 | 客户端反复上下线 | 认证成功但 DHCP 分配不到地址 | 查 DHCP 地址池是否耗尽、VLAN 是否正确 |
| 7 | 「AX3000」实际只有几百兆 | 标称是双频/三频速率之和，非单客户端可达 | 按单频段理论 × 0.6 估算，按并发数摊薄容量 |
| 8 | 5G 覆盖明显不如 2.4G | 频率越高穿透与绕射越差 | 5G 靠增加 AP 密度补覆盖，而非加大功率 |
| 9 | 微波炉旁延迟抖动大 | 2.45GHz 非 Wi-Fi 干扰源 | 频谱分析确认后调整信道或物理隔离 |
| 10 | 边缘 STA 拖慢整网 | 低速率客户端占用空口时间过长 | 关闭 1/2/5.5/11Mbps 基础速率，或用 band steering 引导到 5G |
| 11 | 改了 SSID 后部分设备连不上 | PMK 与 SSID 强绑定，缓存失效 | 这是正常行为；WPA3 下需重新配网，属预期 |
| 12 | Beacon 丢失导致频繁扫描耗电 | AP 功率过低或信道冲突 | 保证 AP 间有 15%~20% 覆盖重叠，Beacon 间隔设 100ms |
| 13 | WPA3 过渡模式下老设备报错 | WPA2/WPA3 混合模式对部分芯片兼容差 | 分 SSID 部署，或升级终端固件 |
| 14 | 漫游后视频卡顿但 ping 正常 | TCP 重传恢复慢、或未命中 PMKSA 缓存走完整 802.1X | 开 OKC/PMKSA 缓存，验证是否会重跑认证 |
| 15 | 信道「自动」后半夜变差 | 自动选信道算法只看启动瞬间 | 生产环境固定信道，定期人工复核干扰 |

## 九、自测练习

1. 【计算】802.11ac 单流 80MHz、256-QAM、编码率 5/6、短保护间隔 400ns 下的理论速率是多少？
2. 【计算】AP 发射功率 17dBm，天线增益 6dBi，馈线损耗 1dB，求 EIRP（dBm 与 mW）；在中国 2.4GHz 是否合规？
3. 【计算】2.4GHz 信道 11（2462MHz）在 50m 处的自由空间路损是多少 dB？
4. 【计算】某 STA 用信道 6 收到 −68dBm，底噪 −92dBm，SNR 是多少？是否满足语音要求？
5. 【排障】用户报告「办公室某角落 2.4G 只有几 Mbps，但信号 4 格」，列出至少 3 个可能原因与验证命令。
6. 【排障】语音终端换 AP 后通话中断 1.5 秒，给出你的排查顺序与最可能的根因。
7. 2.4G 为什么只能有 3 个不重叠信道？给出频率计算过程。
8. 说明 RTS/CTS 如何解决隐藏终端，以及它为什么默认不总是开启。
9. WPA2-PSK 中 ANonce/SNonce 的作用是什么？为什么每次连接的 PTK 都不同？
10. 描述 4 次握手每一步的方向、内容与失败后的现象。
11. 对比二层漫游与三层漫游，各自对网络设备有什么要求？
12. 为什么 802.11 用 DIFS + 随机退避，而不是「空闲就立刻发」？

<details>
<summary>参考答案</summary>

1. 信道 80MHz 下有 234 个数据子载波；短 GI 每符号 3.6μs（含 0.4μs GI），每符号承载 234×6=1404 bit，编码率 5/6 → 1404×5/6 = 1170 bit/符号；符号率 = 1/3.6μs = 277.78 ksymbol/s；单流速率 = 1170 × 277.78k ≈ **325 Mbps**。这正是 802.11ac MCS9 单流 80MHz 的 433Mbps（用长 GI 或含开销版本约 390Mbps）量级。

2. `EIRP = 17 + 6 − 1 = 22 dBm`；`P = 10^(22/10) = 158.5 mW`。中国 2.4GHz 限 100mW（20dBm），**超限 2dB**，需把发射功率降到 ≤15dBm（15+6−1=20dBm=100mW）。

3. `FSPL = 32.44 + 20·log10(0.05) + 20·log10(2462)`。`20·log10(0.05) = 20×(−1.301) = −26.02`；`20·log10(2462) = 20×3.3913 = 67.83`；合计 `32.44 − 26.02 + 67.83 = 74.25 dB`。

4. `SNR = −68 − (−92) = 24 dB`。语音要求 SNR ≥ 25dB，**差 1dB，属于临界偏低**，建议核查干扰或调整 AP 位置。

5. 可能原因：①同频/邻频干扰导致退避频繁（验证：Wi-Fi 分析仪看信道占用与底噪）；②隐藏终端导致 AP 处冲突（验证：抓包看重传率与 RTS/CTS 是否生效）；③低速率客户端拖慢空口（验证：看关联速率与 Airtime 占比）。验证命令：`netsh wlan show interfaces`（Windows）/ macOS `option+点 Wi-Fi 图标` 看信道与速率，或 AP 侧 `show ap client detail`。

6. 排查顺序：先确认是否跨子网（对比切换前后 IP/网关）→ 看是否重跑 DHCP（抓包找 DISCOVER）→ 查是否 11r 未开导致完整认证（抓包看 EAP 往返）→ 查 PMKSA 缓存是否命中。最可能根因：**跨 VLAN 漫游 + DHCP 重来**，表现为 ARP/DHCP 报文在切换后出现。

7. 2.4G 单信道 20MHz 有效带宽约 22MHz，而中心频率间隔仅 5MHz。要两个信道不重叠，信道号差需满足 `5×Δch ≥ 25`（20MHz 带宽 + 保护间隔），即 Δch ≥ 5。范围 1~13 内取 1、6、11 三组，Δch=5，正好 25MHz，共 **3 个**不重叠信道。

8. 隐藏终端 A、C 互不可见却都能到 AP，同时发射会在 AP 处撞车。A 先发 RTS，AP 广播 CTS，C 收到 CTS 后按 Duration 设置 NAV 主动退让，从而避免冲突。默认不总开启是因为 RTS+CTS+SIFS 增加固定开销，小帧场景下开销占比过高反而降低吞吐，通常用阈值只对大帧启用。

9. ANonce 是 AP 生成的 32 字节随机数，SNonce 是 STA 生成的 32 字节随机数，两者一起作为 PTK 派生的输入。由于每次握手 nonce 都重新随机，即使口令、SSID、双方 MAC 都不变，派生出的 PTK 也不同，从而保证每条连接的会话密钥独立（前向保密的基础）。

10. Msg1 AP→STA 发 ANonce；Msg2 STA→AP 发 SNonce+MIC（此时双方算出 PTK）；Msg3 AP→STA 发加密的 GTK+MIC；Msg4 STA→AP 回 MIC 并安装密钥。若 Msg2 的 MIC 校验失败 → 口令/SSID 错；若卡在 Msg3/Msg4 → 密钥安装或加密套件协商问题；若一直无 Msg1 → 关联或认证阶段就没通过。

11. 二层漫游：所有 AP 在同一 VLAN，切 AP 前后 IP/网关不变，依赖 AC 或交换机做同广播域的二层通路。三层漫游：AP 在不同子网，STA 的 IP 会变或需把流量隧道回原网关（如 CAPWAP 隧道到 AC），要求 AC 支持隧道与移动域（mobility domain）配置。

12. 「空闲就立刻发」会让多个 STA 在同一时刻同时发送，冲突概率极高且无法感知。DIFS 保证高优先级帧（ACK）优先，随机退避让不同 STA 错开时刻，显著降低同时发送概率；冲突发生后 CW 翻倍进一步降低再次冲突概率。这是「用时间换冲突概率」的设计。

</details>

## 十、命令与配置速查

| 用途 | Cisco 风格 | 华为风格 | Linux / macOS 主机侧 |
|---|---|---|---|
| 扫描周边 AP | `show ap summary` | `display ap all` | macOS：`/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s`；Linux：`nmcli dev wifi list` |
| 查看关联客户端 | `show ap client detail` | `display station all` | `netsh wlan show interfaces`（Windows） |
| 查看信道与速率 | `show ap dot11 5ghz summary` | `display wlan radio-info` | macOS：`option` + 点 Wi-Fi 图标 |
| 配置 SSID / WPA2 | `wlan ssid-profile NAME` → `wpa2-psk` | `security-profile name NAME` → `security wpa2 psk` | — |
| 查看 802.1X 认证 | `show dot1x all` | `display dot1x` | `wpa_supplicant -Dnl80211 -i wlan0 -c conf` |
| 抓无线管理帧 | `monitor capture`（或 AP 镜像） | `capture-packet` | macOS：`sudo tcpdump -i en0 -y IEEE802_11 -c 20` |
| 查看漫游事件 | `show ap client roaming` | `display station roam-record` | 日志：`log show --predicate 'subsystem=="com.apple.wifi"'` |
| 查看干扰/底噪 | `show ap cleanair`（Cisco CleanAir） | `display wlan interference` | 频谱分析仪 / Wi-Fi 分析类 App |
| 查看邻居 AP（11k） | `show ap neigh` | `display wlan neighbor` | — |
| 配置 11r 快速切换 | `dot11 802.11r` / `wlan mobility` | `ft enable`（模板内） | 终端侧自动 |

## 十一、本章示例索引

| 文件 | 一句话说明 | 运行 |
|------|-----------|------|
| `csma_ca_sim.py` | 模拟 N 个站点 CSMA/CA 竞争，统计冲突率与有效吞吐 | `python3 csma_ca_sim.py` |
| `wifi_standard_table.py` | 802.11 a/b/g/n/ac/ax/be 速率与信道对照，算协议开销占比 | `python3 wifi_standard_table.py` |
| `wpa_psk_derive.py` | PBKDF2 派生 PMK、PRF 派生 PTK，演示 4096 轮的成本意义 | `python3 wpa_psk_derive.py` |
| `roaming_timeline.py` | 漫游五阶段时间线分解，对齐 50ms 语音预算给优化建议 | `python3 roaming_timeline.py` |

---

⬅️ 上一章：[第 04 章 以太网与交换技术](../04-以太网与交换技术/README.md) ｜ ➡️ 下一章：[第 06 章 IPv4 地址与子网划分](../06-IPv4地址与子网划分/README.md) ｜ 🏠 [返回总目录](../README.md)
