#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""海明码 (7,4)：4 位数据编码为 7 位，注入 1 位错误并用校验子定位纠正。

运行: python3 hamming_code.py [4位数据，默认 1011] [错误位置 1~7，默认 5]
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 72
SUB = "-" * 72
DATA_DEFAULT = "1011"
ERR_DEFAULT = 5


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


# 校验位所在位置（2 的幂次）与其覆盖的数据位位置
PARITY_POS = [1, 2, 4]
# 位置 1~7 用 3 位二进制表示，第 k 位为 1 的位被校验位 p_k 覆盖
COVER = {
    1: [1, 3, 5, 7],
    2: [2, 3, 6, 7],
    4: [4, 5, 6, 7],
}


def encode(data: str) -> list[str]:
    """返回长度为 8 的列表 code，下标 1~7 有效（下标 0 占位）。"""
    code = ["-"] * 8
    # 数据位放到 3,5,6,7
    data_pos = [3, 5, 6, 7]
    for p, b in zip(data_pos, data):
        code[p] = b
    # 计算校验位：使覆盖范围内 1 的个数为偶数
    for p in PARITY_POS:
        ones = sum(1 for pos in COVER[p] if pos != p and code[pos] == "1")
        code[p] = "1" if ones % 2 == 1 else "0"
    return code


def syndrome(code: list[str]) -> int:
    """计算校验子：把每个校验位覆盖组的奇偶结果拼成二进制数。"""
    s = 0
    for i, p in enumerate(PARITY_POS):
        ones = sum(1 for pos in COVER[p] if code[pos] == "1")
        bit = ones % 2
        s |= bit << i
    return s


