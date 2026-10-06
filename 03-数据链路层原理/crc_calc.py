#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRC 循环冗余校验：模 2 除法逐步演示 + 以太网 CRC-32 FCS 计算与校验。

运行: python3 crc_calc.py [数据比特串，默认 1101011011]
"""
import sys
import zlib
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 80
SUB = "-" * 80

DATA_DEFAULT = "1101011011"
GEN_STR = "10011"          # x^4 + x + 1，度 r=4，共 5 位
GEN_DESC = "x^4 + x + 1"


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def mod2_divide(dividend: str, divisor: str) -> tuple[str, list[tuple[int, str, str]]]:
    """模 2 除法，返回 (余数, 步骤列表)。步骤为 (位置, 异或前的被除数, 异或后)。"""
    dd = list(dividend)
    n = len(divisor)
    steps: list[tuple[int, str, str]] = []
    for i in range(len(dd) - n + 1):
        if dd[i] == "1":
            before = "".join(dd)
            for j in range(n):
                dd[i + j] = "1" if dd[i + j] != divisor[j] else "0"
            steps.append((i, before, "".join(dd)))
    remainder = "".join(dd[-(n - 1):])
    return remainder, steps


def crc32_reflected(data: bytes) -> int:
    """以太网 FCS 所用的 CRC-32（反射算法，多项式 0x04C11DB7 的反射形式 0xEDB88320）。"""
    poly = 0xEDB88320
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
    return crc ^ 0xFFFFFFFF


def main() -> None:
    data = sys.argv[1] if len(sys.argv) > 1 else DATA_DEFAULT
    if any(ch not in "01" for ch in data) or not data:
        print("输入必须是仅含 0/1 的非空比特串，已回退到默认值。")
        data = DATA_DEFAULT

    print(SEP)
    print("CRC 循环冗余校验 · 模 2 除法与以太网 FCS")
    print(SEP)
    print(f"数据 D = {data}   共 {len(data)} bit")
    print(f"生成多项式 G = {GEN_STR}  即 {GEN_DESC}   度数 r = {len(GEN_STR) - 1}")
    print()

    print(SUB)
    print("【一】发送方：数据后补 r=4 个 0，做成被除数")
    print(SUB)
    dividend = data + "0" * (len(GEN_STR) - 1)
    print(f"被除数 = D + 0000 = {dividend}")
    print()

    print(SUB)
    print("【二】模 2 除法（无借位，等价于逐位异或）：被除数最高位为 1 就与 G 异或")
    print(SUB)
    remainder, steps = mod2_divide(dividend, GEN_STR)
    print(f"{'步骤':<6}{'起始位':<8}{'异或前被除数':<26}{'异或后':<26}")
    print(SUB)
    for idx, (pos, before, after) in enumerate(steps, 1):
        print(pad(str(idx), 6) + pad(str(pos), 8) + pad(before, 26) + pad(after, 26))
    print(SUB)
    print(f"       除数是 {GEN_STR}")
    print(f"       前 {len(data)} 位已被商消耗，余数取最后 r={len(GEN_STR) - 1} 位")
    print(f">>> 余数（CRC）= {remainder}")
    print()

    print(SUB)
    print("【三】发送方发出的码字 = 数据 + 余数，接收方用同一个 G 再除一次")
    print(SUB)
    codeword = data + remainder
    rem2, steps2 = mod2_divide(codeword + "0" * (len(GEN_STR) - 1), GEN_STR)
    print(f"码字 = D + 余数 = {codeword}")
    print(f"接收方计算：CRC(码字) = {rem2}")
    print(f">>> 余数为 0，校验通过：接收方判定传输无差错（CRC 只能检错，不能纠错）。")
    print()

    print(SUB)
    print("【四】错误检出：翻转码字中的 1 位，再除一次")
    print(SUB)
    err_pos = 3
    bad = list(codeword)
    bad[err_pos] = "1" if bad[err_pos] == "0" else "0"
    bad_str = "".join(bad)
    rem3, _ = mod2_divide(bad_str + "0" * (len(GEN_STR) - 1), GEN_STR)
    print(f"注入错误：把第 {err_pos + 1} 位翻转 -> {bad_str}")
    print(f"接收方计算：CRC(错误码字) = {rem3}")
    print(f">>> 余数不为 0，判定出错，丢弃该帧。")
    print()

    print(SUB)
    print("【五】以太网 FCS：真实的 CRC-32")
    print(SUB)
    payload = bytes([0x45, 0x00, 0x00, 0x3C, 0x1C, 0x46, 0x40, 0x00])  # IPv4 首部片段
    c = crc32_reflected(payload)
    c_zlib = zlib.crc32(payload) & 0xFFFFFFFF
    hexs = " ".join(f"{b:02X}" for b in payload)
    print(f"待校验字节（{len(payload)} 字节）: {hexs}")
    print("算法：初始值 0xFFFFFFFF，反射多项式 0xEDB88320，结果再与 0xFFFFFFFF 异或")
    print(f"手算结果   : 0x{c:08X}")
    print(f"zlib 对照  : 0x{c_zlib:08X}")
    print(f">>> 两者一致：{c == c_zlib}")
    fcs_bytes = c.to_bytes(4, "little")
    print(f">>> 以太网 FCS 按小端序追加到帧尾: "
          f"{' '.join(f'{b:02X}' for b in fcs_bytes)}")
    print()
    # 再对照一个空载荷与一个单字节
    print("更多对照（验证实现正确性）：")
    for sample in [b"", b"\x00", b"A", bytes(range(16))]:
        h = " ".join(f"{b:02X}" for b in sample) if sample else "(空)"
        print(f"  {h:<52} -> 0x{crc32_reflected(sample):08X}")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. 生成多项式 G={GEN_STR}（{GEN_DESC}）能产生 {len(GEN_STR) - 1} 位 CRC 余数，"
          f"本算例余数为 {remainder}。")
    print("2. 发送方发「数据 + 余数」，接收方用同一 G 除，余数为 0 判为正确。")
    print("3. CRC 只能检错不能纠错；但能检测出所有单比特错、双比特错与奇数个错、"
          "以及长度小于等于 r 的突发错误。")
    print("4. 以太网 FCS 用 CRC-32（32 位余数，4 字节），残错率极低，是帧级差错的最后防线。")
    print()


if __name__ == "__main__":
    main()
