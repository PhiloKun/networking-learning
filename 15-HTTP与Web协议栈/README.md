# 第 15 章 · HTTP 与 Web 协议栈

> **一句话定位**：本章把「浏览器地址栏回车之后发生了什么」拆到字节级：从 HTTP/1.1 的报文格式与缓存语义，到 HTTP/2 二进制分帧、HTTP/3 基于 QUIC 的多路复用，再到 HTTPS 的 TLS 1.3 握手与 HKDF 密钥派生；读完能手撕 HTTP 报文、能判定缓存该走强缓存还是协商缓存、能解释 HTTPS 为什么安全。
> **前置知识**：第 12 章 TCP 协议详解 ｜ 第 13 章 UDP、QUIC 与套接字 ｜ 第 14 章 DNS 与 DHCP ｜ **难度**：★★★ ｜ **建议投入**：70 分钟

## 一、学习目标

1. 能按「起始行 + 头部 + 空行 + 正文」四段解析任意 HTTP/1.1 报文，并正确解码 `chunked` 分块正文。
2. 能说出 GET/POST/PUT/DELETE/HEAD/OPTIONS/PATCH 的语义与幂等性差异，并解释为什么 POST 默认不幂等。
3. 能记住状态码五大类与 12 个高频码（200/301/302/304/400/401/403/404/405/429/500/502/503/504）的准确含义。
4. 能说明 HTTP/1.1 队头阻塞、HTTP/2 二进制分帧与 HPACK 头压缩、HTTP/3 基于 QUIC 的演进关系。
5. 能按 TLS 1.3 的密钥计划说出 HKDF-Extract / Expand 的输入输出，并解释前向安全与「为什么砍掉 RSA 密钥交换」。
6. 能根据响应头判断强缓存是否命中、是否需要协商缓存，并会算启发式过期 `(Date − Last-Modified) × 10%`。

## 二、核心概念总览

```
   HTTP 版本演进（同一语义，不同传输方式）
   0.9 ── 1.0 ────── 1.1 ─────────── 2 ──────────── 3
   无头部  默认关闭    持久连接+Host     二进制分帧        基于 QUIC(UDP)
   只 GET  Connection  管线化(少用)     多路复用+HPACK    流级无队头阻塞
          : close     chunked         服务端推送         连接迁移 + 0-RTT

   一次 HTTPS 请求的时间线（RTT = 30ms）
   ┌─ DNS 解析 ─┬─ TCP 握手 ─┬─ TLS 1.3 握手 ─┬─ 发请求 ─┬─ 收响应 ─┐
   │  0~n RTT   │   1 RTT    │     1 RTT      │  1 RTT   │  1 RTT   │
   └────────────┴────────────┴────────────────┴──────────┴──────────┘
        HTTP/3(QUIC) 把 TCP 握手与 TLS 握手合并为 1 RTT，恢复会话可 0 RTT

   缓存决策树
   响应到达 → 有 Cache-Control: no-store? ─是→ 不缓存
             否
             no-cache? ─是→ 每次必须协商校验
             否
             max-age 未过期? ─是→ 强缓存命中（0 请求）
             否 → Expires 未过期? ─是→ 强缓存命中
                  否 → 无显式头? → 启发式 (Date-Last-Modified)×10%
                       → 协商缓存：If-None-Match / If-Modified-Since → 304 或 200
```

三块内容环环相扣：**协议格式**决定报文长什么样（起始行、头部、chunked 正文）；**传输方式**决定了性能上限（HTTP/1.1 队头阻塞 → HTTP/2 多路复用 → HTTP/3 流级独立）；**缓存与安全**决定用户实际感知的速度与可信度（强缓存 0 请求、TLS 1.3 前向安全）。理解这条主线，就能把「网页为什么慢」「证书为什么过期」这类问题定位到具体层。

## 三、机制详解

### 3.1 HTTP 版本演进：每一代解决了上一代的什么痛

| 版本 | 时间 | 传输方式 | 解决了什么 | 遗留问题 |
|------|------|----------|------------|----------|
| 0.9 | 1991 | 纯文本、单请求 | 最简 GET | 无头部、无状态码 |
| 1.0 | 1996 | 每请求一条 TCP | 引入头部与状态码 | 默认短连接，握手开销大 |
| 1.1 | 1997 | 默认 keep-alive | 持久连接、Host、chunked、管线化 | 应用层队头阻塞，管线化几乎无人用 |
| 2 | 2015 | 二进制分帧 | 多路复用、HPACK 头压缩、服务端推送 | 仍跑在 TCP 上，传输层队头阻塞 |
| 3 | 2022 | 基于 QUIC（UDP） | 流级独立、无传输层队头阻塞、连接迁移、0-RTT | UDP 可能被中间设备限速 |

