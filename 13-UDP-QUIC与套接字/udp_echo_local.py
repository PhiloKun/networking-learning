#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 127.0.0.1 上起 UDP echo 服务（端口 0 自动分配），演示超时重传。

运行: python3 udp_echo_local.py
"""
import socket
import sys
import threading
import time

sys.dont_write_bytecode = True


def echo_server(sock: socket.socket, stop: threading.Event) -> None:
    """后台线程：把收到的每个数据报原样回送 ECHO: 前缀，最多服务 8 次。"""
    sock.settimeout(0.2)
    served = 0
    while not stop.is_set() and served < 8:
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            continue
        except OSError:
            break
        sock.sendto(b"ECHO:" + data, addr)
        served += 1


def probe(times: int, timeout: float) -> tuple[int, bool]:
    """对无人监听的端口发起 times 次探测，每次超时重试。返回（尝试次数, 是否收到应答）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    s.settimeout(timeout)
    got = False
    attempt = 0
    for attempt in range(1, times + 1):
        s.sendto(b"probe", ("127.0.0.1", 9))  # 9 = discard，回环上无人监听
        try:
            s.recvfrom(2048)
            got = True
            break
        except socket.timeout:
            print("    尝试 %d：%.0f ms 内无应答 -> 超时" % (attempt, timeout * 1000))
    s.close()
    return attempt, got


def main() -> None:
    print("=" * 68)
    print("UDP echo 回环演示（127.0.0.1，端口由系统自动分配）")
    print("=" * 68)

    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server_addr = server.getsockname()
    print("服务端已绑定: %s:%d" % server_addr)

    stop = threading.Event()
    t = threading.Thread(target=echo_server, args=(server, stop), daemon=True)
    t.start()

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind(("127.0.0.1", 0))
    client.settimeout(1.0)
    print("客户端已绑定: %s:%d" % client.getsockname())

    print("\n[1] 正常收发：发送 3 个数据报，观察应答")
    for i in range(1, 4):
        msg = ("hello-%d" % i).encode()
        client.sendto(msg, server_addr)
        reply, _ = client.recvfrom(2048)
        print("    发送 %-10r -> 收到 %r" % (msg, reply))

    print("\n[2] 超时重传演练：对无人监听的端口连续探测 3 次")
    attempts, got = probe(3, 0.12)
    print("    实际尝试 %d 次，收到应答 = %s" % (attempts, got))
    print(">>> 结论：UDP 本身没有重传机制，超时后必须由应用层决定是否重发")

    print("\n[3] 数据报边界验证：一次发送 30 字节，一次接收收到完整 30 字节")
    payload = b"0123456789" * 3
    client.sendto(payload, server_addr)
    reply, _ = client.recvfrom(2048)
    print("    发送 %d 字节，收到 %d 字节（含 5 字节 ECHO: 前缀）" % (len(payload), len(reply)))
    body = reply[len(b"ECHO:"):]
    print(">>> 结论：剥掉前缀后载荷完全一致 = %s，UDP 保留报文边界不会粘包"
          % (body == payload))

    stop.set()
    client.close()
    server.close()
    print("\n服务端与客户端已关闭，端口已释放。")

    print("\n" + "=" * 68)
    print("小结")
    print("-" * 68)
    print("1. UDP 无连接、保留报文边界，sendto/recvfrom 一一对应，不会粘包。")
    print("2. 端口传 0 由系统分配临时端口，回环演示不占用固定端口、不与他人冲突。")
    print("3. UDP 没有超时重传，可靠性必须由应用层自行实现（见 reliable_udp.py）。")
    print("4. connect 后的 UDP socket 只是绑定默认对端，并不建立任何连接状态。")


if __name__ == "__main__":
    main()
