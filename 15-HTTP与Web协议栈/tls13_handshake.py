#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比 TLS 1.3 与 1.2 握手序列，演示 HKDF-Extract/Expand 密钥派生与密钥计划。

运行: python3 tls13_handshake.py
"""
import hashlib
import hmac
import sys

sys.dont_write_bytecode = True

HASH_LEN = 32          # SHA-256 输出长度


def hkdf_extract(salt: bytes, ikm: bytes, hash_name: str = "sha256") -> bytes:
    """HKDF-Extract：PRK = HMAC-Hash(salt, IKM)。salt 为空时按 HashLen 个 0 处理。"""
    if not salt:
        salt = b"\x00" * HASH_LEN
    return hmac.new(salt, ikm, getattr(hashlib, hash_name)).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int,
                hash_name: str = "sha256") -> bytes:
    """HKDF-Expand：T(1)=HMAC(PRK, info||0x01)，T(n)=HMAC(PRK, T(n-1)||info||n)。"""
    hash_len = HASH_LEN
    n = (length + hash_len - 1) // hash_len
    okm = b""
    t = b""
    for i in range(1, n + 1):
        t = hmac.new(prk, t + info + bytes([i]), getattr(hashlib, hash_name)).digest()
        okm += t
    return okm[:length]


def hkdf_expand_label(secret: bytes, label: str, context: bytes,
                      length: int) -> bytes:
    """TLS 1.3 的 HKDF-Expand-Label：把 info 构造成「长度 | 标签 | 上下文」。"""
    full_label = b"tls13 " + label.encode()
    info = (length.to_bytes(2, "big") + bytes([len(full_label)]) + full_label
            + bytes([len(context)]) + context)
    return hkdf_expand(secret, info, length)


def hx(data: bytes) -> str:
    return data.hex()


def main() -> None:
    print("=" * 74)
    print("TLS 1.3 与 TLS 1.2 握手对比 + HKDF 密钥派生演示")
    print("=" * 74)

    print("\n[1] TLS 1.2 握手消息序列（完整握手 = 2 RTT）")
    tls12 = [
        "ClientHello                         ->  （明文：支持的版本、密码套件、随机数）",
        "                             <- ServerHello（选定套件、服务器随机数）",
        "                             <- Certificate（服务器证书链）",
        "                             <- ServerKeyExchange（ECDHE 参数 + 签名）",
        "                             <- ServerHelloDone",
        "ClientKeyExchange                   ->  （客户端 ECDHE 公钥）",
        "ChangeCipherSpec + Finished         ->",
        "                             <- ChangeCipherSpec + Finished",
        "【应用数据】",
    ]
    for line in tls12:
        print("    " + line)
    print("    >>> 第 1 个 RTT 完成协商与密钥交换，第 2 个 RTT 才切换加密并完成握手")

    print("\n[2] TLS 1.3 握手消息序列（完整握手 = 1 RTT）")
    tls13 = [
        "ClientHello + key_share + supported_versions  ->  （一次性把公钥也发出去）",
        "                             <- ServerHello + key_share（服务器公钥）",
        "                             <- {EncryptedExtensions}",
        "                             <- {Certificate}",
        "                             <- {CertificateVerify}",
        "                             <- {Finished}",
        "{Finished}                   ->",
        "【应用数据】",
        "说明：{} 表示该消息已被握手密钥加密；服务器在第 2 条消息后即开始派生密钥",
        "      客户端在收到 ServerHello 后也立刻派生，因此 1 RTT 即可完成。",
    ]
    for line in tls13:
        print("    " + line)
    print("    >>> TLS 1.3 支持 0-RTT（会话恢复）：客户端用 PSK 直接发应用数据，代价是重放风险")

    print("\n[3] 为什么 TLS 1.3 砍掉 RSA 密钥交换")
    print("    TLS 1.2 的 RSA 密钥交换：客户端用服务器证书里的 RSA 公钥加密预主密钥，")
    print("    服务器用私钥解密。若服务器私钥日后泄露，攻击者可解密所有历史会话 —— 无前向安全。")
    print("    TLS 1.3 只保留 (EC)DHE：每次会话临时生成密钥对，用完即丢，")
    print("    即使长期私钥泄露也解不出历史流量 —— 具备前向安全（Forward Secrecy）。")

    print("\n[4] HKDF-Extract 演示（PRK = HMAC-SHA256(salt, IKM)）")
    salt = bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000000")
    ikm_psk = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
    prk = hkdf_extract(salt, ikm_psk)
    print("    salt (32 字节全 0，首次无 PSK 时) = %s" % hx(salt))
    print("    IKM  (输入密钥材料=PSK)          = %s" % hx(ikm_psk))
    print("    PRK  (伪随机密钥)                = %s" % hx(prk))
    print("    验证：HMAC-SHA256 输出固定 32 字节")

    print("\n[5] HKDF-Expand 演示（OKM = HKDF-Expand(PRK, info, L)）")
    info = b"tls13 derived"
    okm = hkdf_expand(prk, info, 32)
    print("    PRK  = %s" % hx(prk))
    print("    info = %r" % info)
    print("    L    = 32 字节")
    print("    OKM  = %s" % hx(okm))
    print("    迭代过程：T(1)=HMAC(PRK, info||0x01)，需要更长时 T(2)=HMAC(PRK, T(1)||info||0x02)")

    print("\n[6] TLS 1.3 密钥计划（Key Schedule）三步派生")
    ecdhe_shared = bytes.fromhex("a0b1c2d3e4f5061728394a5b6c7d8e9f")
    zero_salt = b"\x00" * 32
    early_secret = hkdf_extract(zero_salt, ikm_psk)
    derived1 = hkdf_expand_label(early_secret, "derived", b"", 32)
    handshake_secret = hkdf_extract(derived1, ecdhe_shared)
    derived2 = hkdf_expand_label(handshake_secret, "derived", b"", 32)
    master_secret = hkdf_extract(derived2, b"\x00" * 32)
    client_hs_traffic = hkdf_expand_label(handshake_secret, "c hs traffic", b"\x00", 32)
    server_hs_traffic = hkdf_expand_label(handshake_secret, "s hs traffic", b"\x00", 32)

    print("    ① Early Secret     = HKDF-Extract(0, PSK)          = %s" % hx(early_secret)[:32] + "...")
    print("       derived         = Derive-Secret(Early, 'derived', '')")
    print("    ② Handshake Secret = HKDF-Extract(derived, ECDHE)  = %s" % hx(handshake_secret)[:32] + "...")
    print("       derived         = Derive-Secret(Handshake, 'derived', '')")
    print("    ③ Master Secret    = HKDF-Extract(derived, 0)      = %s" % hx(master_secret)[:32] + "...")
    print("    握手流量密钥：")
    print("      client_handshake_traffic = HKDF-Expand-Label(Handshake, 'c hs traffic') = %s" % hx(client_hs_traffic)[:32] + "...")
    print("      server_handshake_traffic = HKDF-Expand-Label(Handshake, 's hs traffic') = %s" % hx(server_hs_traffic)[:32] + "...")
    print("    >>> ECDHE 共享密钥参与 Handshake Secret 派生，因此每次会话密钥都不同")
    print("    >>> 这是前向安全的来源：长期私钥只用于「签名」而非「解密」")

    print("\n[7] 握手往返与安全特性对比")
    print("    %-22s %-24s %s" % ("对比项", "TLS 1.2", "TLS 1.3"))
    print("    " + "-" * 68)
    rows = [
        ("完整握手往返", "2 RTT", "1 RTT"),
        ("会话恢复", "1 RTT（Session ID/Ticket）", "0 RTT（PSK）"),
        ("密钥交换", "RSA 或 (EC)DHE", "仅 (EC)DHE"),
        ("前向安全", "RSA 套件下不具备", "强制具备"),
        ("明文握手消息", "证书等大量消息明文", "仅 ClientHello/ServerHello 明文"),
        ("密钥派生", "PRF（部分实现混用）", "标准 HKDF（Extract+Expand）"),
        ("加密套件", "含 RSA/静态 DH 等", "AEAD + HKDF 组合"),
        ("SNI", "明文（可被窥探）", "默认明文，可用 ECH 加密"),
    ]
    for a, b, c in rows:
        print("    %-22s %-24s %s" % (a, b, c))

    print("\n" + "=" * 74)
    print("小结")
    print("-" * 74)
    print("1. TLS 1.3 把密钥交换移到第一个 RTT，完整握手从 2 RTT 降到 1 RTT，恢复可 0 RTT。")
    print("2. HKDF 分 Extract（压成固定长度 PRK）与 Expand（拉出所需长度 OKM）两步。")
    print("3. TLS 1.3 密钥计划按 Early -> Handshake -> Master 三级派生，ECDHE 参与其中。")
    print("4. 砍掉 RSA 密钥交换是为强制前向安全：私钥只用于签名，泄露也无法解密历史流量。")


if __name__ == "__main__":
    main()