- **HTTP/1.1 的队头阻塞**：同一连接上请求必须串行处理，前一个响应没回来，后面的请求无法上送（管线化理论可发但响应必须按序返回，遇慢响应仍阻塞，且中间代理支持差，实际被弃用）。
- **HTTP/2 的解法**：把报文切成帧（Frame），每个帧带 **Stream ID**，不同流的帧可以交错发送，接收端按 Stream ID 重装。头部用 **HPACK** 压缩（静态表 61 项 + 动态表 + Huffman 编码），首部从几百字节压到几十字节。
- **HTTP/2 的遗留**：所有流共享一条 TCP 连接，一个 TCP 段丢失会阻塞**所有**流（传输层队头阻塞）。
- **HTTP/3 的解法**：把多路复用下沉到 QUIC，每条流独立编号与重传，A 流丢包不影响 B/C 流。

### 3.2 HTTP/1.1 报文格式与方法幂等性

```
请求报文                              响应报文
┌──────────────────────────────┐    ┌──────────────────────────────┐
│ GET /index.html?q=1 HTTP/1.1 │    │ HTTP/1.1 200 OK              │  起始行
│ Host: www.example.com        │    │ Date: Mon, 06 Oct 2026 ...   │
│ User-Agent: netlab/1.0       │    │ Content-Type: text/html      │  头部
│ Accept-Encoding: gzip, br    │    │ Transfer-Encoding: chunked   │
│ Connection: keep-alive       │    │ Cache-Control: max-age=300   │
│                              │ ←空行│                              │ ←空行(CRLF)
│ （无正文）                    │    │ 18\r\n<html>...</html>\r\n0\r\n\r\n │ 正文
└──────────────────────────────┘    └──────────────────────────────┘
```

- 起始行与头部、头部与正文之间都用 **CRLF**（`\r\n`）分隔；头部与正文之间是**空行**。
- **Content-Length 与 Transfer-Encoding: chunked 互斥**，不能同时出现；chunked 每块格式是「十六进制长度 + CRLF + 数据 + CRLF」，以长度 `0` 的块结束。
- **Host 头是 HTTP/1.1 必填**，虚拟主机靠它区分同一 IP 上的多个站点。

**方法幂等性**：

| 方法 | 幂等 | 语义 | 说明 |
|------|------|------|------|
| GET | 是 | 获取资源 | 可安全重试 |
| HEAD | 是 | 只取头部 | 用于探测资源是否存在 |
| PUT | 是 | 整体替换 | 重复执行结果相同 |
| DELETE | 是 | 删除资源 | 删除已删除的仍是同一结果 |
| OPTIONS | 是 | 查询支持的方法 | CORS 预检用它 |
| POST | 否 | 创建/提交 | 重复提交会产生多份 |
| PATCH | 否 | 局部更新 | 结果依赖实现，通常不幂等 |

### 3.3 状态码五大类与高频码

状态码三位数，首位代表类别：`1xx` 信息、`2xx` 成功、`3xx` 重定向、`4xx` 客户端错误、`5xx` 服务端错误。

| 状态码 | 原因短语 | 含义 | 工程要点 |
|--------|----------|------|----------|
| 200 | OK | 成功 | 正常返回正文 |
| 301 | Moved Permanently | 永久重定向 | 搜索引擎会更新索引，慎用 |
| 302 | Found | 临时重定向 | 保持原 URL 不变 |
| 304 | Not Modified | 协商缓存命中 | 无正文，省带宽 |
| 400 | Bad Request | 请求语法错误 | 参数/格式问题 |
| 401 | Unauthorized | 未认证 | 需带 `WWW-Authenticate` |
| 403 | Forbidden | 已认证但无权限 | 授权问题，非认证问题 |
| 404 | Not Found | 资源不存在 | 也可能是路由未配置 |
| 405 | Method Not Allowed | 方法不允许 | 应带 `Allow` 头 |
| 429 | Too Many Requests | 触发限流 | 应带 `Retry-After` |
| 500 | Internal Server Error | 服务端内部错误 | 后端代码异常 |
| 502 | Bad Gateway | 网关收到无效响应 | 后端进程崩溃/重启 |
| 503 | Service Unavailable | 服务不可用 | 过载或维护 |
| 504 | Gateway Timeout | 网关等待超时 | 后端处理慢 |

