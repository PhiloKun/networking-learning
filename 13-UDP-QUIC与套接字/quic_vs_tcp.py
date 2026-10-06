#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比 TCP+TLS1.3 与 QUIC 的握手往返次数、首字节时延与队头阻塞差异。

运行: python3 quic_vs_tcp.py
"""
import sys

sys.dont_write_bytecode = True

RTT_MS = 30.0          # 端到端单程时延（单程 30ms -> 往返 60ms？此处按一次往返 30ms 计）
# 说明：本表统一用「一次往返 RTT」为 30ms（把 RTT 直接定义为往返耗时）
ONE_WAY_MS = 20.0      # 链路上行/下行各 20ms，供队头阻塞分析用


def ms(v: float) -> str:
    return "%.0f ms" % v


def section1() -> None:
    print("=" * 72)
    print("[1] 握手往返次数对比（RTT = %.0f ms）" % RTT_MS)
    print("=" * 72)
    rows = [
        ("TCP + TLS 1.3（首次连接）", 1 + 1, "TCP 3次握手(1 RTT) + TLS1.3 握手(1 RTT)", 2),
        ("QUIC（首次连接，1-RTT）", 1, "QUIC Initial + TLS1.3 合并(1 RTT)", 1),
        ("QUIC（会话恢复，0-RTT）", 0, "0-RTT 数据随首个 Initial 一起发", 0),
        ("TCP + TLS 1.2", 1 + 2, "TCP(1 RTT) + TLS1.2(2 RTT)", 3),
    ]
    print("%-26s %-10s %-34s %s" % ("方案", "往返次数", "构成", "首字节前等待"))
    print("-" * 72)
    for name, rtt, comp, _ in rows:
        print("%-26s %-10s %-34s %s" % (name, rtt, comp, ms(rtt * RTT_MS)))

    print("\n>>> 结论：同为 TLS 1.3，QUIC 把「传输握手」与「加密握手」合并，比 TCP+TLS 少 1 个 RTT。")
    print(">>> 0-RTT 适合恢复会话，但重放攻击风险需应用层幂等性兜底。")


def section2() -> None:
    print("\n" + "=" * 72)
    print("[2] 首字节时延（Time To First Byte）推算")
    print("=" * 72)
    for name, rtts in (("TCP + TLS 1.3", 2), ("QUIC 1-RTT", 1), ("QUIC 0-RTT", 0)):
        tcp_handshake = rtts * RTT_MS
        server_proc = 5.0
        ttfb = tcp_handshake + server_proc
        print("  %-14s: 握手 %s + 服务端处理 %.0f ms = TTFB %s"
              % (name, ms(tcp_handshake), server_proc, ms(ttfb)))
    delta = 2 * RTT_MS - 1 * RTT_MS
    print("\n>>> 同一网络下，QUIC 1-RTT 比 TCP+TLS1.3 首字节提前 %s 出现。" % ms(delta))
    print(">>> 0-RTT 会话恢复更快，但只对「已访问过的站点」生效。")


def section3() -> None:
    print("\n" + "=" * 72)
    print("[3] 队头阻塞（Head-of-Line Blocking）对比")
    print("=" * 72)
    print("场景：一条连接上并发 3 个请求，其中请求 A 的某个 TCP 段丢失。")
    print()
    print("  TCP + TLS（HTTP/1.1 或 HTTP/2）：")
    print("    流A: [seg1] [seg2 X丢失] [seg3 ...]")
    print("    流B: ................（被内核 TCP 缓冲阻塞，无法交付）")
    print("    流C: ................（同上）")
    print("    >>> 一个 TCP 段丢失，同连接上所有 HTTP 流都被阻塞 = 传输层队头阻塞")
    print()
    print("  QUIC（HTTP/3）：")
    print("    流A: [seg1] [seg2 X丢失] [seg3 重传后补齐]")
    print("    流B: [seg1] [seg2] [seg3] 正常交付")
    print("    流C: [seg1] [seg2] [seg3] 正常交付")
    print("    >>> QUIC 各流独立编号与重传，A 的丢包不影响 B/C = 消除传输层队头阻塞")

    loss_recover = 1 * RTT_MS + ONE_WAY_MS   # 快速重传+重发大约 1 个 RTT 加一程
    wait_tcp = loss_recover
    wait_b = 0.0
    print("\n  量化：丢失段的恢复约需 1 个 RTT + 一程 = %.0f ms" % loss_recover)
    print("  TCP 下流 B/C 额外等待 = %s；QUIC 下流 B/C 额外等待 = %s"
          % (ms(wait_tcp), ms(wait_b)))
    print(">>> 结论：HTTP/2 解决了应用层队头阻塞，但 TCP 层的队头阻塞仍在；")
    print(">>>        HTTP/3(QUIC) 把多路复用下沉到传输层，两层队头阻塞都消除。")


def section4() -> None:
    print("\n" + "=" * 72)
    print("[4] 连接迁移（Connection Migration）")
    print("=" * 72)
    print("  TCP 连接用四元组 (源IP,源端口,目的IP,目的端口) 标识：")
    print("    手机 Wi-Fi -> 4G 时源 IP 变化 -> 四元组改变 -> 连接断开，必须重连。")
    print("  QUIC 连接用 Connection ID（CID，可达 8~20 字节）标识：")
    print("    源 IP 变化但 CID 不变 -> 服务端凭 CID 找到原连接上下文 -> 连接不中断。")
    print("\n  重连代价估算（TCP+TLS1.3）：%s 握手 + 应用层重试" % ms(2 * RTT_MS))
    print("  QUIC 迁移代价：几乎为 0（仅需一次路径校验，约 %s）" % ms(RTT_MS))
    print(">>> 结论：移动网络频繁切换 IP 时，QUIC 的连接迁移显著优于 TCP。")


def main() -> None:
    section1()
    section2()
    section3()
    section4()

    print("\n" + "=" * 72)
    print("汇总表")
    print("=" * 72)
    print("%-22s %-16s %-16s" % ("对比项", "TCP + TLS 1.3", "QUIC / HTTP3"))
    print("-" * 72)
    pairs = [
        ("底层传输", "TCP（内核协议栈）", "UDP（用户态实现）"),
        ("首次握手", "2 RTT", "1 RTT"),
        ("会话恢复", "1 RTT（PSK 恢复）", "0 RTT"),
        ("多路复用", "TCP 层仍队头阻塞", "流级独立，无 HOL"),
        ("加密", "TLS 1.3 分层叠加", "TLS 1.3 内置合并"),
        ("连接迁移", "不支持（四元组绑定）", "支持（CID 标识）"),
        ("加密范围", "仅载荷", "首部也加密（除少量字段）"),
        ("部署依赖", "无", "需 UDP 放通，部分网络限速"),
    ]
    for a, b, c in pairs:
        print("%-22s %-16s %-16s" % (a, b, c))

    print("\n" + "=" * 72)
    print("小结")
    print("-" * 72)
    print("1. QUIC 把 TCP 的可靠传输与 TLS 1.3 加密合并进一个 1-RTT 握手，比 TCP+TLS 快 1 个 RTT。")
    print("2. 多流独立重传消除了 TCP 层的队头阻塞，这是 HTTP/3 相比 HTTP/2 的关键收益。")
    print("3. Connection ID 让连接摆脱四元组绑定，Wi-Fi/蜂窝切换时可无感迁移。")
    print("4. 0-RTT 有重放风险，且 QUIC 依赖 UDP 放通，中间设备限速 UDP 时会退化。")


if __name__ == "__main__":
    main()
