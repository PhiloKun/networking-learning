#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 MAC 生成 EUI-64 接口标识（含第 7 位 U/L 翻转），并对比 RFC 4941 隐私扩展地址。

运行: python3 eui64_gen.py
     python3 eui64_gen.py 00:1a:2b:3c:4d:5e
"""
import ipaddress
import random
import sys

sys.dont_write_bytecode = True
random.seed(42)

MAC = "02:00:00:00:00:0A"           # 本仓库统一教学 MAC（本地管理位=1、单播位=0）
PREFIX = "2001:db8:abcd:100::/64"   # 站点外的 /64 前缀（第 07 章规划表里的研发园区办公区）

# RFC 4941 隐私扩展的默认计时器（秒）
TEMP_PREFERRED_LIFETIME = 604800    # 7 天
TEMP_VALID_LIFETIME = 1209600       # 14 天
# RFC 4862 重复地址检测（DAD）
DAD_TRANSMITS = 1
DAD_RETRANS_MS = 1000


def mac_to_bytes(mac: str) -> list:
    parts = mac.split(":")
    if len(parts) != 6:
        raise ValueError("MAC 必须是 6 组、每组 2 位十六进制，例如 02:00:00:00:00:0A")
    return [int(p, 16) for p in parts]


def bit_info(mac: str) -> tuple:
    b0 = mac_to_bytes(mac)[0]
    ig = b0 & 0x01          # 第 8 位（最低位）：I/G，0=单播 1=组播
    ul = (b0 >> 1) & 0x01   # 第 7 位：U/L，0=全球唯一 1=本地管理
    return ("组播" if ig else "单播",
            "本地管理" if ul else "全球唯一（OUI 分配）")


def eui64(mac: str) -> tuple:
    """MAC-48 → EUI-64：中间插 FF:FE，再把首字节第 7 位（0x02）取反。"""
    b = mac_to_bytes(mac)
    step1 = b[:3] + [0xFF, 0xFE] + b[3:]            # 插入 FF:FE → 8 字节
    step2 = step1[:]
    step2[0] ^= 0x02                                # 翻转 U/L 位
    return step1, step2


def to_iid_groups(b: list) -> str:
    """8 字节 → 4 组 16 位十六进制。"""
    return ":".join(f"{b[i] << 8 | b[i + 1]:04x}" for i in range(0, 8, 2))


def link_local(iid_bytes: list) -> str:
    addr = int.from_bytes(b"\xfe\x80" + b"\x00" * 6 + bytes(iid_bytes), "big")
    return str(ipaddress.IPv6Address(addr))


def gua(prefix: str, iid_bytes: list) -> str:
    net = ipaddress.ip_network(prefix, strict=False)
    addr = int(net.network_address) | int.from_bytes(bytes(iid_bytes), "big")
    return str(ipaddress.IPv6Address(addr))


def random_iid() -> list:
    """RFC 4941：随机生成 64 位接口标识（首字节保留 I/G=0、U/L=0 的形式，其余随机）。"""
    b = [random.randint(0, 255) for _ in range(8)]
    b[0] = (b[0] & 0xFC) | 0x00      # 清掉 I/G 与 U/L 两位
    return b


def self_check() -> None:
    # 官方示例：MAC 00:1a:2b:3c:4d:5e → IID 021a:2bff:fe3c:4d5e
    s1, s2 = eui64("00:1a:2b:3c:4d:5e")
    assert s1 == [0x00, 0x1A, 0x2B, 0xFF, 0xFE, 0x3C, 0x4D, 0x5E]
    assert s2 == [0x02, 0x1A, 0x2B, 0xFF, 0xFE, 0x3C, 0x4D, 0x5E]
    assert to_iid_groups(s2) == "021a:2bff:fe3c:4d5e"
    # 教学 MAC 02:00:00:00:00:0A → 首字节 02 XOR 02 = 00
    s1, s2 = eui64(MAC)
    assert s2 == [0x00, 0x00, 0x00, 0xFF, 0xFE, 0x00, 0x00, 0x0A]
    assert to_iid_groups(s2) == "0000:00ff:fe00:000a"
    assert link_local(s2) == "fe80::ff:fe00:a"
    assert gua(PREFIX, s2) == "2001:db8:abcd:100:0:ff:fe00:a"
    # 位判定
    assert bit_info(MAC) == ("单播", "本地管理")
    assert bit_info("00:1a:2b:3c:4d:5e") == ("单播", "全球唯一（OUI 分配）")


def main() -> int:
    mac = sys.argv[1] if len(sys.argv) > 1 else MAC
    try:
        mac_to_bytes(mac)
    except ValueError as exc:
        print(f"[输入错误] {mac!r}: {exc}")
        return 0
    self_check()

    ig, ul = bit_info(mac)
    print("=" * 84)
    print("MAC → EUI-64 接口标识生成（教学默认 MAC 02:00:00:00:00:0A）")
    print("=" * 84)
    print(f"输入 MAC       : {mac}")
    print(f"  首字节       : 0x{mac_to_bytes(mac)[0]:02x} = {mac_to_bytes(mac)[0]:08b}")
    print(f"  第 8 位 I/G  : {mac_to_bytes(mac)[0] & 1}  → {ig}")
    print(f"  第 7 位 U/L  : {(mac_to_bytes(mac)[0] >> 1) & 1}  → {ul}")
    print("-" * 84)
    s1, s2 = eui64(mac)
    print("步骤 1：把 48 位 MAC 从中间劈开，插入 FF:FE（16 位），凑成 64 位")
    print(f"        {mac.replace(':', '-')}  →  {'-'.join(f'{x:02x}' for x in s1)}")
    print("步骤 2：把首字节的第 7 位（掩码 0x02，U/L 位）取反")
    print(f"        {s1[0]:02x} XOR 02 = {s2[0]:02x}"
          f"  →  {'-'.join(f'{x:02x}' for x in s2)}")
    print(f"步骤 3：拼接成 4 组 16 位 → 接口标识 IID = {to_iid_groups(s2)}")
    print("-" * 84)
    print(f"链路本地地址   : {link_local(s2)}   （fe80::/10，仅本链路有效）")
    print(f"全球单播地址   : {gua(PREFIX, s2)}")
    print(f"                  （前缀 {ipaddress.ip_network(PREFIX, strict=False)} + IID）")
    print("-" * 84)
    print("为什么要翻转 U/L 位？（RFC 4291 附录 A）")
    print("  1. MAC 地址与 IPv6 接口标识都用一个比特表示「全球唯一 / 本地管理」，")
    print("     但两者在该位上的取值约定相反，直接照搬会导致语义颠倒。")
    print("  2. 取反后，节点可以从 IID 的特定位一眼区分「由硬件地址派生」与「本地手工分配」。")
    print(f"  3. 本例：MAC 是「{ul}」（该位={ (mac_to_bytes(mac)[0] >> 1) & 1 }），"
          f"翻转后 IID 该位={ (s2[0] >> 1) & 1 }。")
    print()
    print("=" * 84)
    print("对比：RFC 4941 隐私扩展地址（随机生成、定期更换，不泄露硬件厂商）")
    print("=" * 84)
    print(f"  {'序号':<6}{'IID':<26}{'完整地址'}")
    for i in range(1, 4):
        b = random_iid()
        print(f"  {i:<6}{to_iid_groups(b):<26}{gua(PREFIX, b)}")
    print("-" * 84)
    print("  MAC 派生 IID 与隐私扩展 IID 的差异：")
    print("  ① MAC 派生：稳定不变，同一网卡在任何网络里 IID 相同 → 可被跨网络追踪。")
    print("  ② 隐私扩展：随机生成、定期更换，无法跨网络关联，但不便于用地址反向定位资产。")
    print(f"  ③ 生命周期：临时地址 preferred {TEMP_PREFERRED_LIFETIME}s（7 天）、"
          f"valid {TEMP_VALID_LIFETIME}s（14 天）。")
    print(f"  ④ 现代系统（Windows/macOS/Android）默认启用隐私扩展，getent/ip addr 会同时看到多个地址。")
    print()
    print("地址上线前还要过 DAD（重复地址检测）：")
    print(f"  主机向该地址的请求节点组播发 NS，等 {DAD_TRANSMITS} 次 × {DAD_RETRANS_MS}ms；")
    print("  收到任何 NA 就说明地址冲突，该地址被标记为 duplicate 且不可用。")
    print(">>> 结论：EUI-64 生成过程完全确定（插 FFFE + 翻转 U/L），同一 MAC 永远得到同一 IID。")
    print(">>> 结论：现代终端默认优先使用隐私扩展地址，EUI-64 地址更多出现在服务器/网络设备上。")
    print()
    print("小结")
    print("  1. EUI-64 两步走：中间插 FF:FE、首字节第 7 位取反，得到 64 位接口标识。")
    print("  2. 接口标识拼上前缀（fe80::/10 或 GUA /64）就是完整的 IPv6 地址。")
    print("  3. 隐私扩展用随机 IID 换取不可追踪性，代价是地址与资产不再一一对应。")
    print("  4. 地址启用前必须做 DAD，冲突地址会被操作系统标记为 duplicate 而不可用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