> 现实对照：`502` 通常是 Nginx 连上了后端但后端返回异常（如后端进程刚崩），`504` 是 Nginx 等后端超时（后端还活着但太慢）——这两个码的区分直接决定你去查后端日志还是查后端性能。

### 3.4 关键头部全解

| 头部 | 方向 | 作用 | 常见取值 |
|------|------|------|----------|
| Host | 请求 | 指定虚拟主机 | `www.example.com` |
| Connection | 双向 | 连接管理 | `keep-alive` / `close` |
| Content-Length | 双向 | 正文字节数 | `1234` |
| Transfer-Encoding | 响应 | 分块传输 | `chunked` |
| Accept | 请求 | 可接受的媒体类型 | `text/html,application/json` |
| Accept-Encoding | 请求 | 可接受的压缩 | `gzip, br` |
| Content-Type | 双向 | 正文媒体类型 | `text/html; charset=utf-8` |
| Cache-Control | 双向 | 缓存指令 | `max-age=300`、`no-cache` |
| ETag | 响应 | 资源版本标识 | `"v1-abc"` |
| Last-Modified | 响应 | 资源最后修改时间 | GMT 时间 |
| Cookie / Set-Cookie | 请求/响应 | 会话状态 | `sid=abc123` |
| Access-Control-Allow-Origin | 响应 | CORS 放通来源 | `*` 或具体域名 |
| Location | 响应 | 重定向目标 | 配合 3xx |

**CORS 相关**：跨域请求时浏览器发 `Origin`，服务端回 `Access-Control-Allow-Origin`；非简单请求（如带自定义头或 PUT）会先发 `OPTIONS` **预检**，服务端需回 `Access-Control-Allow-Methods` 与 `Access-Control-Allow-Headers`。

### 3.5 HTTP/2 与 HTTP/3 的机制

**HTTP/2 二进制分帧**：报文被拆成 HEADERS 帧、DATA 帧等，每帧含：

```
+-----------------------------------------------+
|                 Length (24 位)                 |  帧负载长度
+---------------+---------------+---------------+
|   Type (8)    |   Flags (8)   |
+-+-------------+---------------+-------------------------------+
|R|                 Stream Identifier (31 位)                    |
+=+=============================================================+
|                   Frame Payload (帧负载)                        |
+---------------------------------------------------------------+
```

- **多路复用**：不同 Stream ID 的帧交错发送，一个连接并发跑上百请求。
- **HPACK**：静态表（61 个高频头）+ 动态表（连接内增量编码）+ Huffman 编码，`Host` 这类头部首次传后只发索引。
- **服务端推送**：服务器可主动推 `Server-Push` 资源（因缓存命中率与复杂度问题，实际普及度低）。
- **流控**：HTTP/2 有连接级与流级窗口，类似 TCP 滑动窗口。

**HTTP/3 基于 QUIC**：传输层换成 QUIC，每条流独立重传，消除了 TCP 层队头阻塞；连接用 Connection ID 标识，支持连接迁移；握手合并 TCP 与 TLS，首次 1-RTT、恢复 0-RTT。

### 3.6 HTTPS 与 TLS 1.3 握手

**TLS 1.3 完整握手（1-RTT）**：

```
ClientHello + key_share + supported_versions   ->
                                               <- ServerHello + key_share
                                               <- {EncryptedExtensions}
                                               <- {Certificate}
                                               <- {CertificateVerify}
                                               <- {Finished}
{Finished}                                     ->
【应用数据】
```

与 TLS 1.2 的对比：TLS 1.2 完整握手需要 **2 RTT**（第 1 个 RTT 协商与交换密钥，第 2 个 RTT 才切换加密并完成）；TLS 1.3 把密钥交换移进第一个 RTT，且服务器在发完 ServerHello 后即可派生密钥，因此只需 **1 RTT**。

**HKDF 密钥派生**：TLS 1.3 用标准 HKDF（HMAC-based Key Derivation Function），分两步：

1. **HKDF-Extract**：`PRK = HMAC-Hash(salt, IKM)`，把任意长度输入压成固定长度伪随机密钥（SHA-256 输出 32 字节）。
2. **HKDF-Expand**：`T(1)=HMAC(PRK, info||0x01)`，`T(n)=HMAC(PRK, T(n-1)||info||n)`，拼接到所需长度 OKM。

TLS 1.3 密钥计划三级派生：

