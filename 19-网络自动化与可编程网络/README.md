# 第 19 章 · 网络自动化与可编程网络

> **一句话定位**：本章解决「网络配置靠人肉敲、改完不知道变了什么、出错难回滚」的问题——读完后你能读懂 NETCONF/YANG 数据模型、算出 SNMP 轮询与遥测的规模差异、写出声明式合规检查，并理解 SDN 的控制面/数据面分离。
> **前置知识**：第 08 章 路由基础与静态路由、第 16 章 运维类应用协议（SNMP/Syslog）、第 18 章 网络排障与抓包分析 ｜ **难度**：★★★ ｜ **建议投入**：150 分钟

## 一、学习目标

1. 能说明「人肉 CLI 配置」的三大问题（不一致、不可审计、不可回滚）以及自动化如何解决。
2. 能构造并解析 NETCONF 的 `<get-config>` / `<edit-config>` / `<commit>` 报文，并按 YANG 路径提取字段。
3. 能算出给定设备规模下 SNMP 轮询与流式遥测的带宽、时延差异，并给出选型结论。
4. 能对比 Netmiko / NAPALM / Ansible / Terraform 四种工具链的适用场景与连接方式。
5. 能描述 SDN 的控制平面与数据平面分离、OpenFlow 流表 match-action 结构，以及南北向接口的分工。
6. 能写出声明式意图规则并对配置文本做合规扫描，识别高危变更并给出修复建议。

## 二、核心概念总览

自动化的本质是**把「期望状态」变成可重复执行、可验证、可回滚的流程**。下图给出工具链分层：

