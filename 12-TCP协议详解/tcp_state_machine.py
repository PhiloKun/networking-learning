#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TCP 三次握手 / 四次挥手的状态迁移与 seq/ack 数值推演，含同时打开与同时关闭边界。

运行: python3 tcp_state_machine.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


def section(title):
    print("=" * 100)
    print(title)
    print("-" * 100)


def show_seq(seq):
    return "-" if seq is None else str(seq)


def run(steps, c_state, s_state):
    """steps: (方向, 标志, seq, ack, 载荷, 客户端新状态, 服务端新状态)"""
    print(pad("报文", 6) + pad("方向", 12) + pad("标志", 22) + pad("seq", 8)
          + pad("ack", 8) + pad("载荷", 8) + pad("客户端", 16) + "服务端")
    for i, (direction, flag, seq, ack, data, nc, ns) in enumerate(steps, start=1):
        if nc:
            c_state = nc
        if ns:
            s_state = ns
        print(pad(str(i), 6) + pad(direction, 12) + pad(flag, 22)
              + pad(show_seq(seq), 8) + pad(show_seq(ack), 8)
              + pad(f"{data} B" if data else "-", 8)
              + pad(c_state, 16) + s_state)


def main():
    print()
    print("TCP 状态机演示 · 客户端 PC1 主动连接并主动关闭，服务端 PC2 监听 443")
    print("约定：客户端初始序号 ISN=1000，服务端初始序号 ISN=5000")
    print()

    section("一、三次握手（seq/ack 的数值依据）")
    steps = [
        ("PC1 → PC2", "SYN", 1000, None, 0, "SYN_SENT", "SYN_RCVD"),
        ("PC2 → PC1", "SYN, ACK", 5000, 1001, 0, "ESTABLISHED", "SYN_RCVD"),
        ("PC1 → PC2", "ACK", 1001, 5001, 0, "ESTABLISHED", "ESTABLISHED"),
    ]
    run(steps, "CLOSED", "LISTEN")
    print("-" * 100)
    print("数值推导：")
    print("  1) PC1 选 ISN=1000，发 SYN(seq=1000)。SYN 消耗 1 个序号，故 PC1 下一个待发序号是 1001。")
    print("  2) PC2 选 ISN=5000，回 SYN+ACK：seq=5000，ack=1001（确认收到 PC1 的 SYN，期待下一个字节）。")
    print("  3) PC1 回 ACK：seq=1001，ack=5001（确认收到 PC2 的 SYN）。双方进入 ESTABLISHED。")
    print(">>> 为什么是三次而非两次：两次无法确认「客户端的接收能力」。第三次 ACK 让服务端确认")
    print("    自己的 SYN 被收到了；若只有两次，服务端不知道客户端是否收到了自己的 ISN，")
    print("    也无法抵御历史重复的 SYN。多出来的这一次，同时把双方 ISN 的确认都补齐了。")
    print()

    section("二、数据传输（序号按字节推进）")
    steps = [
        ("PC1 → PC2", "PSH, ACK", 1001, 5001, 200, None, None),
        ("PC2 → PC1", "PSH, ACK", 5001, 1201, 500, None, None),
    ]
    run(steps, "ESTABLISHED", "ESTABLISHED")
    print("-" * 100)
    print("PC1 发 200 字节：seq 从 1001 到 1200，下一个序号 1201。")
    print("PC2 发 500 字节：seq 从 5001 到 5500，下一个序号 5501。")
    print(">>> 结论：TCP 的序号是「字节流编号」而不是「报文编号」，ack=N 表示「N-1 及之前全部收到」。")
    print()

    section("三、四次挥手（PC1 主动关闭）")
    steps = [
        ("PC1 → PC2", "FIN, ACK", 1201, 5501, 0, "FIN_WAIT_1", None),
        ("PC2 → PC1", "ACK", 5501, 1202, 0, "FIN_WAIT_2", "CLOSE_WAIT"),
        ("PC2 → PC1", "FIN, ACK", 5501, 1202, 0, "TIME_WAIT", "LAST_ACK"),
        ("PC1 → PC2", "ACK", 1202, 5502, 0, "TIME_WAIT", "CLOSED"),
        ("等待 2MSL", "—", None, None, 0, "CLOSED", "CLOSED"),
    ]
    run(steps, "ESTABLISHED", "ESTABLISHED")
    print("-" * 100)
    print("数值推导：")
    print("  1) PC1 发 FIN(seq=1201)：FIN 消耗 1 个序号，下一个待发序号 1202。")
    print("  2) PC2 先回 ACK(seq=5501, ack=1202)：先确认对方的 FIN；此时 PC2 处于 CLOSE_WAIT，")
    print("     应用层还有机会把剩余数据发完 —— 这就是「半关闭」状态。")
    print("  3) PC2 应用层处理完毕，发 FIN(seq=5501, ack=1202)，进入 LAST_ACK。")
    print("  4) PC1 回 ACK(seq=1202, ack=5502)，PC2 收到后进入 CLOSED。")
    print("  5) PC1 进入 TIME_WAIT，等待 2 × MSL 后才真正 CLOSED。")
    print(">>> 为什么是四次而非三次：TCP 是全双工的，一个方向关闭不代表另一个方向也关了。")
    print("    被动方收到 FIN 后，可能还有数据要发，所以 ACK 与 FIN 必须分成两个报文（步骤 2 与 3）。")
    print()

    section("四、边界情况 A：同时打开（双方同时发 SYN）")
    so = [
        ("PC1 → PC2", "SYN", 1000, None, 0, "SYN_SENT", None),
        ("PC2 → PC1", "SYN", 5000, None, 0, None, "SYN_SENT"),
        ("PC1 → PC2", "SYN, ACK", 1000, 5001, 0, "SYN_RCVD", "SYN_RCVD"),
        ("PC2 → PC1", "SYN, ACK", 5000, 1001, 0, "ESTABLISHED", "ESTABLISHED"),
    ]
    run(so, "CLOSED", "CLOSED")
    print("-" * 100)
    print(">>> 同时打开时，双方都经历 CLOSED→SYN_SENT→SYN_RCVD→ESTABLISHED，")
    print("    最终仍需 4 个报文，但状态路径与常规握手不同 —— 网络运维中极少见，但协议必须定义。")
    print()

    section("五、边界情况 B：同时关闭（双方同时发 FIN）")
    sc = [
        ("PC1 → PC2", "FIN, ACK", 1201, 5501, 0, "FIN_WAIT_1", None),
        ("PC2 → PC1", "FIN, ACK", 5501, 1201, 0, None, "FIN_WAIT_1"),
        ("PC1 ← PC2", "收到对端 FIN", None, None, 0, "CLOSING", None),
        ("PC2 ← PC1", "收到对端 FIN", None, None, 0, None, "CLOSING"),
        ("PC1 ← PC2", "收到自己 FIN 的 ACK", None, None, 0, "TIME_WAIT", None),
        ("PC2 ← PC1", "收到自己 FIN 的 ACK", None, None, 0, None, "TIME_WAIT"),
        ("等待 2MSL", "—", None, None, 0, "CLOSED", "CLOSED"),
    ]
    run(sc, "ESTABLISHED", "ESTABLISHED")
    print("-" * 100)
    print(">>> CLOSING 状态只在「同时关闭」时出现：已经发了 FIN 又收到对方的 FIN，")
    print("    但自己的 FIN 还没被确认，于是停在 CLOSING，等 ACK 后进 TIME_WAIT。")
    print()

    section("六、TCP 全部 11 个状态")
    states = [
        ("CLOSED", "初始/归宿态", "无连接；主动连接从这里出发，被动监听从 LISTEN 出发"),
        ("LISTEN", "被动等待", "服务端调用 listen() 后进入，等待 SYN"),
        ("SYN_SENT", "主动发起", "已发 SYN，等待对端 SYN 或 SYN+ACK"),
        ("SYN_RCVD", "被动接收", "收到 SYN 并回了 SYN+ACK，等待最终 ACK（半连接队列）"),
        ("ESTABLISHED", "数据交换", "双方序号已同步，可双向传输"),
        ("FIN_WAIT_1", "主动关闭第 1 步", "已发 FIN，等待对方的 ACK"),
        ("FIN_WAIT_2", "主动关闭第 2 步", "已收到 ACK，等待对方的 FIN（半关闭）"),
        ("CLOSE_WAIT", "被动关闭", "已收到对方的 FIN 并回了 ACK，等待本端应用调用 close()"),
        ("CLOSING", "同时关闭", "已发 FIN 又收到 FIN，等待自己 FIN 的 ACK"),
        ("LAST_ACK", "被动关闭收尾", "已发 FIN，等待最后一个 ACK"),
        ("TIME_WAIT", "主动关闭收尾", "等待 2×MSL，确保最后的 ACK 到达并让旧报文消散"),
    ]
    print(pad("状态", 16) + pad("分类", 18) + "含义")
    for s, c, d in states:
        print(pad(s, 16) + pad(c, 18) + d)
    print("-" * 100)
    print("状态迁移图（主动关闭路径）：")
    print("  CLOSED → SYN_SENT → ESTABLISHED → FIN_WAIT_1 → FIN_WAIT_2 → TIME_WAIT → CLOSED")
    print("  LISTEN → SYN_RCVD → ESTABLISHED → CLOSE_WAIT → LAST_ACK → CLOSED   （被动关闭路径）")
    print("  同时关闭：FIN_WAIT_1 → CLOSING → TIME_WAIT → CLOSED")
    print()

    section("七、TIME_WAIT 与 CLOSE_WAIT 的排障含义")
    rows = [
        ("TIME_WAIT 少量", "主动关闭方", "正常", "2MSL 内保护最后一个 ACK 可达"),
        ("TIME_WAIT 大量堆积", "主动关闭方（如反向代理）", "需关注", "并发短连接多；可开 tcp_tw_reuse 或改用长连接"),
        ("CLOSE_WAIT 少量", "被动关闭方", "正常", "应用还没调用 close()"),
        ("CLOSE_WAIT 大量堆积", "被动关闭方（如应用服务器）", "严重异常",
         "应用收到 FIN 后没关 socket → 文件描述符泄漏，最终无法建立新连接"),
        ("FIN_WAIT_2 长期存在", "主动关闭方", "异常", "对端一直不发 FIN；需设置 keepalive 或超时回收"),
    ]
    print(pad("现象", 18) + pad("出现在谁身上", 24) + pad("是否异常", 12) + "说明")
    for a, b, c, d in rows:
        print(pad(a, 18) + pad(b, 24) + pad(c, 12) + d)
    print("-" * 100)
    print("TIME_WAIT 为什么是 2MSL：")
    print("  1) 若最后一个 ACK 丢失，对端会重传 FIN，主动关闭方必须还能应答 —— 等 2MSL 覆盖")
    print("     一个完整的「报文往返 + 对端重传」窗口。")
    print("  2) 让本次连接的所有旧报文在网络中自然消亡，避免新连接（相同四元组）收到旧报文。")
    print("  MSL 常见取 2 分钟（RFC 1122），故 TIME_WAIT = 240 秒；")
    print("  Linux 固定为 60 秒（TCP_TIMEWAIT_LEN），与 MSL 取值无关。")
    print("  SO_REUSEADDR 允许在 TIME_WAIT 期间重新绑定同一端口（但不能在两台主机间复用同一四元组）。")
    print()
    print("小结：")
    print("1. 三次握手把「双方 ISN 的确认」补全，第三次 ACK 是必须的；FIN 与 SYN 各消耗 1 个序号。")
    print("2. 四次挥手源于全双工：被动方的 ACK 与 FIN 分两步发，中间就是 CLOSE_WAIT（半关闭）。")
    print("3. 大量 CLOSE_WAIT 几乎总是应用层没 close()；大量 TIME_WAIT 是主动关闭方短连接过多。")
    print()


if __name__ == "__main__":
    main()