```
Early Secret     = HKDF-Extract(0, PSK)             （会话恢复时有意义）
Handshake Secret = HKDF-Extract(derived, ECDHE共享)  （ECDHE 参与，前向安全来源）
Master Secret    = HKDF-Extract(derived, 0)
```

**为什么砍掉 RSA 密钥交换**：TLS 1.2 的 RSA 密钥交换中，客户端用服务器证书的 RSA 公钥加密预主密钥，服务器用私钥解密。一旦服务器私钥泄露，攻击者可解密**所有历史会话**——没有前向安全。TLS 1.3 只保留 (EC)DHE，每次会话临时生成密钥对、用完即丢，长期私钥只用于**签名**（CertificateVerify），因此即使私钥泄露也解不出历史流量。

**证书链与 SNI**：服务器返回的 `Certificate` 是**证书链**（叶子证书 → 中间 CA → 根 CA），客户端逐级验证到受信任的根。**SNI（Server Name Indication）** 让客户端在 ClientHello 里带上目标域名，服务器据此选择对应证书，从而在同一 IP 上部署多个 HTTPS 站点；TLS 1.3 可用 ECH 加密 SNI。

### 3.7 缓存机制

**强缓存（不发请求）**：

- `Cache-Control: max-age=N`：N 秒内直接用本地副本。优先级高于 Expires。
- `Expires: <GMT 时间>`：HTTP/1.0 的绝对时间，受客户端时钟影响，已被 max-age 取代。

**协商缓存（发请求但可能省正文）**：

- `ETag` ↔ `If-None-Match`：服务器比对 ETag，命中返回 `304 Not Modified`（无正文）。
- `Last-Modified` ↔ `If-Modified-Since`：服务器比对修改时间，未变化返回 304。

**启发式过期**：当响应既无 `Cache-Control` 也无 `Expires` 时，客户端可按 `(Date − Last-Modified) × 10%` 估算新鲜期，上限通常 24 小时。

**no-cache 与 no-store 的区别**：`no-cache` 是「可以缓存，但每次使用前必须协商校验」；`no-store` 是「完全不缓存，任何位置都不存」。前者针对频繁变更的 HTML，后者针对含隐私的响应。

### 3.8 CDN、反向代理与负载均衡

- **反向代理（Reverse Proxy）**：位于服务器前，代客户端转发请求，可做 TLS 卸载、压缩、缓存、限流。Nginx、HAProxy 是典型。
- **CDN（Content Delivery Network）**：把静态资源缓存到靠近用户的边缘节点，用户从边缘取，降低回源延迟与源站压力。缓存键通常含 URL + 部分头部（如 `Accept-Encoding`）。
- **负载均衡算法**：轮询（Round Robin）、加权轮询、最少连接（Least Connections）、一致性哈希（Consistent Hashing，保证同一用户落到同一后端，利于缓存命中）、IP 哈希。

## 四、动手验证

### 4.1 `http_message.py` —— 报文解析与构造

演示内容：解析原始 HTTP 请求与响应（含 chunked 分块体），打印起始行/头部/正文；再反向构造带 `Host` 与 `Connection: keep-alive` 的请求并校验。

运行命令：

```bash
python3 http_message.py
```

关键输出片段：

```
[3] 逐块解码 chunked 正文
    块 1: 长度 = 0x18 = 24 字节，内容 = b'<html><body>hello</body>'
    块 2: 长度 = 0x0E = 14 字节，内容 = b'</html>--end--'
    结束块 = 0（长度行 0x0，之后是空行）
    拼接后正文 = b'<html><body>hello</body></html>--end--'
```

看出的结论：报文边界靠 CRLF 与空行划分；chunked 每块的十六进制长度是**数据字节数**（不含自身长度行与 CRLF），解码后正文长度可以精确还原。

### 4.2 `http_cache.py` —— 缓存判定

演示内容：给定六组响应头，逐条件打印强缓存/协商缓存判定过程，含 no-cache、no-store 与启发式过期。

运行命令：

```bash
python3 http_cache.py
```

关键输出片段：

```
场景：仅有 Last-Modified，无 Cache-Control / Expires
    -> 无 Cache-Control 且无 Expires，使用启发式过期公式：
       新鲜期 = (Date - Last-Modified) × 10%
              = (...) × 0.10 = ... 秒（上限 86400 秒）
```

看出的结论：强缓存命中 0 请求，协商缓存命中返回 304 省正文但不省 RTT；`no-cache` 与 `no-store` 语义完全不同。

### 4.3 `tls13_handshake.py` —— 握手与 HKDF

