#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端口 / 服务 / 协议查询工具：内置常见端口对照表，支持按端口号或服务名检索。

运行:
    python3 port_service_lookup.py            # 打印完整对照表
    python3 port_service_lookup.py 443        # 按端口号查
    python3 port_service_lookup.py bgp        # 按服务名 / 说明关键词查
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

# (端口, 协议, 服务名, 说明, 风险标记)
# 风险标记: 高危 / 注意 / 正常 / 内网
PORTS = [
    (20, "TCP", "ftp-data", "FTP 数据连接（主动模式）", "高危"),
    (21, "TCP", "ftp", "FTP 控制连接，明文传输账号密码", "高危"),
    (22, "TCP", "ssh", "安全 Shell，远程管理首选", "注意"),
    (23, "TCP", "telnet", "远程登录，全明文，必须禁用", "高危"),
    (25, "TCP", "smtp", "邮件投递；多数云商封禁出站 25", "注意"),
    (43, "TCP", "whois", "域名注册信息查询", "正常"),
    (53, "TCP/UDP", "dns", "域名解析；TCP 用于大响应与区域传送", "注意"),
    (67, "UDP", "dhcp-server", "DHCP 服务端监听端口", "注意"),
    (68, "UDP", "dhcp-client", "DHCP 客户端监听端口", "内网"),
    (69, "UDP", "tftp", "简单文件传输，无认证，用于设备引导", "高危"),
    (79, "TCP", "finger", "用户信息查询，早已淘汰", "高危"),
    (80, "TCP", "http", "明文 HTTP", "注意"),
    (88, "TCP", "kerberos", "Kerberos 认证", "内网"),
    (110, "TCP", "pop3", "邮局协议 v3，明文收信", "高危"),
    (111, "TCP/UDP", "rpcbind", "RPC 端口映射，信息泄露面大", "高危"),
    (113, "TCP", "ident", "身份查询，几乎只被滥用于探测", "高危"),
    (119, "TCP", "nntp", "网络新闻传输", "正常"),
    (123, "UDP", "ntp", "时间同步；可被用于反射放大攻击", "注意"),
    (135, "TCP", "msrpc", "Windows RPC 端点映射", "高危"),
    (137, "UDP", "netbios-ns", "NetBIOS 名称服务", "高危"),
    (138, "UDP", "netbios-dgm", "NetBIOS 数据报服务", "高危"),
    (139, "TCP", "netbios-ssn", "NetBIOS 会话服务", "高危"),
    (143, "TCP", "imap", "IMAP 收信，明文", "高危"),
    (161, "UDP", "snmp", "SNMP 轮询；v1/v2c 的 community 明文", "高危"),
    (162, "UDP", "snmptrap", "SNMP 告警上报", "注意"),
    (179, "TCP", "bgp", "BGP 邻居建连；ACL 需只放行对端", "注意"),
    (194, "TCP", "irc", "IRC 聊天", "正常"),
    (389, "TCP", "ldap", "目录服务；明文时可被嗅探", "注意"),
    (443, "TCP", "https", "TLS 加密的 HTTP", "正常"),
    (445, "TCP", "microsoft-ds", "SMB 文件共享，跨网段必须封禁", "高危"),
    (464, "TCP/UDP", "kpasswd", "Kerberos 改密", "内网"),
    (465, "TCP", "smtps", "SMTPS 隐式 TLS", "注意"),
    (500, "UDP", "isakmp", "IPSec IKE 密钥协商", "注意"),
    (512, "TCP", "exec", "rexec，明文远程执行", "高危"),
    (513, "TCP", "login", "rlogin，明文远程登录", "高危"),
    (514, "UDP", "syslog", "系统日志，明文可伪造", "注意"),
    (515, "TCP", "printer", "LPD 打印服务", "注意"),
    (520, "UDP", "rip", "RIPv2 路由协议", "内网"),
    (546, "UDP", "dhcpv6-client", "DHCPv6 客户端", "内网"),
    (547, "UDP", "dhcpv6-server", "DHCPv6 服务端", "内网"),
    (548, "TCP", "afp", "Apple 文件共享", "注意"),
    (554, "TCP", "rtsp", "流媒体控制协议", "正常"),
    (587, "TCP", "submission", "邮件客户端提交端口，走 STARTTLS", "注意"),
    (623, "UDP", "ipmi", "服务器带外管理，默认口令风险高", "高危"),
    (631, "TCP", "ipp", "打印服务（CUPS）", "注意"),
    (636, "TCP", "ldaps", "TLS 加密的 LDAP", "正常"),
    (646, "TCP", "ldp", "MPLS 标签分发协议", "内网"),
    (873, "TCP", "rsync", "文件同步，匿名模式易被滥用", "注意"),
    (902, "TCP", "vmware", "VMware 管理接口", "高危"),
    (989, "TCP", "ftps-data", "FTPS 数据连接", "注意"),
    (990, "TCP", "ftps", "FTPS 控制连接", "注意"),
    (993, "TCP", "imaps", "TLS 加密的 IMAP", "正常"),
    (995, "TCP", "pop3s", "TLS 加密的 POP3", "正常"),
    (1080, "TCP", "socks", "SOCKS 代理，常被滥用做跳板", "高危"),
    (1099, "TCP", "rmi", "Java RMI，历史反序列化漏洞高发", "高危"),
    (1194, "UDP", "openvpn", "OpenVPN 默认端口", "注意"),
    (1433, "TCP", "ms-sql", "Microsoft SQL Server，严禁暴露公网", "高危"),
    (1434, "UDP", "ms-sql-browser", "SQL Server 浏览器服务", "高危"),
    (1521, "TCP", "oracle", "Oracle 数据库，严禁暴露公网", "高危"),
    (1701, "UDP", "l2tp", "L2TP 隧道", "注意"),
    (1723, "TCP", "pptp", "PPTP，加密已被攻破", "高危"),
    (1812, "UDP", "radius", "RADIUS 认证，802.1X 后端", "注意"),
    (1813, "UDP", "radius-acct", "RADIUS 计费", "内网"),
    (1883, "TCP", "mqtt", "物联网消息协议，明文", "注意"),
    (1900, "UDP", "ssdp", "UPnP 发现，可被用于反射放大", "高危"),
    (2049, "TCP/UDP", "nfs", "网络文件系统，需 IP 白名单", "高危"),
    (2082, "TCP", "cpanel", "cPanel 管理面板", "注意"),
    (2181, "TCP", "zookeeper", "ZooKeeper 客户端端口", "高危"),
    (2375, "TCP", "docker", "Docker 明文 API，可被直接控制主机", "高危"),
    (2376, "TCP", "docker-tls", "Docker TLS API", "注意"),
    (2379, "TCP", "etcd-client", "etcd 客户端，存着 K8s 全部状态", "高危"),
    (2380, "TCP", "etcd-peer", "etcd 节点间通信", "内网"),
    (3128, "TCP", "squid", "Squid 代理，开放代理是常见隐患", "高危"),
    (3260, "TCP", "iscsi", "iSCSI 存储，访问即等于拿到磁盘", "高危"),
    (3306, "TCP", "mysql", "MySQL，严禁暴露公网", "高危"),
    (3389, "TCP", "rdp", "远程桌面，勒索病毒主要入口", "高危"),
    (3478, "UDP", "stun", "NAT 穿透探测", "正常"),
    (3690, "TCP", "svn", "Subversion 版本库", "注意"),
    (3784, "UDP", "bfd-control", "BFD 双向转发检测", "内网"),
    (4369, "TCP", "epmd", "Erlang 端口映射守护进程", "注意"),
    (4500, "UDP", "ipsec-nat-t", "IPSec NAT 穿透封装", "注意"),
    (4789, "UDP", "vxlan", "VXLAN 隧道目的端口", "内网"),
    (4848, "TCP", "glassfish", "GlassFish 管理控制台", "注意"),
    (5000, "TCP", "upnp", "UPnP / 各类 HTTP 应用", "注意"),
    (5060, "TCP/UDP", "sip", "SIP 信令，明文", "注意"),
    (5061, "TCP", "sips", "TLS 加密的 SIP", "正常"),
    (5222, "TCP", "xmpp-client", "XMPP 客户端连接", "正常"),
    (5353, "UDP", "mdns", "组播 DNS（Bonjour / Avahi）", "注意"),
    (5432, "TCP", "postgresql", "PostgreSQL，严禁暴露公网", "高危"),
    (5555, "TCP", "adb", "Android 调试桥，暴露即被完全控制", "高危"),
    (5601, "TCP", "kibana", "Kibana 可视化面板", "注意"),
    (5666, "TCP", "nrpe", "Nagios NRPE 远程检查", "注意"),
    (5672, "TCP", "amqp", "RabbitMQ 消息队列", "注意"),
    (5900, "TCP", "vnc", "VNC 远程桌面，明文且常无认证", "高危"),
    (5984, "TCP", "couchdb", "CouchDB 数据库", "注意"),
    (6000, "TCP", "x11", "X Window，暴露可劫持图形会话", "高危"),
    (6379, "TCP", "redis", "Redis，默认无认证，暴露即被挖矿", "高危"),
    (6443, "TCP", "kube-apiserver", "Kubernetes API Server", "高危"),
    (6667, "TCP", "irc", "IRC 服务", "正常"),
    (6881, "TCP", "bittorrent", "BT 下载", "注意"),
    (7001, "TCP", "weblogic", "WebLogic 控制台，反序列化漏洞高发", "高危"),
    (7077, "TCP", "spark", "Spark 集群通信", "注意"),
    (8000, "TCP", "http-alt", "常见应用 / 开发调试端口", "注意"),
    (8009, "TCP", "ajp", "Tomcat AJP 连接器（幽灵猫漏洞）", "高危"),
    (8080, "TCP", "http-proxy", "HTTP 备用端口 / 代理", "注意"),
    (8081, "TCP", "http-alt", "HTTP 备用端口", "注意"),
    (8086, "TCP", "influxdb", "InfluxDB HTTP API", "注意"),
    (8123, "TCP", "clickhouse-http", "ClickHouse HTTP 接口", "注意"),
    (8443, "TCP", "https-alt", "HTTPS 备用端口", "正常"),
    (8649, "TCP", "ganglia", "Ganglia 监控", "注意"),
    (8883, "TCP", "mqtt-tls", "TLS 加密的 MQTT", "正常"),
    (8983, "TCP", "solr", "Solr 搜索服务", "注意"),
    (9000, "TCP", "php-fpm", "PHP-FPM / 各类应用端口", "高危"),
    (9042, "TCP", "cassandra", "Cassandra CQL 端口", "注意"),
    (9090, "TCP", "prometheus", "Prometheus 查询接口", "注意"),
    (9092, "TCP", "kafka", "Kafka Broker", "注意"),
    (9100, "TCP", "node-exporter", "主机指标导出器 / 原始打印", "注意"),
    (9200, "TCP", "elasticsearch", "Elasticsearch HTTP，默认无认证", "高危"),
    (9300, "TCP", "elasticsearch-nodes", "Elasticsearch 节点间通信", "高危"),
    (9418, "TCP", "git", "Git 原生协议，无认证", "注意"),
    (9443, "TCP", "https-alt", "HTTPS 备用端口", "正常"),
    (10000, "TCP", "webmin", "Webmin 系统管理面板", "高危"),
    (10250, "TCP", "kubelet", "Kubelet API，暴露可执行容器命令", "高危"),
    (11211, "TCP/UDP", "memcached", "内存缓存，反射放大攻击主力", "高危"),
    (15672, "TCP", "rabbitmq-mgmt", "RabbitMQ 管理界面", "注意"),
    (16379, "TCP", "redis-cluster", "Redis 集群总线", "内网"),
    (25565, "TCP", "minecraft", "Minecraft 服务器", "正常"),
    (27017, "TCP", "mongodb", "MongoDB，默认无认证，暴露即被勒索", "高危"),
    (27018, "TCP", "mongodb-shard", "MongoDB 分片", "注意"),
    (50000, "TCP", "db2", "IBM DB2 数据库", "高危"),
    (50070, "TCP", "hdfs-namenode", "Hadoop NameNode Web UI", "高危"),
    (61616, "TCP", "activemq", "ActiveMQ 消息队列", "高危"),
]