```
  ┌──────────────────────── 意图 / 期望状态（人类书写的声明）────────────────────────┐
  │   "所有接入口必须划分 VLAN 且关闭 DTP"    "核心设备 OSPF 必须认证"                │
  └──────────────────────────────────┬───────────────────────────────────────────────┘
                                     │  北向接口（Northbound）
  ┌──────────────────────────────────▼───────────────────────────────────────────────┐
  │  编排与工具层：Ansible(playbook) / Terraform(state) / 自研平台 / CI 流水线        │
  └──────────────────────────────────┬───────────────────────────────────────────────┘
                                     │  南向接口（Southbound）
   ┌─────────────┬─────────────┬─────▼───────┬──────────────┬─────────────────────────┐
   │ NETCONF     │ RESTCONF    │ gNMI/gRPC   │ SNMP         │ CLI over SSH            │
   │ XML+候选配置 │ HTTP+YANG   │ 遥测/订阅    │ 轮询/TRAP    │ Netmiko/expect          │
   │ 事务+回滚    │ 无状态       │ 秒级push     │ 分钟级pull   │ 最通用、最脆弱          │
   └─────────────┴─────────────┴─────────────┴──────────────┴─────────────────────────┘
                                     │
  ┌──────────────────────────────────▼───────────────────────────────────────────────┐
  │  设备侧：running-config / candidate-config / startup-config 三份配置 + YANG 模型   │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

三种「配置态」的关系：

| 配置 | 含义 | 特点 |
|---|---|---|
| running-config | 当前生效配置，内存中 | 重启即丢失 |
| candidate-config | 候选配置，可修改后再提交 | 支持事务与校验，NETCONF 特有 |
| startup-config | 开机加载配置，持久化 | `copy run start` / `<copy-config>` 写入 |

统一使用的教学网段：办公网 `192.0.2.0/24`、对外服务 `198.51.100.0/24`、骨干 `203.0.113.0/24`。

## 三、机制详解

### 3.1 自动化要解决的问题

**人肉 CLI 配置的三个致命问题**：

1. **不一致（Drift）**：同一批交换机上线时漏敲一条命令，半年后没人知道差异在哪，故障时才暴露。
2. **不可审计**：谁在什么时候改了什么，只在终端回滚缓冲里，出了事无从追溯。
3. **不可回滚**：改错了要一条条敲回去，恢复时间取决于工程师的记忆。

**自动化的三个目标**：配置由**模板 + 变量**生成（保证一致性）、每次变更**留痕**（保证可审计）、变更前**先备份 + 具备一键回滚**（保证可恢复）。

自动化能力成熟度可以分四级：**手工 CLI → 脚本化（Netmiko）→ 声明式（Ansible/NETCONF）→ 意图驱动 + 闭环校验**。级别越高，人介入越少、越依赖数据模型而非命令字符串。

### 3.2 NETCONF / YANG / RESTCONF

**NETCONF（Network Configuration Protocol，RFC 6241）** 把配置操作用 RPC 标准化：

| 操作 | 作用 | 关键点 |
|---|---|---|
| `<get>` | 读配置 + 状态数据 | 包含 state 数据（计数器等） |
| `<get-config>` | 只读配置数据 | 必须指定 `<source>`（running/candidate/startup） |
| `<edit-config>` | 修改配置 | 属性 `operation` = merge / replace / create / delete |
| `<commit>` | 把候选配置提交为运行配置 | 配合 `confirmed-commit` 可定时自动回滚 |
| `<lock>` / `<unlock>` | 锁定配置数据 | 防止多人并发修改同一份配置 |

NETCONF 用 XML 承载，分层为：传输层（SSH，端口 830）→ 消息层（`<rpc>` / `<rpc-reply>`）→ 操作层（`get-config` 等）→ 内容层（YANG 数据）。

**YANG（RFC 6020/7950）** 是数据建模语言，定义配置数据的**树形结构**。每个叶子节点都有确定的路径，例如接口的启用状态是 `/interfaces/interface/enabled`，MTU 是 `/interfaces/interface/mtu`。CLI 的 `shutdown` 命令在 YANG 里对应 `enabled = false` —— 这是「命令 → 数据」的思维转换。

**RESTCONF（RFC 8040）** 把 YANG 映射到 HTTP 方法：`GET` = 读、`POST` = 创建、`PUT` = 替换、`PATCH` = 合并、`DELETE` = 删除，路径就是 YANG 路径。例如 `GET /restconf/data/ietf-interfaces:interfaces`。

### 3.3 SNMP 轮询 vs 流式遥测

**SNMP 轮询（Pull）**：网管每隔一段时间向设备逐个（或用 GetBulk 批量）请求 OID。问题是**滞后等于轮询周期**，且周期越短、设备 CPU 与网络带宽压力越大。

**流式遥测（Push / gNMI / gRPC）**：设备与采集器建立长期订阅，**指标变化时主动推送**。优势是秒级感知、设备侧控制采样频率、无「拉取风暴」。

关键量化差异（5000 台设备 × 200 个指标，详见 §四）：

- 相同 300 秒滞后下，逐 OID 轮询 5.87 Mbit/s，GetBulk 3.59 Mbit/s，遥测（10% 变化）1.07 Mbit/s。
- 若把 SNMP 压到 10 秒周期，带宽飙到 176 Mbit/s；同样 10 秒刷新，遥测只需 32 Mbit/s。

所以选型不是「哪个省带宽」，而是**实时性要求与设备能力的匹配**：核心/出口走遥测，老设备退回 SNMP GetBulk。

### 3.4 自动化工具链对比

| 工具 | 连接方式 | 幂等性 | 适用场景 | 局限 |
|---|---|---|---|---|
| Netmiko | SSH + CLI（`network_cli`） | 无（自己写判断） | 老设备、无 API 设备 | 解析回显脆弱、无事务 |
| NAPALM | 多厂商统一 API（CLI/NETCONF） | 部分 | 多厂商混合环境 | 支持型号有限 |
| Ansible | `network_cli` / `netconf` / `httpapi` | 有（模块级） | 批量下发、配置模板 | 大量设备时串行慢，需 fork/并发 |
| Terraform | 厂商 provider（HTTP/NETCONF） | 有（state 文件） | 云网资源、声明式生命周期 | 网络设备 provider 成熟度参差 |
| 自研 Python | 任意（含 gNMI） | 自己实现 | 复杂编排、闭环校验 | 维护成本高 |

**幂等性（Idempotency）** 是核心概念：同一个 playbook 跑一次和跑十次，结果必须一致。CLI 的 `switchport access vlan 100` 是幂等的（重复执行无害），但 `no vlan 100` 后再 `vlan 100` 就会清空该 VLAN 的其它属性 —— 这就是为什么声明式工具比命令拼接更安全。

### 3.5 SDN 架构与 OpenFlow

**SDN（Software-Defined Networking）** 的核心是**控制平面与数据平面分离**：

- **数据平面（转发面）**：只按流表转发，不做路由决策。
- **控制平面**：集中计算路径并下发流表。
- **南向接口**：控制器 ↔ 设备，典型是 **OpenFlow**。
- **北向接口**：控制器 ↔ 应用/编排，通常是 REST API。

**OpenFlow 流表**是 `match + action` 结构：报文进入交换机后按优先级匹配流表项（match 字段包括入端口、源/目的 MAC、源/目的 IP、TCP/UDP 端口、VLAN ID、以太网类型等），命中后执行 action（转发到某端口、丢弃、改字段、送到控制器）。未命中则发 packet-in 给控制器（或按 table-miss 流表项处理）。

**Open vSwitch（OVS）** 是开源虚拟交换机，广泛用于云平台，支持 OpenFlow 与 OVSDB 两种管理接口。

### 3.6 配置安全与治理

**为什么重要**：自动化的风险是「批量出错」——一条错模板能在几秒内摧毁整个网络。治理手段：

1. **配置备份与版本管理**：每次变更前自动拉取运行配置入库（Git），变更有历史、可对比。
2. **金标准模板 + 差异审计**：以模板渲染出「期望配置」，与实际运行配置做 diff，差异就是配置漂移。
3. **变更审批与回滚预案**：高危变更（`shutdown`、删除 ACL、默认路由变更）必须人工复核，并准备回滚配置。
4. **CI/CD 化的网络变更**：配置提交到 Git → 触发流水线 → 语法/合规检查 → 实验室验证 → 分批灰度 → 生产下发。

### 3.7 CI/CD 化的网络变更

一条典型流水线：

```
开发者提交配置变更(PR) -> 分支触发 CI:
  1) 语法与模板检查（渲染是否成功）
  2) 合规检查（意图规则扫描，见 §四 intent_check.py）
  3) 与生产运行配置做 diff（看影响面）
  4) 高危变更人工审批（门禁）
  5) 实验室/仿真环境验证
  6) 分批灰度下发（先 1 台 -> 10% -> 全量）
  7) 下发生效后用 NETCONF get / 遥测回读校验，不一致则自动回滚