演示内容：对比 TLS 1.2/1.3 握手序列，逐步计算 HKDF-Extract / Expand 与密钥计划三级派生。

运行命令：

```bash
python3 tls13_handshake.py
```

关键输出片段：

```
[4] HKDF-Extract 演示（PRK = HMAC-SHA256(salt, IKM)）
    PRK  (伪随机密钥)                = 32 字节十六进制
[6] TLS 1.3 密钥计划（Key Schedule）三步派生
    ② Handshake Secret = HKDF-Extract(derived, ECDHE)  = ...
```

看出的结论：HKDF 的输出完全由输入决定（可复现）；ECDHE 共享密钥参与 Handshake Secret 派生，是前向安全的来源。

### 4.4 `local_http_server.py` —— keep-alive 复用验证

演示内容：在 `127.0.0.1` 起零依赖 HTTP 服务（`port=0`），用同一连接发两个请求验证 keep-alive，再对照每次新建连接。

运行命令：

```bash
python3 local_http_server.py
```

关键输出片段：

```
[2] 服务端记录的客户端连接（源端口）
    客户端 127.0.0.1:56938  请求路径 /first
    客户端 127.0.0.1:56938  请求路径 /second
    >>> 连接复用判定：是（源端口相同，TCP 未重建）
```

看出的结论：同一连接的两次请求源端口相同，证明 TCP 连接被复用；对照实验中 `Connection: close` 使源端口变化，说明每次都在重建连接。

## 五、关键字段 / 报文格式解剖

**HTTP/1.1 请求行与状态行**

| 部分 | 格式 | 示例 |
|------|------|------|
| 请求行 | `Method SP Request-Target SP HTTP-Version CRLF` | `GET /index.html HTTP/1.1` |
| 状态行 | `HTTP-Version SP Status-Code SP Reason-Phrase CRLF` | `HTTP/1.1 200 OK` |
| 头部行 | `Field-Name ":" OWS Field-Value CRLF` | `Content-Type: text/html` |
| 空行 | `CRLF` | 头部与正文分隔 |

**chunked 编码结构**

| 部分 | 内容 | 示例 |
|------|------|------|
| 块长度 | 十六进制 + CRLF | `18\r\n` |
| 块数据 | 任意字节 + CRLF | `<html><body>hello</body>\r\n` |
| 结束块 | `0` + CRLF + 可选的 trailer + CRLF | `0\r\n\r\n` |

**HTTP/2 帧头（9 字节）**

| 字段 | 长度 | 作用 | 常见取值 |
|------|------|------|----------|
| Length | 24 位 | 帧负载长度 | ≤ 16384 默认 |
| Type | 8 位 | 帧类型 | 0=DATA 1=HEADERS 4=SETTINGS |
| Flags | 8 位 | 帧标志 | END_STREAM、END_HEADERS |
| R + Stream ID | 1 + 31 位 | 流标识 | 客户端用奇数流 ID |

**TLS 1.3 密钥计划**

| 阶段 | 公式 | 作用 |
|------|------|------|
| Early Secret | `HKDF-Extract(0, PSK)` | 0-RTT / 会话恢复 |
| Handshake Secret | `HKDF-Extract(derive(Early), ECDHE)` | 派生握手流量密钥 |
| Master Secret | `HKDF-Extract(derive(Handshake), 0)` | 派生应用流量密钥 |

## 六、易混概念对比

| 概念 A | 概念 B | 核心区别 | 典型场景 |
|--------|--------|----------|----------|
| 强缓存 | 协商缓存 | 强缓存 0 请求；协商缓存发请求但可能 304 | max-age vs ETag |
| no-cache | no-store | no-cache 可存但必校验；no-store 完全不存 | HTML 用 no-cache，隐私响应用 no-store |
| 301 | 302 | 301 永久（会改索引）；302 临时（保留 URL） | 域名迁移用 301，登录跳转用 302 |
| 502 | 504 | 502 网关收到无效响应；504 网关等待超时 | 后端崩溃 vs 后端太慢 |
| ETag | Last-Modified | ETag 精确到内容版本；Last-Modified 精度到秒 | 强校验用 ETag |
| HTTP/2 队头阻塞 | HTTP/3 队头阻塞 | HTTP/2 仍有传输层队头阻塞；HTTP/3 流级独立 | 高丢包链路 HTTP/3 更优 |
| TLS 1.2 | TLS 1.3 | 1.2 完整握手 2 RTT 且可用无前向安全的 RSA；1.3 只需 1 RTT 且强制前向安全 | 新站点一律上 1.3 |
| 反向代理 | 正向代理 | 反向代理代表服务器；正向代理代表客户端 | Nginx 是反向，浏览器 VPN 是正向 |