RISK_ORDER = {"高危": 0, "注意": 1, "正常": 2, "内网": 3}
COL_W = (7, 9, 22, 44, 6)


def dw(text: str) -> int:
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


def clip(text: str, width: int) -> str:
    if dw(text) <= width:
        return text
    out, used = "", 0
    for ch in text:
        step = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if used + step > width - 1:
            break
        out += ch
        used += step
    return out + "…"


def render_row(port, proto, name, desc, risk) -> str:
    return (f"  {pad(str(port), COL_W[0], 'right')}  {pad(proto, COL_W[1])}"
            f"{pad(name, COL_W[2])}{pad(clip(desc, COL_W[3]), COL_W[3])}"
            f"{pad(risk, COL_W[4], 'center')}")


def print_header() -> None:
    print(f"  {pad('端口', COL_W[0], 'right')}  {pad('协议', COL_W[1])}"
          f"{pad('服务名', COL_W[2])}{pad('说明', COL_W[3])}{pad('风险', COL_W[4], 'center')}")
    print("  " + "─" * (sum(COL_W) + 6))


def print_table(rows) -> None:
    print_header()
    for row in rows:
        print(render_row(*row))


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 96)
    print("  端口 / 服务 / 协议查询工具  ·  内置对照表")
    print("=" * 96)
    print()

    if arg is None:
        print(f"【完整对照表】共 {len(PORTS)} 条，按端口号升序排列")
        print()
        print_table(sorted(PORTS, key=lambda r: r[0]))
    elif arg.isdigit():
        port = int(arg)
        hits = [r for r in PORTS if r[0] == port]
        if hits:
            print(f"【按端口查询】端口 {port} 命中 {len(hits)} 条")
            print()
            print_table(hits)
            risk = hits[0][4]
            if risk == "高危":
                print()
                print(f">>> 警示：端口 {port}（{hits[0][2]}）属于高危服务，"
                      "若对公网开放应立即收敛，并检查是否有弱口令或未授权访问。")
        else:
            print(f"【按端口查询】端口 {port} 未在内置表中命中。")
            print()
            print("  说明：内置表只收录常见服务（IANA 注册端口 0-1023 与高频的注册端口）。")
            print(f"  若该端口确实是业务使用，建议执行 `ss -tulnp | grep {port}` 确认监听进程，")
            print("  并在资产台账里补登记——「未知端口」本身就是值得警惕的信号。")
    else:
        key = arg.lower()
        hits = [r for r in PORTS
                if key in r[2].lower() or key in r[3].lower()]
        if hits:
            print(f"【按关键词查询】「{arg}」命中 {len(hits)} 条")
            print()
            print_table(hits)
        else:
            print(f"【按关键词查询】「{arg}」未命中任何服务名或说明。")
            print()
            print("  可试的关键词：ssh / http / dns / bgp / redis / kafka / docker / mongo …")
            print("  也可直接传端口号，例如：python3 port_service_lookup.py 6379")

    high = [r for r in PORTS if r[4] == "高危"]
    warn = [r for r in PORTS if r[4] == "注意"]
    print()
    print("=" * 96)
    print("【小结】")
    print(f"  1. 内置 {len(PORTS)} 条常见端口，其中标注「高危」{len(high)} 条、"
          f"「注意」{len(warn)} 条、其余为正常或仅限内网。")
    print("  2. 高危的典型特征是「默认无认证 + 暴露即可被利用」：Redis(6379)、"
          "MongoDB(27017)、Elasticsearch(9200)、Docker API(2375) 都属此类。")
    print("  3. 排查思路：先用 `ss -tulnp` 列出本机所有监听端口，"
          "再拿本工具逐个核对用途——「这个端口是谁开的、为什么开着」必须答得上来。")
    if high:
        top = ", ".join(f"{r[0]}({r[2]})" for r in sorted(high, key=lambda r: r[0])[:6])
        print(f"  4. 首要收敛对象（按端口升序）：{top} …")


if __name__ == "__main__":
    main()