```

关键点：**每一步都必须有「失败即停 + 自动回滚」**，这是自动化能用于生产的前提。

### 3.8 数据模型、幂等性与闭环

自动化要真正闭环，必须有**回读校验**：下发后重新读取设备状态，与期望状态比较。NETCONF 的 `get-config` 返回结构化数据，正是为此而生。CLI 方案做回读校验只能靠正则解析回显，脆弱且易漏。

## 四、动手验证

### 4.1 `netconf_yang.py` —— 构造 NETCONF 请求并解析 YANG 路径

运行：

```
python3 netconf_yang.py
```

关键输出片段：

```
  <rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
    <get-config>
      <source>
        <running />
      </source>
      <filter type="subtree">
        <if:interfaces>
          <if:interface />
        </if:interfaces>
      </filter>
    </get-config>
  </rpc>
```

从输出看出：脚本用 `xml.etree.ElementTree` + 命名空间构造出合法的 `get-config` 请求，再解析一段 `<rpc-reply>`，按 YANG 路径提取每个接口的 `name / description / enabled / mtu / ipv4/address`，并给出 CLI 命令到 YANG 路径的对照。

### 4.2 `config_diff.py` —— 配置版本比对与高危标记

运行：

```
python3 config_diff.py
```

关键输出片段：

```
  - transport input ssh
  + transport input telnet
类别        动作      内容                                          风险
interface 新增       shutdown                                   高危: 接口将被关闭，业务直接中断
route     新增      ip route 0.0.0.0 0.0.0.0 203.0.113.6        高危: 默认路由变更，影响全局可达性
security  新增       transport input telnet                     高危: 明文登录，安全降级
```

从输出看出：脚本用 `difflib.unified_diff` 生成标准 diff，再把每条变更按「接口 / 路由 / ACL / 安全」分类，并标记高危项（`shutdown`、`transport input telnet`、默认路由变更、VLAN 变更、ACL deny 新增）。

### 4.3 `telemetry_vs_poll.py` —— SNMP 轮询与遥测的规模对比

运行：

```
python3 telemetry_vs_poll.py
```

关键输出片段：

```
方式                                        带宽      采集滞后相对基线
SNMP 逐 OID                       5.87 Mbit/s       300    100.0%
SNMP GetBulk                     3.59 Mbit/s       300     61.3%
遥测(仅变化 10%)                      1.07 Mbit/s       300     18.2%
>>> 推导：把 SNMP 轮询周期压到 10 秒，带宽 = 209.81 MB × 8 / 10 = 176.00 Mbit/s
>>> 同样 10 秒刷新，遥测只需 32.00 Mbit/s，差距 5.5 倍
```

从输出看出：脚本按 5000 台设备 × 200 个指标逐项推导带宽，把三种方式统一到 300 秒窗口做公平对比，并给出遥测在不同上报周期下的带宽曲线。

### 4.4 `intent_check.py` —— 声明式合规检查

运行：

```
python3 intent_check.py
```

关键输出片段：

```
  [违规 1 处] R2 接入口必须关闭 DTP
      ! (高) GigabitEthernet0/1: 接入口未关闭 DTP，可能被协商成 Trunk（VLAN Hopping 风险）