## 七、工程实践与最佳实践

1. **静态资源用「长 max-age + 内容哈希文件名」**——因为文件名变了即 URL 变了，缓存永远安全，可在不改名时把 max-age 设成一年（`immutable`），改内容靠改文件名破缓存。
2. **HTML 走 `no-cache` 或短 max-age**——因为 HTML 入口引用的资源 URL 常变，若不校验会长时间指向旧资源。
3. **协商缓存优先用 ETag 而不是 Last-Modified**——因为 Last-Modified 精度只到秒，且文件「碰一下」时间就变；ETag 能精确反映内容是否真的变了。
4. **不要同时用 ETag 与 Last-Modified 做弱校验混用**——两者不一致时按优先级判断易出错，选一种为主、另一种为辅。
5. **HTTPS 务必上 TLS 1.3**——因为少一个 RTT、强制前向安全、且握手消息大部分加密，抗降级能力更强。
6. **证书链要下发完整**——只发叶子证书会导致部分客户端（尤其安卓）验链失败，表现为「电脑能开手机不能开」。
7. **Nginx 的 `proxy_read_timeout` 要与后端处理时间匹配**——设置过小会把后端正常的长处理误判为 504；过大则故障时连接堆积。
8. **502 与 504 分开监控**——502 多半是后端进程异常，504 多半是后端性能问题，二者处置路径完全不同。
9. **开启 HTTP/2 需要 TLS + ALPN**——明文 HTTP/2（h2c）支持差，实际都用 HTTPS 协商 `h2`/`h3`。
10. **CDN 缓存键要显式配置**——默认可能把 `Cookie`、`Authorization` 纳入缓存键导致命中率暴跌，也可能因忽略 `Vary` 而缓存串味。
11. **CORS 不要图省事回 `Access-Control-Allow-Origin: *` 又带凭证**——带 `credentials` 时通配符会被浏览器拒绝，必须回具体来源。
12. **`Connection: keep-alive` 要配合理的超时与最大请求数**——防止空闲连接长期占用后端连接池，也防止单连接请求过多导致负载不均。

## 八、常见陷阱清单

| # | 现象 | 根因 | 排查 / 规避 |
|---|------|------|-------------|
| 1 | 页面样式更新后浏览器仍用旧样式 | 强缓存 max-age 过长且文件名未变 | 用内容哈希文件名或降 max-age |
| 2 | 接口返回 304 但前端拿不到数据 | 把 304 当正常响应解析正文 | 304 无正文，应复用本地缓存 |
| 3 | 同时出现 Content-Length 与 chunked | 服务端/代理重复添加 | 二者互斥，保留其一 |
| 4 | chunked 解析乱码 | 长度行当十进制解析 | 长度行是**十六进制** |
| 5 | 请求体被截断 | 未读 Content-Length 指定的全部字节 | 按 Content-Length 精确读满 |
| 6 | 跨域报 CORS 错误但服务端加了头 | 预检 OPTIONS 未回允许头 | OPTIONS 也需返回 ACAO/ACAM/ACAH |
| 7 | 带凭证的跨域请求被拒 | 服务端回了 `Access-Control-Allow-Origin: *` | 带 credentials 必须回具体来源 |
| 8 | 频繁 502 | 后端进程崩溃或健康检查失败 | 查后端日志与进程状态、调健康检查 |
| 9 | 频繁 504 | 后端处理慢或代理超时过短 | 查后端耗时，调 `proxy_read_timeout` |
| 10 | 手机打不开网站电脑正常 | 服务器未下发完整证书链 | 配置 `ssl_certificate` 包含中间 CA |
| 11 | HTTP/2 协商失败退回 1.1 | ALPN 未配置或客户端不支持 | 确认 Nginx 有 `http2` 且 TLS ≥1.2 |
| 12 | 上 HTTP/3 无收益 | UDP 443 被中间设备阻断 | 放通 UDP，确认 `Alt-Svc` 生效 |
| 13 | 缓存命中率异常低 | 缓存键纳入 Cookie/Authorization | 显式配置缓存键，剥离无关头 |
| 14 | POST 重试导致重复下单 | 误以为 POST 幂等 | 用幂等键（Idempotency-Key）去重 |
| 15 | CDN 上缓存了带 Set-Cookie 的响应 | 未对动态响应设 no-store/private | 动态响应加 `Cache-Control: private, no-store` |