def main() -> None:
    data = sys.argv[1] if len(sys.argv) > 1 else DATA_DEFAULT
    if len(data) != 4 or any(ch not in "01" for ch in data):
        print("数据必须是 4 位 0/1 串，已回退到默认值 1011")
        data = DATA_DEFAULT
    err = int(sys.argv[2]) if len(sys.argv) > 2 else ERR_DEFAULT
    if not (1 <= err <= 7):
        err = ERR_DEFAULT

    m, r = 4, 3
    print(SEP)
    print("海明码 (7,4) 编码 · 检错与纠错")
    print(SEP)
    print(f"数据位数 m = {m}    校验位数 r = {r}    总长 n = m + r = {m + r}")
    print(f"约束不等式 2^r >= m + r + 1 :  2^{r} = {2 ** r} >= {m} + {r} + 1 = {m + r + 1}"
          f"  ->  {'成立' if 2 ** r >= m + r + 1 else '不成立'}")
    print(f"最小码距 d_min = 3，可检出 2 位错，纠正 1 位错（d_min = 2t + 1, t = 1）")
    print()

    print(SUB)
    print("【一】位置分配：校验位放在 2 的幂次位置 1/2/4，数据位放 3/5/6/7")
    print(SUB)
    print(pad("位置", 8) + "".join(pad(str(i), 6) for i in range(1, 8)))
    print(pad("二进制", 8) + "".join(pad(f"{i:03b}", 6) for i in range(1, 8)))
    role = []
    for i in range(1, 8):
        role.append("P" if i in PARITY_POS else "D")
    print(pad("角色", 8) + "".join(pad(x, 6) for x in role))
    print(SUB)
    print("覆盖关系：")
    for p in PARITY_POS:
        print(f"  P{p} 覆盖位置 {COVER[p]}（自身 + 二进制第 {PARITY_POS.index(p)} 位为 1 的位置）")
    print()

    code = encode(data)
    print(SUB)
    print("【二】编码过程：逐位计算校验位（偶校验，使覆盖组内 1 的个数为偶数）")
    print(SUB)
    print(f"先把数据位填入: 位置3=D1={data[0]}, 位置5=D2={data[1]}, "
          f"位置6=D3={data[2]}, 位置7=D4={data[3]}")
    print()
    for p in PARITY_POS:
        others = [pos for pos in COVER[p] if pos != p]
        vals = " ^ ".join(code[pos] for pos in others)
        ones = sum(1 for pos in others if code[pos] == "1")
        print(f"  P{p} = {vals} = {'1' if (ones % 2) == 1 else '0'}"
              f"   （组内 1 的个数={ones}，需凑偶 -> P{p}={code[p]}）")
    code_str = "".join(code[1:])
    print()
    print(f">>> 编码结果（位置1..7）= {code_str}")
    print(f"    即 P1 P2 D1 P4 D2 D3 D4 = "
          f"{code[1]} {code[2]} {code[3]} {code[4]} {code[5]} {code[6]} {code[7]}")
    print(f"    传输的数据位仍是 {data}，索引 3/5/6/7 可读出。")
    print()

    print(SUB)
    print("【三】信道注入 1 位错误")
    print(SUB)
    bad = code[:]
    bad[err] = "1" if bad[err] == "0" else "0"
    bad_str = "".join(bad[1:])
    print(f"翻转位置 {err}：{code_str}  ->  {bad_str}")
    print()

    print(SUB)
    print("【四】接收方计算校验子 S = (S4 S2 S1)，用二进制值定位错误位置")
    print(SUB)
    print(pad("校验组", 20) + pad("覆盖位置的值", 28) + pad("1 的个数", 10, True) + "  S 位")
    print(SUB)
    s_total = 0
    for i, p in enumerate(PARITY_POS):
        vals = " ^ ".join(bad[pos] for pos in COVER[p])
        ones = sum(1 for pos in COVER[p] if bad[pos] == "1")
        bit = ones % 2
        s_total |= bit << i
        print(pad(f"P{p} 组", 20) + pad(vals, 28) + pad(str(ones), 10, True) + f"  S{i + 1}={bit}")
    print(SUB)
    print(f">>> 校验子 S = {s_total}（二进制 {s_total:03b}）")
    if s_total == 0:
        print("    校验子为 0，判定无差错。")
    else:
        print(f"    校验子 = {s_total} 不为 0，错误位置就是第 {s_total} 位。")
        print(f"    纠正动作：翻转第 {s_total} 位 —— 与注入位置 {err} "
              f"{'一致，纠正成功' if s_total == err else '不一致'}。")
        fixed = bad[:]
        fixed[s_total] = "1" if fixed[s_total] == "0" else "0"
        fixed_str = "".join(fixed[1:])
        print(f"    纠正后码字 = {fixed_str}")
        print(f"    提取数据位 3/5/6/7 = {fixed[3]}{fixed[5]}{fixed[6]}{fixed[7]}"
              f"  （原始数据 {data}，{'恢复正确' if ''.join([fixed[3], fixed[5], fixed[6], fixed[7]]) == data else '不一致'}）")
    print()

    print(SUB)
    print("【五】海明码能力边界")
    print(SUB)
    print(pad("错误情况", 20) + pad("校验子", 14) + "结果")
    print(SUB)
    print(pad("0 位错", 20) + pad("0", 14) + "正确接收")
    print(pad("1 位错", 20) + pad("非 0", 14) + "可定位并纠正")
    print(pad("2 位错", 20) + pad("非 0", 14) + "能检出但纠错会出错")
    print(pad("3 位错", 20) + pad("可能为 0", 14) + "可能漏检")
    print(SUB)
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print(f"1. (7,4) 海明码用 3 个校验位保护 4 个数据位，满足 2^3 >= 4+3+1。")
    print(f"2. 编码结果 {code_str} 中，任一 1 位错误都会使校验子等于出错位置，直接定位。")
    print("3. 最小码距 3 意味着只能纠 1 位错；出现 2 位错时会「纠」到错误位置，需配合 CRC 检错。")
    print("4. 扩展海明码加 1 个全校验位后总长 8 位，可区分「1 位错」与「2 位错」。")
    print()


if __name__ == "__main__":
    main()
