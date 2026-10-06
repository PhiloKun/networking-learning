#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印 DHCP DORA 四步报文的源/目的地址、广播标志与关键 Option，演示 T1/T2 与中继。

运行: python3 dhcp_dora.py
"""
import sys
import struct

sys.dont_write_bytecode = True

# DHCP 消息类型（Option 53）
MSG_TYPE = {1: "DISCOVER", 2: "OFFER", 3: "REQUEST", 4: "DECLINE",
            5: "ACK", 6: "NAK", 7: "RELEASE", 8: "INFORM"}

# 常用 Option 编号
OPTIONS = {
    1: "子网掩码", 3: "默认网关", 6: "DNS 服务器", 12: "主机名",
    15: "域名", 28: "广播地址", 42: "NTP 服务器", 43: "厂商特定信息",
    50: "请求的 IP 地址", 51: "IP 租期（秒）", 52: "Option 溢出",
    53: "DHCP 消息类型", 54: "服务器标识", 55: "参数请求列表",
    57: "最大报文长度", 58: "续租时间 T1", 59: "重绑定时间 T2",
    60: "厂商类别标识", 61: "客户端标识", 82: "中继代理信息",
}

LEASE = 86400          # 租期 24 小时
SERVER = "198.51.100.1"
CLIENT_ASSIGNED = "198.51.100.100"
RELAY = "203.0.113.1"


def show(step: str, src: str, dst: str, flags: str, opts: list[tuple[int, str]]) -> None:
    print("\n  [%s]" % step)
    print("    源 IP:端口   = %s" % src)
    print("    目的 IP:端口 = %s" % dst)
    print("    BOOTP 标志   = %s" % flags)
    for num, val in opts:
        print("    Option %-3d (%-12s) = %s" % (num, OPTIONS.get(num, "?"), val))


def t1_t2(lease: int) -> None:
    t1 = lease // 2
    t2 = lease * 7 // 8
    print("\n[5] 租期计时与续租")
    print("    租期 LEASE = %d 秒（Option 51 指定）" % lease)
    print("    T1（续租）  = LEASE × 50%%  = %d 秒 -> 单播 DHCPREQUEST 给原服务器" % t1)
    print("    T2（重绑定）= LEASE × 87.5%% = %d 秒 -> 广播 DHCPREQUEST 给任意服务器" % t2)
    print("    到期未续租 -> 客户端停止使用该地址（可能收到 NAK）")
    print("    >>> 公式：T1 = 0.5 × lease，T2 = 0.875 × lease（RFC 2131 默认）")


def main() -> None:
    print("=" * 72)
    print("DHCP DORA 四步交互建模（广播/单播边界与关键 Option）")
    print("=" * 72)
    print("客户端初始状态：无 IP（0.0.0.0），使用端口 68；服务器使用端口 67")

    print("\n[1] DISCOVER —— 客户端广播寻找 DHCP 服务器")
    show("DISCOVER", "0.0.0.0:68", "255.255.255.255:67",
         "BROADCAST=1（客户端还没 IP，必须广播）",
         [(53, "1 (DISCOVER)"), (55, "1,3,6,15,28,42（想要的参数）"),
          (57, "1500（客户端能收的最大报文）"), (61, "01 + 客户端 MAC")])

    print("\n[2] OFFER —— 服务器给出临时可用地址")
    show("OFFER", "%s:67" % SERVER, "255.255.255.255:68",
         "BROADCAST=1（客户端仍无 IP，无法单播）",
         [(53, "2 (OFFER)"), (1, "255.255.255.0"), (3, SERVER),
          (6, "198.51.100.53, 203.0.113.53"), (51, "%d（秒）" % LEASE),
          (54, "%s（服务器标识）" % SERVER)])

    print("\n[3] REQUEST —— 客户端广播确认选定服务器（不是选地址，是选服务器）")
    show("REQUEST", "0.0.0.0:68", "255.255.255.255:67",
         "BROADCAST=1（让所有服务器知道自己选了谁）",
         [(53, "3 (REQUEST)"), (50, "%s（请求的 IP）" % CLIENT_ASSIGNED),
          (54, "%s（选定的服务器）" % SERVER), (55, "1,3,6,15,28,42")])

    print("\n[4] ACK —— 服务器正式下发租期与配置")
    show("ACK", "%s:67" % SERVER, "255.255.255.255:68",
         "BROADCAST=1（部分实现此步可单播到已分配地址）",
         [(53, "5 (ACK)"), (1, "255.255.255.0"), (3, SERVER),
          (6, "198.51.100.53, 203.0.113.53"), (51, "%d（秒）" % LEASE),
          (54, "%s" % SERVER), (28, "198.51.100.255")])

    t1_t2(LEASE)

    print("\n[6] DHCP 中继（Relay）：跨网段获取地址")
    print("    场景：客户端在 192.0.2.0/24，DHCP 服务器在 198.51.100.0/24（三层隔离）")
    print("    ① 客户端广播 DISCOVER（广播不能跨路由器，路由器默认丢弃）")
    print("    ② 网关路由器开启 DHCP 中继（ip helper-address 198.51.100.1）")
    print("       把 giaddr 字段填为本接口地址 = %s，再单播转发给服务器" % RELAY)
    print("    ③ 服务器根据 giaddr 判断该给哪个网段（192.0.2.0/24）的地址池")
    print("    ④ 服务器把响应单播回 giaddr:67，由中继转交客户端")
    print("    ⑤ Option 82（中继代理信息）可携带电路 ID 与远端 ID，用于定位端口：")
    print("       · Circuit ID：标识客户端接入的交换机端口")
    print("       · Remote ID：标识中继设备本身")
    print("    >>> 关键：giaddr 非 0 时，服务器一定把响应发给中继，而不是广播给客户端")

    print("\n[7] 常用 DHCP Option 速查")
    detail = {
        1: "4 字节掩码，如 255.255.255.0", 3: "默认网关列表", 6: "DNS 服务器列表",
        12: "客户端主机名", 15: "域名后缀", 28: "广播地址",
        42: "NTP 服务器列表", 51: "租约时长，网络字节序 4 字节",
        53: "1=DISCOVER/2=OFFER/3=REQUEST/5=ACK", 54: "供客户端回指服务器",
        55: "客户端希望获得的 Option 列表", 57: "客户端可接收的最大 DHCP 报文",
        58: "T1 续租时间（覆盖默认 0.5×租期）", 59: "T2 重绑定时间（覆盖默认 0.875×租期）",
        61: "客户端唯一标识，常为 01+MAC", 82: "中继代理信息：Circuit ID + Remote ID",
    }
    print("    %-6s %-16s %s" % ("编号", "名称", "说明"))
    print("    " + "-" * 58)
    for num in (1, 3, 6, 12, 15, 28, 42, 51, 53, 54, 55, 57, 58, 59, 61, 82):
        print("    %-6d %-16s %s" % (num, OPTIONS[num], detail[num]))
    print("\n    字节序提醒：DHCP 报文由 BOOTP 承载，除 Option 外的大多数字段为网络字节序（大端）")
    print("    例：租期 86400 秒 = 0x00015180，在报文中写作 00 01 51 80")
    print("    86400 的十六进制验证 = " + struct.pack(">I", 86400).hex(" ").upper())

    print("\n" + "=" * 72)
    print("小结")
    print("-" * 72)
    print("1. DHCP 四步 DORA：Discover(广播) → Offer(广播) → Request(广播) → Ack(广播/单播)。")
    print("2. 客户端无 IP，前几步必须靠广播；拿到地址后 T1 续租才是单播到原服务器。")
    print("3. T1=50%、T2=87.5% 租期是续租与重绑定的两个时间点，可用 Option 58/59 覆盖。")
    print("4. 跨网段必须用中继，giaddr 填中继接口地址，Option 82 帮助定位接入端口。")


if __name__ == "__main__":
    main()
