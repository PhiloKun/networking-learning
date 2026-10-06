#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四类常见攻击的过程建模与检测特征（纯模拟，不发起任何真实流量）。

运行: python3 attack_model.py [arp|mitm|syn|scan|all]
"""
import sys

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78
BANNER = "[教学模拟 · 未发起真实流量]"

ATTACKS = {
    "arp": {
        "title": "ARP 欺骗（ARP Spoofing）",
        "goal": "让 PC1 把攻击者 MAC 误当成网关 MAC，把 PC2 的流量引到攻击者机器。",
        "steps": [
            "攻击者监听局域网，学习到网关 R1 的 IP 192.0.2.1 与真实 MAC 02:00:00:00:00:01。",
            "攻击者向 PC1 持续发送伪造的 ARP 应答：「192.0.2.1 的 MAC 是我的 02:00:00:00:00:0A」。",
            "这条应答是 A 类「免费 ARP 样式」的单播/广播报文，PC1 无请求也接受，直接覆写 ARP 缓存。",
            "同时攻击者向网关发「192.0.2.10（PC1）的 MAC 是我的」，形成双向劫持。",
            "此后 PC1 发往外网的所有帧目的 MAC 变成攻击者，攻击者转发时即可旁观或篡改。",
        ],
        "sniff": [
            "同一 MAC 在短时间内映射到多个 IP（典型：网关 IP 与多台主机 IP 都指向 02:00:00:00:00:0A）。",
            "ARP 应答报文数量远超 ARP 请求（正常网络里应答应与请求大致成对）。",
            "抓包里出现「未经请求的 ARP reply」，Wireshark 过滤 arp.opcode == 2 可见大量重复。",
        ],
        "defense": [
            "交换机开启 DAI（Dynamic ARP Inspection，动态 ARP 检测），用 DHCP Snooping 绑定表校验 ARP 合法性。",
            "接入口配置 IP Source Guard + 端口安全（Port Security），限制每个端口可学习的 MAC 数量。",
            "主机侧留静态 ARP 表项或用 802.1X 准入，减少伪造报文生效面。",
        ],
        "impact": "局域网内可被完整中间人，明文协议全部失守；表现为「上网时好时坏」或证书告警。",
    },
    "mitm": {
        "title": "中间人攻击（Man-in-the-Middle）",
        "goal": "在 PC1 与服务器之间做透明转发，同时窃听/篡改双向流量。",
        "steps": [
            "前置条件：先通过 ARP 欺骗（或伪造网关/DNS）把双向流量引到攻击者机器。",
            "攻击者打开内核 IP 转发，保证 PC1 的连通性不中断，避免引起怀疑。",
            "在攻击者机器上对会话做旁路分析：HTTP 明文直接读取，TLS 则尝试降级或用伪造证书。",
            "若为 HTTPS，攻击者要么等待用户点「继续访问」，要么配合恶意 CA 证书签发伪造证书。",
            "篡改方向：对下载内容插入脚本、对登录表单改写提交地址，实现凭据窃取。",
        ],
        "sniff": [
            "路径异常：同一会话的 TTL 比平时少 1（多经过了一跳攻击者主机）。",
            "TLS 证书链异常：抓包中 Server Hello 证书的签发者与正常网站不一致（或自签名）。",
            "出现异常的 TCP 重传/重组，因为转发路径多了一台软件转发设备。",
        ],
        "defense": [
            "全站 HTTPS + HSTS，客户端启用证书校验（检测到伪造证书直接告警）。",
            "用 DNSSEC / DoH / DoT 防 DNS 层劫持，用静态 ARP 或 DAI 防二层劫持。",
            "重要系统部署双向 TLS（mTLS），对端也要验客户端证书。",
        ],
        "impact": "凭据、会话 Cookie、业务数据可被窃取或篡改；抓包看路径与证书最容易识破。",
    },
    "syn": {
        "title": "SYN Flood 泛洪",
        "goal": "耗尽服务器半连接队列，使正常用户无法建立 TCP 连接。",
        "steps": [
            "攻击者伪造大量随机源 IP，向目标 198.51.100.10 的开放端口（如 443）发送 TCP SYN。",
            "服务器每收到一个 SYN 就分配一块半连接队列（SYN 队列）资源，并回复 SYN-ACK。",
            "因源 IP 是伪造的，SYN-ACK 要么石沉大海，要么发给了被冒充的无辜主机。",
            "服务器在 RTO 内反复重传 SYN-ACK，队列项迟迟不释放，半连接队列被占满。",
            "新到的正常 SYN 因队列满被丢弃，真实用户表现为「连接超时、打不开网页」。",
        ],
        "sniff": [
            "某一时刻 SYN 数量骤增，SYN-ACK 后没有对应的 ACK，三次握手大量停在第二步。",
            "源 IP 分布极散且多为随机地址，源端口也杂乱无规律。",
            "Wireshark 统计 tcp.flags.syn==1 && tcp.flags.ack==0 计数曲线垂直拉升。",
        ],
        "defense": [
            "开启 SYN Cookie：不为每个 SYN 预分配资源，把状态编码进序列号，队列压力归零。",
            "部署抗 DDoS 清洗设备 / 云清洗，在源侧限速与信誉拦截。",
            "调大 backlog 并缩短 SYN-ACK 重传次数只能缓解，治本仍是 SYN Cookie + 清洗。",
        ],
        "impact": "服务整体不可用，且带宽未必被打满——瓶颈是连接表而非链路，易被误判成应用故障。",
    },
    "scan": {
        "title": "端口扫描（Port Scanning）",
        "goal": "探测目标开放了哪些端口，为后续入侵选点。",
        "steps": [
            "TCP connect 扫描：调用完整 connect()，完成三次握手；有回应=开放，RST=关闭。特点是会被目标日志记录。",
            "TCP SYN 半开扫描：只发 SYN，收到 SYN-ACK 即判开放，立即发 RST 断开；半连接不完成，隐蔽性更高。",
            "FIN 扫描：向端口发 FIN，开放端口直接忽略、关闭端口回 RST，用于绕过只拦 SYN 的简单防火墙。",
            "XMAS 扫描：置位 FIN+PSH+URG 三个标志位；NULL 扫描：一个标志位都不置。均靠关闭端口回 RST 来判定。",
            "对无状态防火墙，攻击者还常配合源端口 53/80 等「可信端口」与分片来躲避检测。",
        ],
        "sniff": [
            "同一源 IP 在短时间内对大量目的端口发送 SYN，且不完成握手（SYN 多、ACK 少）。",
            "出现异常标志位组合：TCP flags 为 0x001(NULL)、0x029(FIN+PSH+URG) 等。",
            "目标侧大量 RST 回包，源端口高度固定或严格递增。",
        ],
        "defense": [
            "关闭无用端口，只暴露必要服务；用防火墙对入站做白名单。",
            "开启 IDS/IPS 的扫描检测规则，对短时间内大量 SYN 对同一目标的源做封禁。",
            "对边界设备做速率限制，并把「非法标志位组合」直接丢弃。",
        ],
        "impact": "扫描本身不破坏服务，但会暴露攻击面；表现为防火墙日志里的密集拒绝记录。",
    },
}


def render(key: str) -> None:
    data = ATTACKS[key]
    print()
    print(SEP)
    print(f"{BANNER} {data['title']}")
    print(SEP)
    print(f"攻击目标：{data['goal']}")
    print()
    print(SUB)
    print("过程建模（编号步骤，仅为逻辑推演）")
    print(SUB)
    for i, step in enumerate(data["steps"], 1):
        print(f"  {i}. {step}")
    print()
    print(SUB)
    print("抓包上会看到什么（检测特征）")
    print(SUB)
    for feat in data["sniff"]:
        print(f"  - {feat}")
    print()
    print(SUB)
    print("怎么防（防御手段）")
    print(SUB)
    for i, d in enumerate(data["defense"], 1):
        print(f"  {i}) {d}")
    print()
    print(f">>> 业务影响：{data['impact']}")


def main() -> None:
    choice = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print(BANNER)
    print(SEP)
    print("常见网络攻击过程建模与检测特征 · 纯逻辑推演，不发送任何报文")
    print(SEP)
    print("说明：本脚本只做「文本建模」，不打开套接字、不构造真实攻击流量，")
    print("     所有 IP/MAC 均为 RFC 5737 与本地管理地址用法的教学值。")

    if choice in ATTACKS:
        render(choice)
    else:
        print("四种攻击的速览对照（下面逐个展开）：")
        print(SUB)
        print(f"{'攻击':<12}{'核心目标':<28}{'最典型抓包特征'}")
        print(SUB)
        overview = [
            ("ARP 欺骗", "劫持二层转发", "同一 MAC 映射多个 IP / 无请求的 ARP reply"),
            ("中间人", "窃听与篡改", "TTL 异常 + 证书链异常"),
            ("SYN Flood", "耗尽半连接队列", "大量 SYN 无后续 ACK"),
            ("端口扫描", "探测开放端口", "大量 SYN 不完成握手 / 异常标志位"),
        ]
        for a, b, c in overview:
            print(f"{a:<12}{b:<28}{c}")
        for key in ("arp", "mitm", "syn", "scan"):
            render(key)

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. 四类攻击的共同抓手都是「协议设计时未考虑信任边界」：ARP 无认证、TCP 三次握手无验证。")
    print("2. 检测优先看特征：二层看 MAC-IP 映射异常，三层看 TTL 与证书，四层看握手完成率与标志位。")
    print("3. 防御是分层的：接入层（DAI/端口安全）+ 网络层（防火墙/IPS）+ 应用层（TLS/HSTS）缺一不可。")
    print("4. 本脚本全程只做文本建模，未打开任何套接字、未发起任何真实流量。")
    print()


if __name__ == "__main__":
    main()
