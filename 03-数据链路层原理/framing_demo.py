#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""帧定界：字节填充（0x7E/0x7D 转义）与位填充（5 个 1 后插 0）的完整过程。

运行: python3 framing_demo.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

FLAG = 0x7E     # 帧定界符 01111110
ESC = 0x7D      # 转义符 01111101


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def hexs(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def bits_of(data: bytes) -> str:
    return "".join(f"{b:08b}" for b in data)


def byte_stuff(payload: bytes) -> tuple[bytes, list[str]]:
    out = bytearray([FLAG])
    log: list[str] = []
    for b in payload:
        if b == FLAG:
            out += bytes([ESC, FLAG ^ 0x20])
            log.append(f"  数据字节 0x7E 命中定界符 -> 转义为 0x7D 0x{FLAG ^ 0x20:02X}")
        elif b == ESC:
            out += bytes([ESC, ESC ^ 0x20])
            log.append(f"  数据字节 0x7D 命中转义符 -> 转义为 0x7D 0x{ESC ^ 0x20:02X}")
        else:
            out.append(b)
    out.append(FLAG)
    return bytes(out), log


def byte_destuff(frame: bytes) -> tuple[bytes, int]:
    assert frame[0] == FLAG and frame[-1] == FLAG
    body = frame[1:-1]
    out = bytearray()
    removed = 0
    i = 0
    while i < len(body):
        if body[i] == ESC:
            nxt = body[i + 1] ^ 0x20
            out.append(nxt)
            removed += 1
            i += 2
        else:
            out.append(body[i])
            i += 1
    return bytes(out), removed


def bit_stuff(bits: str) -> tuple[str, list[int]]:
    out = []
    ones = 0
    inserted: list[int] = []
    for idx, b in enumerate(bits):
        out.append(b)
        if b == "1":
            ones += 1
            if ones == 5:
                out.append("0")
                inserted.append(len(out) - 1)
                ones = 0
        else:
            ones = 0
    return "".join(out), inserted


def bit_destuff(bits: str) -> tuple[str, int]:
    out = []
    ones = 0
    i = 0
    removed = 0
    while i < len(bits):
        b = bits[i]
        out.append(b)
        if b == "1":
            ones += 1
            if ones == 5:
                if i + 1 < len(bits) and bits[i + 1] == "0":
                    i += 2       # 跳过被填充的 0
                    removed += 1
                    ones = 0
                    continue
                ones = 0
        else:
            ones = 0
        i += 1
    return "".join(out), removed


def main() -> None:
    print(SEP)
    print("帧定界演示 · 字节填充 与 位填充")
    print(SEP)
    print(f"帧定界符 FLAG = 0x{FLAG:02X}（二进制 {FLAG:08b}）")
    print(f"转义符   ESC  = 0x{ESC:02X}（二进制 {ESC:08b}）")
    print("说明：0x7E ^ 0x20 = 0x5E，0x7D ^ 0x20 = 0x5D，转义=与原字节异或 0x20")
    print()

    print(SUB)
    print("【一】字节填充（面向字节的协议，如 PPP 的同步/异步字符流）")
    print(SUB)
    payload = bytes([0x7E, 0x41, 0x7D, 0x42, 0x7E])
    print(f"原始载荷（{len(payload)} 字节）: {hexs(payload)}")
    print("注意：载荷里本身含 0x7E，若直接发送，接收方会误以为是帧结束。")
    print(SUB)
    for line in byte_stuff(payload)[1]:
        print(line)
    frame, _ = byte_stuff(payload)
    print(SUB)
    print(f">>> 填充后整帧（{len(frame)} 字节）: {hexs(frame)}")
    print(f"    首尾各一个 0x7E 是帧定界符，中间的 0x7D 0x5E / 0x7D 0x5D 是转义序列。")
    print(f"    载荷 5 字节 -> 转义后 7 字节，开销 2 字节。")
    print()
    restored, removed = byte_destuff(frame)
    print(f">>> 接收方去填充还原: {hexs(restored)}   共去转义 {removed} 处，"
          f"与原始载荷一致: {restored == payload}")
    print()
    print("边界细节：转义符本身也必须转义。若载荷含 0x7D，必须写成 0x7D 0x5D，")
    print("否则接收方会把紧随其后的字节当成被转义字节，导致还原错误。")
    print()

    print(SUB)
    print("【二】位填充（面向比特的协议，如 HDLC / 以太网前导后的比特流）")
    print(SUB)
    raw = bytes([0x7E, 0xFC])
    bits = bits_of(raw)
    print(f"原始比特串（2 字节 = {len(bits)} bit）: {bits}")
    print("规则：发送方每见到 5 个连续 1，就插入 1 个 0，保证数据中永不出现 01111110。")
    stuffed, inserted = bit_stuff(bits)
    print(SUB)
    # 逐位展示，每 8 位分段
    print("原始 : " + " ".join(bits[i:i + 8] for i in range(0, len(bits), 8)))
    print("填充 : " + " ".join(stuffed[i:i + 8] for i in range(0, len(stuffed), 8)))
    print(f"插入 0 的位置（填充后串的下标，从 0 起）: {inserted}")
    print(f">>> 原始 {len(bits)} bit -> 填充后 {len(stuffed)} bit，多了 {len(stuffed) - len(bits)} 个填充位。")
    print()
    # 展示插入过程
    print("插入位置示意（^ 指向新增的 0）：")
    mark = [" "] * len(stuffed)
    for pos in inserted:
        mark[pos] = "^"
    for start in range(0, len(stuffed), 16):
        seg = stuffed[start:start + 16]
        mk = "".join(mark[start:start + 16])
        print(f"  {seg}")
        print(f"  {mk}")
    print()
    destuffed, rm = bit_destuff(stuffed)
    print(f">>> 接收方去填充: {destuffed}")
    print(f"    删除了 {rm} 个填充位，与原始比特串一致: {destuffed == bits}")
    print()

    print(SUB)
    print("【三】为什么位填充能保证不出错：满 5 个 1 必插 0")
    print(SUB)
    longest = 0
    cur = 0
    for b in stuffed:
        if b == "1":
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    print(f"填充后比特串中最长的连续 1 的个数 = {longest}")
    print(f">>> 只要限制最长连续 1 不超过 5，就不会出现 01111110（6 个 1）与定界符冲突。")
    print()

    print(SUB)
    print("【四】四种帧定界方法对比")
    print(SUB)
    print(pad("方法", 16) + pad("思路", 30) + pad("优点", 16) + "缺点")
    print(SUB)
    rows = [
        ("字符计数法", "首字节写帧内字节数", "实现简单", "计数被破坏即全乱"),
        ("字节填充", "转义 0x7E / 0x7D", "面向字节易实现", "依赖 8 位字符集"),
        ("位填充", "5 个 1 后插 0", "与字符集无关", "硬件实现稍复杂"),
        ("违规编码", "用非法电平组合做定界", "不占额外比特", "依赖特定编码方案"),
    ]
    for a, b, c, d in rows:
        print(pad(a, 16) + pad(b, 30) + pad(c, 16) + d)
    print(SUB)
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. 字节填充把载荷里的 0x7E/0x7D 转义，本算例 5 字节载荷膨胀为 7 字节。")
    print(f"2. 位填充每 5 个连续 1 插入 1 个 0，本算例插入 {len(inserted)} 位，"
          f"保证不出现定界符 01111110。")
    print("3. 接收方必须执行完全对称的去填充，转义符自身、填充位自身都要正确处理。")
    print("4. 无论哪种方法，本质都是让「载荷」与「定界符」在比特模式上永不冲突。")
    print()


if __name__ == "__main__":
    main()
