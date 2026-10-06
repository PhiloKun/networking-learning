#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建模 FTP 主动/被动模式的双连接建立，演示 NAT 下 PASV 返回私网地址导致的失败与修复。

运行: python3 ftp_modes.py
"""
import sys

sys.dont_write_bytecode = True

CONTROL_PORT = 21
ACTIVE_DATA_PORT = 20


def decode_pasv_reply(reply: str) -> tuple[str, int]:
    """从 227 响应中解析 (h1,h2,h3,h4,p1,p2) 得到数据连接 IP 与端口。"""
    inside = reply[reply.find("(") + 1:reply.find(")")]
    nums = [int(x) for x in inside.split(",")]
    ip = ".".join(str(n) for n in nums[:4])
    port = nums[4] * 256 + nums[5]
    return ip, port


def encode_port_arg(ip: str, port: int) -> str:
    parts = ip.split(".")
    p1, p2 = divmod(port, 256)
    return ",".join(parts + [str(p1), str(p2)])


def main() -> None:
    print("=" * 74)
    print("FTP 双连接模型：控制连接 21 + 数据连接（主动 20 / 被动随机）")
    print("=" * 74)

    print("\n[1] 主动模式（Active / PORT）：服务器主动连客户端")
    port_arg = encode_port_arg("192.0.2.50", 51000)
    p1, p2 = divmod(51000, 256)
    steps = [
        "客户端 -> 服务器:21   控制连接建立（TCP 三次握手）",
        "服务器 -> 客户端:    220 Service ready",
        "客户端 -> 服务器:    USER anonymous",
        "服务器 -> 客户端:    331 Please specify password",
        "客户端 -> 服务器:    PASS guest@",
        "服务器 -> 客户端:    230 Login successful",
        "客户端 -> 服务器:    PORT %s   （告诉服务器自己的数据端口）" % port_arg,
        "服务器 -> 客户端:    200 PORT command successful",
        "客户端 -> 服务器:    RETR file.txt",
        "服务器:20 -> 客户端:%d   服务器从 20 端口主动连回（数据连接）" % 51000,
        "（数据传完，数据连接关闭，控制连接保留继续下一条命令）",
    ]
    for s in steps:
        print("    " + s)
    print("    端口编码：PORT 参数 = ip四段 + p1,p2，端口 = p1×256 + p2")
    print("              %d = %d×256 + %d  ->  p1=%d p2=%d" % (51000, p1, p2, p1, p2))
    print("    >>> 主动模式的问题：客户端在 NAT 后时，PORT 里写的是私网 IP，服务器连不进来")

    print("\n[2] 被动模式（Passive / PASV）：客户端主动连服务器")
    reply = "227 Entering Passive Mode (203,0,113,10,195,80)"
    ip, port = decode_pasv_reply(reply)
    steps = [
        "客户端 -> 服务器:21   控制连接建立",
        "客户端 -> 服务器:    PASV",
        "服务器 -> 客户端:    %s" % reply,
        "                       （数据地址 = %s，端口 = 195×256+80 = %d）" % (ip, port),
        "客户端 -> 服务器:%d   客户端主动建立数据连接（TCP 三次握手）" % port,
        "（服务器在数据连接上发送文件内容）",
    ]
    for s in steps:
        print("    " + s)
    print("    端口解码：195×256 + 80 = %d" % (195 * 256 + 80))
    print("    >>> 被动模式对客户端 NAT 友好，因为连接方向是「客户端主动出站」")

    print("\n[3] NAT 场景下的经典故障：PASV 返回私网地址")
    print("    拓扑：外部客户端 --Internet--> 防火墙NAT --内网--> FTP服务器(192.168.1.10)")
    print("    ① 外部客户端发 PASV")
    print("    ② 服务器回：227 Entering Passive Mode (192,168,1,10,195,80)")
    print("       注意：服务器不知道自己在 NAT 后面，回的是自己的私网地址 192.168.1.10")
    print("    ③ 外部客户端尝试连接 192.168.1.10:50000  ->  私网地址不可路由  ->  失败")
    print("    现象：控制连接（21）正常、能登录、能 ls，但一到传输数据就卡住/超时")
    print("    根本原因：FTP 把数据连接地址写在应用层报文里，NAT 只改 IP 头不改应用层载荷")

    print("\n[4] 两种修复思路")
    print("    方案 A（服务器侧）：让服务器对外宣告公网地址")
    print("      vsftpd.conf:  pasv_address=203.0.113.10")
    print("                    pasv_min_port=50000")
    print("                    pasv_max_port=50100")
    print("      ProFTPD:      MasqueradeAddress 203.0.113.10")
    print("      -> 服务器在 PASV 响应里回公网地址，并在防火墙放通 50000~50100 端口段")
    print("    方案 B（防火墙侧）：启用 FTP ALG（Application Layer Gateway）")
    print("      -> 防火墙能识别 PASV/PORT 报文并动态改写其中的地址与端口，同时临时放通数据连接")
    print("      -> 缺点：ALG 对加密的 FTPS 无效（载荷被加密，改不了），且实现差异大")

    print("\n[5] 主动 vs 被动 对照表")
    print("    %-16s %-30s %s" % ("维度", "主动模式(PORT)", "被动模式(PASV)"))
    print("    " + "-" * 72)
    rows = [
        ("数据连接方向", "服务器 -> 客户端", "客户端 -> 服务器"),
        ("数据端口", "服务器固定 20", "服务器随机高端口"),
        ("客户端 NAT", "困难（需 ALG）", "友好"),
        ("服务器 NAT", "友好", "困难（需 pasv_address）"),
        ("防火墙", "需放通服务器 -> 客户端高端口", "需放通客户端 -> 服务器高端口段"),
        ("现代默认", "少用", "客户端默认（FTP 客户端常加 -p）"),
    ]
    for a, b, c in rows:
        print("    %-16s %-30s %s" % (a, b, c))

    print("\n[6] 更安全的替代：SFTP / SCP")
    print("    %-10s %-14s %-22s %s" % ("协议", "端口", "底层", "特点"))
    print("    " + "-" * 66)
    alt = [
        ("FTP", "21+数据口", "TCP 明文", "双连接、凭据与数据均明文，需 ALG"),
        ("FTPS", "990/21", "TLS 加密", "FTP 加 TLS，ALG 对加密数据失效"),
        ("SFTP", "22", "SSH 子系统", "单连接、全程加密、无 NAT 难题"),
        ("SCP", "22", "SSH", "只做文件拷贝，无交互"),
    ]
    for a, b, c, d in alt:
        print("    %-10s %-14s %-22s %s" % (a, b, c, d))
    print("    >>> 运维建议：新系统一律用 SFTP/SCP 取代 FTP，既安全又免去 NAT/ALG 的坑")

    print("\n" + "=" * 74)
    print("小结")
    print("-" * 74)
    print("1. FTP 用两条 TCP 连接：21 传命令，20（主动）或随机端口（被动）传数据。")
    print("2. 主动模式是服务器连客户端，客户端在 NAT 后会被挡；被动模式是客户端连服务器，对客户端友好。")
    print("3. 服务器在 NAT 后时 PASV 会回私网地址，需 pasv_address 或 FTP ALG 修复。")
    print("4. SFTP/SCP 基于 SSH 单连接、全程加密，彻底规避 FTP 的端口与 NAT 问题。")


if __name__ == "__main__":
    main()