序号   级别    对象                      问题                                      修复建议
2    高     GigabitEthernet0/1      接入口未关闭 DTP，可能被协商成 Trunk（VLAN Hoppin...  补充: switchport nonegotiate
>>> 结论：共 7 处违规（高危 4、中危 3）；高危项必须先修复再上线
```

从输出看出：脚本把「意图」写成 6 条规则，扫描示例配置文本，逐条给出违规对象、问题描述与修复命令；其中 `enable password`、`transport input telnet`、未关 DTP 被标为高危。

## 五、关键字段 / 报文格式解剖

### 5.1 NETCONF `<rpc>` 报文结构

| 层级 | 元素 | 作用 | 常见取值 |
|---|---|---|---|
| 传输层 | SSH 830 / TLS | 承载 NETCONF | 默认端口 830 |
| 消息层 | `<rpc>` / `<rpc-reply>` | 请求与响应容器 | `message-id` 做请求匹配 |
| 操作层 | `<get-config>` | 读配置 | `<source>` 指定数据源 |
| 数据源 | `<running/>` / `<candidate/>` / `<startup/>` | 目标配置库 | 三者任选 |
| 过滤 | `<filter type="subtree">` | 只取关心的子树 | 也可用 XPath |
| 内容层 | `<interfaces>` 等 | 实际配置数据 | 命名空间来自 YANG 模块 |

### 5.2 `<edit-config>` 的 operation 属性

| 属性值 | 含义 | 注意 |
|---|---|---|
| `merge` | 合并（默认） | 只覆盖指定的叶子节点 |
| `replace` | 替换 | 未提及的节点可能被清空 |
| `create` | 创建 | 已存在则报错 |
| `delete` | 删除 | 不存在则报错 |
| `remove` | 移除 | 不存在也不报错 |

### 5.3 YANG 与 CLI 字段对照

| CLI 命令 | YANG 路径 | 数据类型 |
|---|---|---|
| `interface Gi0/0` | `/interfaces/interface/name` | string |
| ` ip address 192.0.2.1 255.255.255.0` | `/interfaces/interface/ipv4/address/ip` + `prefix-length` | inet:ipv4-address + uint8 |
| ` mtu 1500` | `/interfaces/interface/mtu` | uint16 |
| ` shutdown` | `/interfaces/interface/enabled` = false | boolean |
| ` description Uplink` | `/interfaces/interface/description` | string |

## 六、易混概念对比

| 概念 A | 概念 B | 核心区别 | 典型场景 |
|---|---|---|---|
| SNMP 轮询 | 流式遥测 | 前者 Pull、滞后一个周期；后者 Push、变化即报 | 老设备轮询 vs 核心设备遥测 |
| NETCONF | RESTCONF | 前者基于 SSH/XML、有候选配置与事务；后者基于 HTTP、无状态 | 事务性配置 vs 简单读取 |
| CLI 命令 | YANG 数据 | 命令是过程式的、厂商相关；数据是声明式的、有模型 | 脚本拼命令 vs 声明期望状态 |
| Ansible | Terraform | 前者过程式 playbook、无状态；后者声明式、有 state 文件 | 批量配置 vs 资源生命周期 |
| OpenFlow 流表 | 路由表 | 流表按五元组+更多字段 match-action；路由表按目的网段选下一跳 | SDN 转发 vs 传统转发 |
| 幂等 | 可重复 | 幂等要求重复执行结果一致；可重复只要求能再跑一次 | 配置模板判定 |

## 七、工程实践与最佳实践

1. **变更前必须自动备份运行配置到版本库**。因为一旦下发失败，唯一可靠的恢复依据是变更前的完整配置快照，而非记忆。
2. **优先用 NETCONF/RESTCONF 而非 CLI 自动化**。因为结构化数据可校验、可回读、有事务；CLI 回显解析会在设备版本升级后突然失效。
3. **配置由模板 + 变量生成，禁止手改生成物**。因为手改会破坏一致性，下次自动下发就把它覆盖了，问题被隐藏。
4. **所有变更走 CI 流水线并设置高危门禁**。因为 `shutdown`、删除 ACL、默认路由变更这类操作一旦批量出错，影响是灾难性的。
5. **灰度下发：先 1 台、再 10%、最后全量**。因为模板在实验室通过不代表生产可用，灰度能在小范围暴露问题。
6. **下发后必须回读校验（闭环）**。因为设备可能因资源不足静默丢弃配置，只有回读才能确认「实际状态 = 期望状态」。
7. **遥测只订阅关键指标，不要全量推**。因为全量推会把带宽放大数十倍（本例 10.67 vs 1.07 Mbit/s），得不偿失。
8. **SNMP 必须用 GetBulk 而非逐 OID Get**。因为逐 OID 的请求头开销占了大头，GetBulk 可省约 39% 流量。
9. **轮询周期与告警时效要求匹配**。因为 5 分钟轮询对流量突增类告警毫无意义，这类指标必须走遥测。
10. **合规规则要版本化并纳入 CI**。因为安全基线会演进，规则不版本化就无法追溯「某次放行是依据哪版规则」。
11. **自动化账号用最小权限 + 独立 AAA**。因为自动化凭据一旦泄露，等于交出全网配置权限；应限制其只能改授权范围。
12. **保留人工兜底通道（带外管理）**。因为自动化把网络改挂时，你需要一条不依赖被改设备的恢复路径。

## 八、常见陷阱清单

| # | 现象 | 根因 | 排查 / 规避 |
|---|------|------|-------------|
| 1 | Ansible 跑完显示 ok 但配置没变 | 模块认为状态已符合，跳过执行 | 加 `--diff` 看实际改动，或核对幂等判定逻辑 |
| 2 | CLI 自动化在设备升级后集体失败 | 回显格式变化导致正则失配 | 改用 NETCONF/RESTCONF 结构化接口 |
| 3 | NETCONF edit-config 报 data-missing | 父节点未创建就写子节点 | 按树自顶向下创建，或用 merge 语义 |
| 4 | commit 后配置没生效 | 只改了 candidate 未 commit | 检查是否漏了 `<commit>`；或用 confirmed-commit |
| 5 | 批量下发把整个网段配错 | 模板变量传错且无灰度 | 加变量校验 + 先 1 台灰度 + 自动回滚 |
| 6 | 遥测订阅后采集器 CPU 打满 | 订阅了全量指标、频率过高 | 只订阅关键路径，降低采样频率 |
| 7 | SNMP 轮询把设备 CPU 拉高 | 周期过短、逐 OID Get | 用 GetBulk，周期不低于 60 秒，错峰轮询 |
| 8 | 配置漂移无人发现 | 没有金标准模板与差异审计 | 定期渲染模板与运行配置 diff，告警差异 |
| 9 | 回滚时发现没备份 | 变更前未自动拉取配置 | 流水线第一步固定做配置备份入库 |
| 10 | 自动化凭据泄露 | 密码明文写在脚本里 | 用 vault / 密钥管理，脚本只引用变量 |
| 11 | 幂等脚本反而破坏配置 | 用 `no` + 重建的方式「重置」 | 改成声明式设置，避免清空未提及的属性 |
| 12 | 高危变更无人复核就上线 | 流水线缺门禁 | 按规则标记高危，卡审批才能继续 |
| 13 | 多厂商环境同一脚本行为不一致 | YANG 模型/命令语法差异 | 用 NAPALM 等抽象层，或按厂商分支处理 |
| 14 | 并发下发导致配置冲突 | 多人/多任务同时改同一设备 | 下发前 `<lock>` 锁定配置数据 |
| 15 | 实验室验证通过、生产失败 | 实验室设备版本与生产不一致 | 记录并同步设备版本，把版本纳入验证矩阵 |

## 九、自测练习

1. 计算：5000 台设备 × 200 个指标，SNMP 逐 OID 轮询（请求 100B、响应 120B/个），周期 300 秒，求平均带宽。
2. 计算：同上规模改用 GetBulk（每包 25 个 OID，请求 120B、每 OID 条目 130B），求平均带宽与相对逐 OID 的节省比例。
3. 计算：若把问题 1 的轮询周期从 300 秒压到 10 秒，带宽变为多少？与 10 秒上报、仅推 10% 变化的遥测（每条 400B）相比如何？
4. 写出读取设备 `running` 配置中接口子树的 NETCONF `get-config` 报文骨架（外层 `rpc` + `source` + `filter`）。
5. 说明 `merge` 与 `replace` 在 `<edit-config>` 中的区别，以及各自的危险点。
6. 排障：某 Ansible playbook 显示 `changed=0` 但设备配置明显不符，列出两种原因与验证方法。
7. 排障：NETCONF 下发后设备配置没变化，但 RPC 返回 `<ok/>`，如何定位？
8. 计算：一条配置模板渲染需要 0.2 秒，网络下发每台 3 秒，串行处理 500 台设备总耗时多少？如何优化？
9. 解释为什么「CLI 自动化」比「NETCONF 自动化」在长期维护上更脆弱。
10. 给出把网络变更做成 CI/CD 流水线的 5 个关键阶段，并说明每阶段的失败处理。

<details>
<summary>参考答案</summary>

**1.** 逐 OID 轮询带宽。

- 单机单周期字节：`200 × (100 + 120) = 200 × 220 = 44000 B`
- 全网单周期：`44000 × 5000 = 220,000,000 B = 209.81 MB`
- 平均带宽：`220,000,000 × 8 / 300 = 5,866,667 bit/s ≈ 5.87 Mbit/s`

**2.** GetBulk 带宽与节省。

- 每包 OID 数 25，需包数 `ceil(200 / 25) = 8`
- 单包字节：`120 + 25 × 130 = 120 + 3250 = 3370 B`
- 单机单周期：`8 × 3370 = 26,960 B`
- 全网单周期：`26960 × 5000 = 134,800,000 B = 128.56 MB`
- 带宽：`134,800,000 × 8 / 300 = 3,594,667 bit/s ≈ 3.59 Mbit/s`
- 节省比例：`(220,000,000 - 134,800,000) / 220,000,000 = 38.7%`

**3.** 压缩周期与遥测对比。

- SNMP 压到 10 秒：`220,000,000 × 8 / 10 = 176,000,000 bit/s = 176 Mbit/s`
- 遥测（10% 变化、10 秒、每条 400B）：
  - 单机单次上报：`200 × 0.10 × 400 = 8000 B`
  - 全网单次上报：`8000 × 5000 = 40,000,000 B`
  - 带宽：`40,000,000 × 8 / 10 = 32,000,000 bit/s = 32 Mbit/s`
- 差距：`176 / 32 = 5.5 倍`，即同刷新率下遥测需要的带宽只有 SNMP 的约 18%。

**4.** 报文骨架。

```xml
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
  <get-config>
    <source>
      <running/>
    </source>
    <filter type="subtree">
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface/>
      </interfaces>
    </filter>
  </get-config>
