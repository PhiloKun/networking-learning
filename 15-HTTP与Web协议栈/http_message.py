#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析原始 HTTP 请求/响应报文（含 chunked 分块体），并反向构造合法请求。

运行: python3 http_message.py
"""
import sys

sys.dont_write_bytecode = True

REASON = {200: "OK", 301: "Moved Permanently", 302: "Found", 304: "Not Modified",
          400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
          500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable"}

RAW_REQUEST = (
    "GET /index.html?q=1 HTTP/1.1\r\n"
    "Host: www.example.com\r\n"
    "User-Agent: netlab/1.0\r\n"
    "Accept: text/html,application/json\r\n"
    "Accept-Encoding: gzip, br\r\n"
    "Connection: keep-alive\r\n"
    "Cookie: sid=abc123\r\n"
    "\r\n"
)

RAW_RESPONSE = (
    "HTTP/1.1 200 OK\r\n"
    "Date: Mon, 06 Oct 2026 08:00:00 GMT\r\n"
    "Server: nginx\r\n"
    "Content-Type: text/html; charset=utf-8\r\n"
    "Transfer-Encoding: chunked\r\n"
    "Cache-Control: max-age=300\r\n"
    "ETag: \"v1-abc\"\r\n"
    "\r\n"
    "18\r\n<html><body>hello</body>\r\n"
    "0e\r\n</html>--end--\r\n"
    "0\r\n"
    "\r\n"
)


def parse_start_and_headers(raw: bytes) -> tuple[str, list[tuple[str, str]], bytes]:
    """拆分起始行、头部列表与正文；头部按首次出现顺序返回。"""
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    start_line = lines[0].decode("latin-1")
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        name, _, value = line.decode("latin-1").partition(":")
        headers.append((name.strip(), value.strip()))
    return start_line, headers, body


def decode_chunked(body: bytes) -> tuple[bytes, list[tuple[int, bytes]]]:
    """按 chunked 编码逐块解析：每块「十六进制长度 CRLF 数据 CRLF」，以 0 块结束。"""
    chunks: list[tuple[int, bytes]] = []
    pos = 0
    while True:
        eol = body.find(b"\r\n", pos)
        size_line = body[pos:eol].split(b";")[0].strip()     # 忽略 chunk extension
        size = int(size_line, 16)
        pos = eol + 2
        if size == 0:
            break
        data = body[pos:pos + size]
        chunks.append((size, data))
        pos += size + 2                                       # 跳过数据后的 CRLF
    return b"".join(d for _s, d in chunks), chunks


def header_get(headers: list[tuple[str, str]], name: str) -> str | None:
    for k, v in headers:
        if k.lower() == name.lower():
            return v
    return None


def main() -> None:
    print("=" * 72)
    print("HTTP/1.1 报文解析与构造")
    print("=" * 72)

    print("\n[1] 解析原始请求报文")
    raw = RAW_REQUEST.encode("latin-1")
    start, headers, body = parse_start_and_headers(raw)
    method, target, version = start.split(" ")
    print("    原始字节数 = %d" % len(raw))
    print("    起始行 = %r" % start)
    print("      请求方法(Method) = %s" % method)
    print("      请求目标(Target) = %s" % target)
    print("      协议版本(Version) = %s" % version)
    print("    头部共 %d 个：" % len(headers))
    for k, v in headers:
        print("      %-16s : %s" % (k, v))
    print("    正文长度 = %d 字节（GET 无正文，头部后紧跟空行 CRLF CRLF）" % len(body))
    print("    >>> Host 头是 HTTP/1.1 的必填项，虚拟主机靠它区分同一 IP 上的不同站点")

    print("\n[2] 解析原始响应报文（含 chunked 分块体）")
    raw_resp = RAW_RESPONSE.encode("latin-1")
    start, headers, body = parse_start_and_headers(raw_resp)
    ver, code, reason = start.split(" ", 2)
    print("    起始行 = %r" % start)
    print("      版本 = %s  状态码 = %s  原因短语 = %s" % (ver, code, reason))
    print("    关键头部：")
    for key in ("Date", "Server", "Content-Type", "Transfer-Encoding", "Cache-Control", "ETag"):
        v = header_get(headers, key)
        if v is not None:
            print("      %-18s: %s" % (key, v))
    print("    Content-Length 是否存在？ %s" % (header_get(headers, "Content-Length") is not None))
    print("    >>> 使用 chunked 时不能同时带 Content-Length（二者互斥，二选一）")

    print("\n[3] 逐块解码 chunked 正文")
    decoded, chunks = decode_chunked(body)
    for i, (size, data) in enumerate(chunks, 1):
        print("    块 %d: 长度 = 0x%02X = %d 字节，内容 = %r" % (i, size, size, data))
    print("    结束块 = 0（长度行 0x0，之后是空行）")
    print("    拼接后正文 = %r" % decoded)
    print("    总正文长度 = %d 字节" % len(decoded))
    total_chunk_overhead = sum(len(("%X" % s).encode()) + 2 + 2 for s, _ in chunks) + 5
    print("    >>> 分块编码额外开销约 %d 字节（长度行 + CRLF + 结束块）" % total_chunk_overhead)

    print("\n[4] 反向构造一个合法请求并做格式校验")
    built_headers = [
        ("Host", "www.example.com"),
        ("User-Agent", "netlab/1.0"),
        ("Accept", "*/*"),
        ("Connection", "keep-alive"),
    ]
    lines = ["GET / HTTP/1.1"]
    lines += ["%s: %s" % (k, v) for k, v in built_headers]
    built = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    print("    构造结果（转义显示）：")
    print("      " + built.decode("latin-1").replace("\r\n", "\\r\\n"))
    checks = [
        ("以 CRLF 结尾且含头部结束空行", built.endswith(b"\r\n\r\n")),
        ("起始行格式 Method SP Target SP Version", len(lines[0].split(" ")) == 3),
        ("含 Host 头", header_get(built_headers, "Host") is not None),
        ("Connection 为 keep-alive", header_get(built_headers, "Connection") == "keep-alive"),
    ]
    print("    校验项：")
    for name, ok in checks:
        print("      [%s] %s" % ("通过" if ok else "失败", name))

    print("\n[5] 请求方法幂等性对照")
    idem = [("GET", "是", "只读获取资源"), ("HEAD", "是", "只取头部"),
            ("PUT", "是", "整体替换资源"), ("DELETE", "是", "删除资源"),
            ("POST", "否", "创建/提交，重复提交会重复生效"),
            ("PATCH", "否", "局部更新，结果依赖实现"),
            ("OPTIONS", "是", "查询支持的方法")]
    print("    %-8s %-8s %s" % ("方法", "幂等", "说明"))
    print("    " + "-" * 44)
    for m, i, d in idem:
        print("    %-8s %-8s %s" % (m, i, d))

    print("\n" + "=" * 72)
    print("小结")
    print("-" * 72)
    print("1. HTTP 报文 = 起始行 + 头部 + 空行(CRLF) + 正文；头部与正文之间必须有空行分隔。")
    print("2. 正文长度两种表达：Content-Length（定长）或 Transfer-Encoding: chunked（分块），二者互斥。")
    print("3. chunked 每块格式为「十六进制长度 CRLF 数据 CRLF」，以长度 0 的块结束。")
    print("4. HTTP/1.1 必带 Host 头；GET/HEAD/PUT/DELETE/OPTIONS 幂等，POST/PATCH 不幂等。")


if __name__ == "__main__":
    main()