## 九、自测练习

1. **（计算题）** 一段响应使用 chunked 编码，块长度为 `2a`、`1f`、`0`。求正文总字节数（不含长度行与 CRLF），并说明结束块格式。
2. **（计算题）** 某响应头 `Date: Mon, 06 Oct 2026 08:00:00 GMT`，`Last-Modified: Mon, 29 Sep 2026 08:00:00 GMT`，无 Cache-Control 与 Expires。求启发式新鲜期（秒），并判断「缓存 1 小时后访问」是否强缓存命中。
3. **（计算题）** 客户端发起一次完整 HTTPS 请求，RTT=30ms。使用 (a) HTTP/1.1 + TLS 1.3、(b) HTTP/3 首次连接，分别求从 TCP/QUIC 握手开始到收到响应的最少总时延（DNS 已缓存，忽略服务端处理）。
4. **（计算题）** 某站点有 50 个静态资源，若每资源单独建 TCP+TLS1.3 连接（2 RTT 建连）并串行请求，与复用一条 keep-alive 连接相比，节省多少 RTT？RTT=30ms 时节省多少毫秒？
5. **（排障题）** 用户反馈网站间歇性 502，刷新后恢复。请给出至少 3 个排查方向。
6. **（排障题）** 前端发跨域请求，浏览器报 CORS 错误，但 `curl` 直接请求接口正常返回。分析原因。
7. 说明 HTTP/1.1 队头阻塞、HTTP/2 传输层队头阻塞、HTTP/3 流级多路复用三者的层次差异。
8. 解释 HKDF 的 Extract 与 Expand 两步分工，以及为什么 TLS 1.3 需要把两步分开。
9. 为什么说 `no-cache` 不是「不缓存」？它与 `no-store` 在实现上分别对缓存做了什么？
10. **（计算题）** TLS 1.3 用 SHA-256，HKDF-Extract 的 PRK 长度是多少字节？若 HKDF-Expand 需要 64 字节输出，需要迭代几次？
11. 说明 SNI 的作用，以及为什么同一 IP 上能部署多个 HTTPS 站点。
12. `http://` 与 `https://` 在「是否加密」「默认端口」「证书校验」「SNI 是否明文」四个维度上有何差异？

<details>
<summary>参考答案</summary>