</rpc>
```

关键点：`<source>` 指定数据源为 `running`；`<filter type="subtree">` 只取 `interfaces` 子树；命名空间必须与被查询的 YANG 模块一致。

**5.** merge 与 replace。

- `merge`（默认）：只覆盖报文中出现的叶子节点，未提及的节点保持原值。危险点：删不掉配置，想移除一条规则必须显式 delete。
- `replace`：把目标节点整体替换，报文中未出现的子节点会被清空/置默认。危险点：一次 replace 一个父节点可能误删该节点下所有未写出的配置（如整段接口配置）。

**6.** `changed=0` 但配置不符的原因与验证。

1. **幂等判断逻辑与实际状态不符**：模块用某个属性判断「已达标」，但该属性并不代表真实配置。验证：加 `--diff --check` 查看模块的具体比较内容。
2. **连错设备或命名空间/登录虚终端不同**：playbook 的 inventory 指向了另一台设备。验证：在任务里加 `debug` 输出 `hostname` 与 `ansible_host`，或单独 `-l 单台` 重跑。
3. 补充可能：设备上配置在别的连接上下文（如不同 VRF）里，模块读取路径不对。验证：手工用 NETCONF `get-config` 回读该路径确认。

**7.** RPC 返回 `<ok/>` 但配置未生效的定位。

1. 确认改的是哪份配置：`<edit-config>` 的 `<target>` 若是 `candidate`，必须再发 `<commit>` 才进 running。这是最常见原因。
2. 用 `<get-config>` 回读目标路径，确认 candidate 里到底有没有改进去。
3. 检查是否被其它进程/策略覆盖（如设备有自动配置回滚、或另一个管理系统在持续纠正）。
4. 检查 `<error-option>` 与设备日志，部分实现会「尽力而为」跳过失败节点。

**8.** 串行总耗时与优化。

- 串行：`500 × 3 = 1500 秒 = 25 分钟`（模板渲染 0.2s 相对可忽略）。
- 优化：
  1. **并发下发**（Ansible `forks` / 异步任务），把 500 台分成 N 组并行。理论上 `1500 / N` 秒。
  2. **减少下发量**：只下发 diff（changed 部分），未变化设备跳过。
  3. **灰度分批**：先 1 台验证，再 10%，最后全量，既快又安全。
  4. 注意设备侧并发限制与 AAA 服务器承载，别把自动化变成 DDoS。

**9.** CLI 自动化脆弱的原因。

- CLI 是**面向人的文本界面**，回显格式（空格、提示符、分页 `--More--`）随版本、语言、终端设置变化，正则解析容易失配。
- 命令是**过程式**的，没有「期望状态」概念，脚本必须自己判断当前状态再决定敲什么，逻辑复杂且易错。
- 没有**事务与回滚**，一条命令敲错立即生效，无法原子提交。
- 相比之下 NETCONF/YANG 提供**结构化数据 + 数据模型 + 候选配置 + commit/rollback**，解析稳定、有事务、可回读校验，长期维护成本低得多。

**10.** CI/CD 五阶段与失败处理。

1. **语法与模板渲染**：渲染失败 → 直接终止，不产生任何变更。
2. **合规检查**（意图规则扫描）：发现高危违规 → 卡住，需人工审批放行或修复。
3. **差异分析**：与生产运行配置 diff；若出现未预期的差异 → 告警并人工确认。
4. **灰度下发**（1 台 → 10% → 全量）：每批下发后用 NETCONF 回读校验；任一批失败 → 停止后续批次并自动回滚已下发设备。
5. **闭环校验与记录**：回读比对期望状态，不一致则自动回滚并在工单留痕。

</details>

## 十、命令与配置速查

| 用途 | 主机侧 / 工具侧 | 设备侧（Cisco / 华为） |
|---|---|---|
| 备份配置 | `ansible -m ios_command -a "commands='show running-config'"` | `show running-config` / `display current-configuration` |
| 保存配置 | `ncclient` `<copy-config>` | `copy running-config startup-config` / `save` |
| NETCONF 探测 | `ssh -p 830 user@host -s netconf` | `netconf-yang`（开启） / `netconf` |
| RESTCONF 读取 | `curl -k -u u:p https://host/restconf/data/ietf-interfaces:interfaces` | `restconf`（开启） |
| gNMI 订阅 | `gnmic -a host:57400 -u u -p p subscribe --path /interfaces` | `telemetry` / `grpc`（开启） |
| SNMP 查询 | `snmpwalk -v2c -c public host 1.3.6.1.2.1.1` | `snmp-server community public RO` / `snmp-agent community read` |
| 查看配置差异 | `diff -u old.cfg new.cfg` | `show archive config differences` |
| 配置回滚 | Git `git checkout` + 重新下发 | `configure replace` / `rollback configuration` |
| 查看接口状态 | `gnmic subscribe --path /interfaces/interface/state` | `show interfaces` / `display interface` |
| 并发下发 | `ansible-playbook -f 20 site.yml` | — |
| 校验 YANG | `pyang -f tree model.yang` | — |

## 十一、本章示例索引

| 文件 | 一句话说明 | 运行 |
|------|-----------|------|
| `netconf_yang.py` | 构造 NETCONF get-config 请求并解析 config 响应 | `python3 netconf_yang.py` |
| `config_diff.py` | 配置版本 unified diff + 分类 + 高危变更标记 | `python3 config_diff.py` |
| `telemetry_vs_poll.py` | SNMP 轮询与流式遥测的带宽/时延规模对比 | `python3 telemetry_vs_poll.py` |
| `intent_check.py` | 声明式意图规则合规扫描与修复建议 | `python3 intent_check.py` |

---

⬅️ 上一章：[第 18 章 网络排障与抓包分析](../18-网络排障与抓包分析/README.md) ｜ ➡️ 下一章：[第 20 章 网络虚拟化与云网络](../20-网络虚拟化与云网络/README.md) ｜ 🏠 [返回总目录](../README.md)
