#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印一次完整 SMTP 会话（EHLO→STARTTLS→MAIL→RCPT→DATA→.→QUIT）与 Base64 附件编码。

运行: python3 smtp_session.py
"""
import base64
import sys

sys.dont_write_bytecode = True

CODES = {
    "220": "服务就绪 / TLS 就绪",
    "221": "服务关闭，再见",
    "235": "认证成功",
    "250": "请求的操作已完成",
    "334": "等待认证凭据",
    "354": "开始输入邮件内容，以 <CRLF>.<CRLF> 结束",
    "421": "服务不可用，关闭连接",
    "450": "临时拒绝（邮箱不可用）",
    "550": "永久拒绝（邮箱不存在 / 被拒）",
    "554": "事务失败",
}


def line(direction: str, text: str) -> None:
    """direction: C(客户端) / S(服务器) / *（说明行）。"""
    if direction == "C":
        print("  C: %s" % text)
    elif direction == "S":
        code = text[:3]
        note = CODES.get(code, "")
        print("  S: %-60s  # %s" % (text, note))
    else:
        print("     %s" % text)


def build_mime() -> str:
    """构造一封带 Base64 附件的邮件（MIME multipart）。"""
    attachment = "网络实验室附件：这是一段中文测试内容。".encode("utf-8")
    b64 = base64.b64encode(attachment).decode("ascii")
    wrapped = "\r\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
    mime = (
        "From: alice@example.com\r\n"
        "To: bob@example.net\r\n"
        "Subject: =?utf-8?B?572R57uc5a6e6aqM6YKu5Lu2?=\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/mixed; boundary=\"BOUNDARY-42\"\r\n"
        "\r\n"
        "--BOUNDARY-42\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "Content-Transfer-Encoding: 8bit\r\n"
        "\r\n"
        "你好，这是一封测试邮件。\r\n"
        "--BOUNDARY-42\r\n"
        "Content-Type: application/octet-stream\r\n"
        "Content-Transfer-Encoding: base64\r\n"
        "Content-Disposition: attachment; filename=\"test.txt\"\r\n"
        "\r\n"
        + wrapped + "\r\n"
        "--BOUNDARY-42--\r\n"
    )
    return mime


def main() -> None:
    print("=" * 74)
    print("SMTP 会话全过程（端口 587 提交 + STARTTLS）")
    print("=" * 74)

    print("\n[1] SMTP 命令会话（C=客户端，S=服务器）")
    line("S", "220 mail.example.com ESMTP Postfix")
    line("C", "EHLO pc1.example.com")
    line("S", "250-mail.example.com")
    line("S", "250-PIPELINING")
    line("S", "250-SIZE 10240000")
    line("S", "250-STARTTLS")
    line("S", "250-8BITMIME")
    line("S", "250 AUTH LOGIN PLAIN")
    line("*", "说明：EHLO 返回服务器能力列表，客户端据此决定是否升级加密")
    line("C", "STARTTLS")
    line("S", "220 2.0.0 Ready to start TLS")
    line("*", "[此处进行 TLS 握手，之后所有命令与内容均加密]")
    line("C", "EHLO pc1.example.com")
    line("S", "250-mail.example.com")
    line("S", "250 AUTH LOGIN PLAIN")
    line("C", "AUTH PLAIN AGFsaWNlAHNlY3JldA==")
    line("S", "235 2.7.0 Authentication successful")
    line("*", "说明：认证后才允许提交邮件；587 是「提交端口」，25 用于服务器间中继")
    line("C", "MAIL FROM:<alice@example.com>")
    line("S", "250 2.1.0 Ok")
    line("C", "RCPT TO:<bob@example.net>")
    line("S", "250 2.1.5 Ok")
    line("C", "DATA")
    line("S", "354 End data with <CR><LF>.<CR><LF>")
    line("*", "[客户端发送邮件头部 + 正文 + 附件，见第 2 节]")
    line("C", ".")
    line("S", "250 2.0.0 Ok: queued as 4A2B1C")
    line("C", "QUIT")
    line("S", "221 2.0.0 Bye")

    print("\n[2] Base64 与 MIME 附件编码")
    mime = build_mime()
    raw = "网络实验室附件：这是一段中文测试内容。".encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    print("    原始附件字节数 = %d" % len(raw))
    print("    Base64 编码后长度 = %d（膨胀率 = %d / %d ≈ %.2f）"
          % (len(b64), len(b64), len(raw), len(b64) / len(raw)))
    print("    Base64 编码结果 = %s" % b64)
    print("    解码回原文验证 = %s" % (base64.b64decode(b64).decode("utf-8") ==
                                     "网络实验室附件：这是一段中文测试内容。"))
    print("    公式：Base64 每 3 字节原文编码为 4 个字符，长度 ≈ 4 × ceil(n/3)")
    print("          本例 4 × ceil(%d/3) = 4 × %d = %d" % (len(raw), -(-len(raw) // 3), len(b64)))
    print("\n    解码后的 MIME 结构：")
    for l in mime.replace("\r\n", "\n").split("\n"):
        if l:
            print("      | " + l)

    print("\n[3] 邮件三段式防伪链：SPF / DKIM / DMARC")
    print("    %-8s %-14s %-30s %s" % ("机制", "记录位置", "验证什么", "失败后果"))
    print("    " + "-" * 74)
    rows = [
        ("SPF", "DNS TXT 记录", "发信 IP 是否被该域授权", "标记为可疑/拒绝"),
        ("DKIM", "DNS TXT(公钥)+邮件头", "邮件内容与签名的密码学校验", "正文被篡改则验签失败"),
        ("DMARC", "DNS TXT (_dmarc)", "SPF/DKIM 与 From 域是否对齐", "按 p= 策略隔离/拒收"),
    ]
    for a, b, c, d in rows:
        print("    %-8s %-14s %-30s %s" % (a, b, c, d))
    print("\n    典型 SPF 记录：v=spf1 mx ip4:198.51.100.0/24 -all")
    print("      v=spf1  版本；mx 授权本域 MX；ip4:... 授权网段；-all 其余全部拒绝（hardfail）")
    print("    DKIM 校验点：邮件头 DKIM-Signature 含 d=(域) s=(选择器) b=(签名)，")
    print("      收件方用 d.s._domainkey.<域> 取公钥验签，并检查 h= 列出的头部是否被改。")
    print("    DMARC 校验点：要求 SPF 或 DKIM 至少一个「通过」且与 From 头域名对齐（Alignment）。")

    print("\n[4] POP3(110) 与 IMAP(143) 的关键差异")
    print("    %-14s %-26s %s" % ("维度", "POP3", "IMAP"))
    print("    " + "-" * 66)
    comp = [
        ("默认端口", "110（SSL 995）", "143（SSL 993）"),
        ("存储模型", "下载到本地后通常删除", "邮件保留在服务器"),
        ("多设备同步", "差（各自下载）", "好（服务器为唯一真相）"),
        ("文件夹/标记", "不支持", "支持文件夹、已读/星标"),
        ("部分下载", "整体下载", "支持只取头部/正文片段"),
        ("适用", "单设备、离线归档", "多设备、Webmail"),
    ]
    for a, b, c in comp:
        print("    %-14s %-26s %s" % (a, b, c))

    print("\n" + "=" * 74)
    print("小结")
    print("-" * 74)
    print("1. SMTP 用 587 做客户端提交、25 做服务器间中继，STARTTLS 把明文会话升级为加密。")
    print("2. DATA 以单独一行「.」结束；正文里若真出现以 . 开头的行需点填充（dot-stuffing）。")
    print("3. Base64 把二进制附件编码为文本，长度约为原文的 4/3（膨胀约 33%）。")
    print("4. SPF 查发信 IP、DKIM 验内容签名、DMARC 要求二者与 From 对齐，三者协同防伪造。")


if __name__ == "__main__":
    main()