1. `0x2a` = 42，`0x1f` = 31，结束块 `0`。正文总字节数 = 42 + 31 = **73 字节**。结束块格式：`0\r\n\r\n`（长度行 `0` + CRLF + 可选 trailer + 最后的 CRLF）。
2. `Date` 与 `Last-Modified` 相差 7 天 = 7 × 86400 = 604800 秒。启发式 = 604800 × 0.10 = **60480 秒**（小于上限 86400，无需截断）。缓存 1 小时 = 3600 秒 < 60480 秒 → **强缓存命中**。
3. (a) HTTP/1.1 + TLS 1.3：TCP 握手 1 RTT + TLS 1.3 握手 1 RTT + 请求/响应 1 RTT = 3 RTT = **90 ms**。(b) HTTP/3 首次：QUIC 握手（含 TLS）1 RTT + 请求/响应 1 RTT = 2 RTT = **60 ms**。HTTP/3 省下 1 个 RTT（30ms）。若 QUIC 用 0-RTT 恢复并直接带请求，还可再省。
4. 每资源单独建连 = 每资源 2 RTT 建连 + 1 RTT 请求 = 3 RTT，50 个串行 = 150 RTT。复用一条连接：首次 2 RTT 建连 + 50 × 1 RTT 请求 = 52 RTT。节省 150 − 52 = **98 RTT**，RTT=30ms 时节省 98 × 30 = **2940 ms**（约 2.94 秒）。实际浏览器还会并发多条连接，收益按并发度分摊。
5. 排查方向：① 后端进程是否重启/崩溃（查后端日志与 `systemd` 状态）；② 健康检查是否过于敏感导致实例被摘除又加回；③ 后端连接池/线程池是否被打满；④ 负载均衡到后端的网络抖动（查 LB 日志的 upstream 错误）；⑤ 后端某台机器内存/GC 导致瞬时无响应。
6. 原因：CORS 是**浏览器**的安全策略，`curl` 不受同源策略约束。预检请求（OPTIONS）需要服务端返回 `Access-Control-Allow-Origin`、`Access-Control-Allow-Methods`、`Access-Control-Allow-Headers`；若只在实际请求上加了头而 OPTIONS 未处理，浏览器就会拦。需检查 OPTIONS 的响应头与 `Vary: Origin`。
7. HTTP/1.1 队头阻塞在**应用层**：同一连接请求串行，前一个响应未回后一个请求不能上送。HTTP/2 队头阻塞在**传输层（TCP）**：多路复用解决了应用层，但所有流共享一条 TCP，一个 TCP 段丢失会阻塞所有流。HTTP/3 把多路复用下沉到 QUIC，每条流独立编号与重传，A 流丢包不影响 B/C 流，两层队头阻塞都消除。
8. Extract 负责**把任意长度的输入压成固定长度的 PRK**（用 HMAC），目的是把不同来源的密钥材料（PSK、ECDHE）统一成同一长度、便于后续混入；Expand 负责**把 PRK 拉长到所需长度并保持伪随机性**。TLS 1.3 需要把「多个熵源分阶段混合」与「按用途派生不同长度的密钥」解耦，因此必须分两步：Extract 逐级混合熵源（Early→Handshake→Master），Expand 用 `HKDF-Expand-Label` 为不同用途（client/server traffic、key/iv）派生出互不相同的密钥。
9. `no-cache` 的含义是「**可以缓存，但每次使用前必须与服务器协商校验**」，缓存会存储副本，只是副本不能直接用；`no-store` 是「**不允许任何形式的存储**」，缓存连副本都不保留。实现上：`no-cache` 存入缓存但每次请求都带条件头（If-None-Match/If-Modified-Since）；`no-store` 收到响应后直接丢弃，不写入缓存。
10. SHA-256 的 PRK 长度 = **32 字节**。HKDF-Expand 每次迭代产出 32 字节，需要 64 字节 → 需要 **2 次**迭代（T(1) 与 T(2) 拼接后取前 64 字节）。
11. SNI 是客户端在 TLS ClientHello 中携带的目标域名。服务器收到 ClientHello 后，根据 SNI 选择对应域名的证书返回，因此同一 IP（同一端口 443）上可以托管多个 HTTPS 站点，各自用各自的证书。若客户端不支持 SNI，服务器只能返回默认证书。
12. ① 加密：HTTP 明文，HTTPS 加密；② 默认端口：HTTP 80，HTTPS 443；③ 证书校验：HTTP 无，HTTPS 需验证证书链与域名；④ SNI：二者都可用于虚拟主机，但 HTTPS 的 SNI 在 TLS 1.3 里默认仍是明文（除非启用 ECH），HTTP 的 `Host` 头是明文。

</details>

## 十、命令与配置速查

| 用途 | Linux / macOS 主机侧 | Cisco 风格 | 华为风格 |
|------|----------------------|------------|----------|
| 查看响应头 | `curl -I https://www.example.com` | — | — |
| 看完整交互 | `curl -v https://www.example.com` | — | — |
| 强制用 HTTP/2 | `curl --http2 -I URL` | — | — |
| 强制用 HTTP/3 | `curl --http3 -I URL` | — | — |
| 查 TLS 握手 | `openssl s_client -connect www.example.com:443 -tls1_3` | — | — |
| 看证书链 | `openssl s_client -showcerts -connect host:443` | — | — |
| 抓 HTTP 包 | `tcpdump -nn -A 'tcp port 443'` | — | — |
| 本地起静态服务 | `python3 -m http.server 8000` | — | — |
| 压测 | `ab -n 1000 -c 10 https://url/` | — | — |
| 查看代理缓存 | `nginx -T \| grep -i cache` | — | — |

## 十一、本章示例索引

| 文件 | 一句话说明 | 运行 |
|------|-----------|------|
| `http_message.py` | 解析原始 HTTP 请求/响应（含 chunked 分块体），反向构造合法请求并校验 | `python3 http_message.py` |
| `http_cache.py` | 逐条件判定强缓存/协商缓存，含 no-cache/no-store 与启发式过期公式 | `python3 http_cache.py` |
| `tls13_handshake.py` | TLS 1.3/1.2 握手序列对比 + HKDF-Extract/Expand 与密钥计划演示 | `python3 tls13_handshake.py` |
| `local_http_server.py` | 127.0.0.1 起零依赖 HTTP 服务，用同一连接验证 keep-alive 复用 | `python3 local_http_server.py` |

---

⬅️ 上一章：[第 14 章 DNS与DHCP](../14-DNS与DHCP/README.md) ｜ ➡️ 下一章：[第 16 章 运维类应用协议](../16-运维类应用协议/README.md) ｜ 🏠 [返回总目录](../README.md)
