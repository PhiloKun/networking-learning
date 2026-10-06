#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WPA2-PSK 密钥派生：PBKDF2(SSID+口令, 4096 轮) → PMK，再演示 PTK 的组成来源。

运行: python3 wpa_psk_derive.py
"""
import binascii
import hashlib
import hmac
import sys

sys.dont_write_bytecode = True

SSID = "networking-lab"
PASSPHRASE = "P@ssw0rd-2026"
ITERATIONS = 4096          # WPA2-PSK 规定的 PBKDF2 迭代次数
PMK_LEN = 32               # PMK = 256 bit
PTK_LEN = 48               # CCMP 下 PTK = 384 bit = KCK(16)+KEK(16)+TK(16)
LABEL = b"Pairwise key expansion"

# 802.11i 的示例地址/nonce（真实抓包时来自 4 次握手报文）
AP_MAC = "02:00:00:00:00:0A"       # Authenticator Address (AA)
STA_MAC = "02:00:00:00:00:1B"      # Supplicant Address (SPA)
ANONCE = "5c2b1f3d8e7a4906b1c2d3e4f5061728" + "394a5b6c7d8e9f001122334455667788"
SNONCE = "a1b2c3d4e5f60718293a4b5c6d7e8f90" + "0102030405060708090a0b0c0d0e0f10"


def hx(b: bytes) -> str:
    return binascii.hexlify(b).decode()


def prf_sha1(key: bytes, label: bytes, data: bytes, out_len: int) -> bytes:
    """802.11i PRF：T_i = HMAC-SHA1(K, label || 0x00 || data || i)，级联后截断。"""
    out = b""
    i = 0
    while len(out) < out_len:
        out += hmac.new(key, label + b"\x00" + data + bytes([i]), hashlib.sha1).digest()
        i += 1
    return out[:out_len]


def pmk_from_psk(ssid: str, passphrase: str, iterations: int = ITERATIONS) -> bytes:
    """WPA2-PSK: PMK = PBKDF2-HMAC-SHA1(口令, SSID, 4096 轮, 32 字节)。"""
    return hashlib.pbkdf2_hmac("sha1", passphrase.encode(), ssid.encode(),
                               iterations, PMK_LEN)


def build_ptk_data(aa: str, spa: str, anonce: str, snonce: str) -> bytes:
    """PTK 输入 = Min/Max(AA,SPA) || Min/Max(ANonce,SNonce)（按字节序排序）。"""
    a = binascii.unhexlify(aa.replace(":", ""))
    s = binascii.unhexlify(spa.replace(":", ""))
    an = binascii.unhexlify(anonce)
    sn = binascii.unhexlify(snonce)
    return min(a, s) + max(a, s) + min(an, sn) + max(an, sn)


def bench_rounds_per_pmk_per_sec() -> float:
    """按 SHA-1 压缩次数估算暴力破解速率（纯计算模型，不发起任何真实攻击）。"""
    sha1_per_sec = 1.0e10        # 单张现代 GPU 的 SHA-1 压缩量级
    compressions = ITERATIONS * 2 * 2   # 每轮 HMAC 内外各 2 次压缩
    return sha1_per_sec / compressions


def main() -> int:
    print("=" * 78)
    print("WPA2-PSK 密钥派生演示（PBKDF2 → PMK → PTK，纯本地计算，无网络交互）")
    print("=" * 78)
    print(f"SSID       = {SSID!r}   （即 PSK 的「盐」，故意用明文且全网一致）")
    print(f"Passphrase = {PASSPHRASE!r}   （8~63 个 ASCII 字符，长度即安全下限）")
    print(f"迭代次数   = {ITERATIONS}（WPA2 强制，802.11i 规定）")
    print("-" * 78)

    pmk = pmk_from_psk(SSID, PASSPHRASE)
    print(f"PMK (256 bit) = {hx(pmk)}")
    print(f"  ├─ 前 16 字节 = {hx(pmk[:16])}")
    print(f"  └─ 后 16 字节 = {hx(pmk[16:])}")
    print()

    # 演示「改 SSID 会得到完全不同的 PMK」
    pmk2 = pmk_from_psk(SSID + "_x", PASSPHRASE)
    print("同口令、SSID 改一个字符后的 PMK（说明暴破必须针对具体 SSID 重算）：")
    print(f"  {hx(pmk2)}")
    print()

    data = build_ptk_data(AP_MAC, STA_MAC, ANONCE, SNONCE)
    ptk = prf_sha1(pmk, LABEL, data, PTK_LEN)
    print("PTK 派生输入（按字节序取 Min/Max，避免双方算出的顺序不同）：")
    print(f"  AA (AP MAC)  = {AP_MAC}")
    print(f"  SPA(STA MAC) = {STA_MAC}")
    print(f"  ANonce       = {ANONCE[:32]}...  ({len(ANONCE) * 4} bit)")
    print(f"  SNonce       = {SNONCE[:32]}...  ({len(SNONCE) * 4} bit)")
    print(f"  PRF label    = {LABEL.decode()!r} + 0x00 + 输入串 + 计数器 i")
    print()
    print(f"PTK (384 bit) = {hx(ptk)}")
    print(f"  ├─ KCK (16B) = {hx(ptk[0:16])}   ← 用于计算 4 次握手的 MIC")
    print(f"  ├─ KEK (16B) = {hx(ptk[16:32])}   ← 用于解密握手报文里的 WPA Key Data")
    print(f"  └─ TK  (16B) = {hx(ptk[32:48])}   ← 真正加密数据帧的 CCMP 会话密钥")
    print("-" * 78)

    rate = bench_rounds_per_pmk_per_sec()
    print("为什么要 4096 轮？（PBKDF2 迭代成本模型）")
    print(f"  单次 PMK 计算 = {ITERATIONS} 轮 × 2 次 HMAC × 2 次 SHA-1 压缩 = "
          f"{ITERATIONS * 2 * 2} 次压缩")
    print(f"  按 {1.0e10:.0e} 次 SHA-1 压缩/秒估算，单卡约 {rate:.0e} 个口令/秒")
    print(f"  8 位纯数字口令空间 = 1e8，全量枚举约 {1e8 / rate:.1f} 秒")
    print(f"  若迭代为 1 轮，同样的卡能快 {ITERATIONS} 倍 "
          f"（= {1e8 / (rate * ITERATIONS):.4f} 秒）")
    print(">>> 结论：4096 轮不增加算法强度，只是把单次尝试的成本放大 4096 倍。")
    print(">>> 结论：真正的防线是口令熵（≥12 位混合字符）+ 关闭 WPS + 启用 802.1X。")
    print(">>> 结论：PMK 与 SSID 强绑定，同一口令在不同 SSID 下 PMK 完全不同。")
    print()
    print("小结")
    print("  1. WPA2-PSK 的密钥链条：口令 + SSID --PBKDF2(4096)--> PMK --PRF--> PTK。")
    print("  2. PTK 把 KCK/KEK/TK 三段分开，各管一件事，避免用加密密钥去算完整性。")
    print("  3. 4 次握手里 ANonce/SNonce 每连接刷新，所以同一密码每次上线的 PTK 都不同。")
    print("  4. 迭代次数只拉高离线暴破成本，口令本身太弱仍然会被字典攻坚破。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
