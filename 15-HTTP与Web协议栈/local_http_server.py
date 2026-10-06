#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 127.0.0.1 起零依赖 HTTP 服务（端口 0），用同一连接发两个请求验证 keep-alive。

运行: python3 local_http_server.py
"""
import http.client
import http.server
import sys
import threading

sys.dont_write_bytecode = True

BODY1 = "hello from netlab 第一个响应".encode("utf-8")
BODY2 = "第二个响应（同一连接复用）".encode("utf-8")
RECORDS: list[tuple[str, int, str]] = []   # (客户端IP, 客户端源端口, 请求行)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"          # 关键：HTTP/1.1 才默认 keep-alive

    def log_message(self, fmt, *args):      # 关闭默认 stderr 日志，保持输出整洁
        pass

    def do_GET(self):
        RECORDS.append((self.client_address[0], self.client_address[1], self.path))
        if self.path == "/second":
            body = BODY2
        else:
            body = BODY1
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(body)


def show_request(conn: http.client.HTTPConnection, path: str) -> None:
    conn.request("GET", path, headers={"Host": "127.0.0.1", "Connection": "keep-alive"})
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    print("    请求 %-8s -> 状态 %d %s，正文 %r" % (path, resp.status, resp.reason, body))
    print("      响应头：")
    for k, v in resp.getheaders():
        print("        %-18s: %s" % (k, v))


def main() -> None:
    print("=" * 72)
    print("本机 HTTP keep-alive 连接复用验证（127.0.0.1，端口 0 自动分配）")
    print("=" * 72)

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    host, port = server.server_address
    print("服务端已启动: http://%s:%d（后台线程处理请求）" % (host, port))

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    print("\n[1] 用同一个 HTTPConnection 连续发两个请求（预期复用同一条 TCP 连接）")
    conn = http.client.HTTPConnection(host, port, timeout=3)
    show_request(conn, "/first")
    show_request(conn, "/second")
    conn.close()

    print("\n[2] 服务端记录的客户端连接（源端口）")
    ports = [p for _ip, p, _path in RECORDS]
    for ip, p, path in RECORDS:
        print("    客户端 %s:%d  请求路径 %s" % (ip, p, path))
    print("    两次请求来自的源端口：%s" % ports)
    reused = len(set(ports)) == 1 and len(ports) == 2
    print("    >>> 连接复用判定：%s" % ("是（源端口相同，TCP 未重建）" if reused else "否"))

    print("\n[3] 对照实验：每次新建连接（Connection: close）")
    RECORDS.clear()
    for path in ("/a", "/b"):
        c = http.client.HTTPConnection(host, port, timeout=3)
        c.request("GET", path, headers={"Host": "127.0.0.1", "Connection": "close"})
        r = c.getresponse()
        r.read()
        c.close()
    new_ports = [p for _ip, p, _path in RECORDS]
    print("    两次请求来自的源端口：%s" % new_ports)
    print("    >>> 源端口不同 -> 每条请求都重建了 TCP 连接（多花握手与慢启动）")

    print("\n[4] HTTP/1.1 持久连接要点")
    print("    · HTTP/1.0 默认 Connection: close；HTTP/1.1 默认 keep-alive")
    print("    · 复用连接省去 3 次握手与 TLS 握手，但 HTTP/1.1 仍有应用层队头阻塞")
    print("    · 管线化（Pipelining）理论上可并发，但响应必须按请求顺序返回，且中间设备支持差，实际很少用")
    print("    · HTTP/2 用二进制分帧 + 多路复用取代了管线化，HTTP/3 进一步在 QUIC 上消除传输层队头阻塞")

    server.shutdown()
    server.server_close()
    print("\n服务端已 shutdown 并关闭，端口释放。")

    print("\n" + "=" * 72)
    print("小结")
    print("-" * 72)
    print("1. HTTP/1.1 默认持久连接，同一连接可连续承载多个请求，源端口不变即为复用。")
    print("2. keep-alive 省去了重复的 TCP/TLS 握手，是 Web 性能的第一层优化。")
    print("3. HTTP/1.1 的队头阻塞要靠 HTTP/2 多路复用与 HTTP/3 的 QUIC 才能根治。")
    print("4. 服务端通过 Content-Length 或 chunked 明确正文边界，客户端才能正确复用连接。")


if __name__ == "__main__":
    main()
