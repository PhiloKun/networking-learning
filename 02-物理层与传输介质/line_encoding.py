#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NRZ / 曼彻斯特 / 差分曼彻斯特线路编码的 ASCII 波形与直流分量对比。

运行: python3 line_encoding.py [比特串，默认 10110010]
"""
import sys
import unicodedata

sys.dont_write_bytecode = True

BITS_DEFAULT = "10110010"
CELL_W = 3          # 每个半比特时间单元占 3 个字符
SEP = "=" * 72
SUB = "-" * 72


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def nrz_cells(bits: str) -> list[int]:
    """NRZ：高电平=1，低电平=0，每个比特占 2 个时间单元。"""
    cells: list[int] = []
    for b in bits:
        level = 1 if b == "1" else 0
        cells += [level, level]
    return cells


def manchester_cells(bits: str) -> list[int]:
    """IEEE 802.3 曼彻斯特：0 = 高到低跳变，1 = 低到高跳变（每个比特从中间跳变）。"""
    cells: list[int] = []
    for b in bits:
        if b == "0":
            cells += [1, 0]
        else:
            cells += [0, 1]
    return cells


def diff_manchester_cells(bits: str, start: int = 0) -> list[int]:
    """差分曼彻斯特：比特起始处有跳变=0，无跳变=1；比特中间必跳变。"""
    cells: list[int] = []
    level = start
    for b in bits:
        if b == "0":
            level = 1 - level
        first = level
        level = 1 - level
        cells += [first, level]
    return cells


def render(cells: list[int]) -> tuple[str, str]:
    """返回 (波形字符串, 跳变标记串)。高电平显示 '-'，低电平显示 '_'。"""
    wave = ""
    mark = ""
    prev = None
    for c in cells:
        wave += ("-" if c == 1 else "_") * CELL_W
        mark += ("^" if (prev is not None and c != prev) else " ") + " " * (CELL_W - 1)
        prev = c
    return wave, mark


def dc_component(cells: list[int]) -> float:
    """直流分量：以 1=+1、0=-1 求平均电平。"""
    return sum(1 if c == 1 else -1 for c in cells) / len(cells)


def transitions(cells: list[int]) -> int:
    return sum(1 for i in range(1, len(cells)) if cells[i] != cells[i - 1])


def main() -> None:
    bits = sys.argv[1] if len(sys.argv) > 1 else BITS_DEFAULT
    if any(ch not in "01" for ch in bits) or not bits:
        print("输入必须是仅含 0/1 的非空比特串，已回退到默认值。")
        bits = BITS_DEFAULT

    print(SEP)
    print("线路编码波形对比 · NRZ / 曼彻斯特 / 差分曼彻斯特")
    print(SEP)
    print(f"输入比特串: {bits}   共 {len(bits)} 位")
    print(f"图例: '-' = 高电平   '_' = 低电平   '^' = 该处发生电平跳变")
    print(f"每个比特占 2 个时间单元，每单元 {CELL_W} 字符")
    print()

    encoders = [
        ("NRZ", nrz_cells(bits), "1->高，0->低；无自带同步"),
        ("曼彻斯特", manchester_cells(bits), "每比特中间必跳变；0=高到低，1=低到高"),
        ("差分曼彻斯特", diff_manchester_cells(bits), "起始跳变=0，无跳变=1；中间必跳变"),
    ]

    print(SUB)
    print("【一】波形图")
    print(SUB)
    # 时间轴
    axis = ""
    for i, b in enumerate(bits):
        axis += pad(b, CELL_W * 2, right=False)
    print(pad("比特", 14) + axis)
    print(SUB)
    for name, cells, note in encoders:
        wave, mark = render(cells)
        print(pad(name, 14) + wave)
        print(pad("", 14) + mark)
    print(SUB)
    for name, cells, note in encoders:
        print(f"  {name}: {note}")
    print()

    print(SUB)
    print("【二】直流分量（1=+1，0=-1，取全体时间单元平均）")
    print(SUB)
    print(pad("编码", 16) + pad("直流分量", 12, True) + pad("跳变次数", 12, True) + "  同步能力")
    print(SUB)
    for name, cells, note in encoders:
        dc = dc_component(cells)
        tr = transitions(cells)
        if name == "NRZ":
            sync = "差：长连 0 或连 1 时无跳变，易失步"
        else:
            sync = "强：每比特中间必有跳变"
        print(pad(name, 16) + pad(f"{dc:+.3f}", 12, True) + pad(f"{tr} 次", 12, True)
              + "  " + sync)
    print(SUB)
    print(">>> 曼彻斯特与差分曼彻斯特的直流分量恒为 0（每比特一高一低），")
    print("    NRZ 的直流分量取决于 0/1 比例，长连 0 或连 1 时会累积直流偏移。")
    print()

    print(SUB)
    print("【三】同步能力量化：每个比特的平均跳变次数")
    print(SUB)
    for name, cells, note in encoders:
        per_bit = transitions(cells) / len(bits)
        print(pad(name, 16) + f" {per_bit:.2f} 次/比特")
    print(SUB)
    # 构造一段长连比特做对照
    long_run = "0" * 8
    nrz_run = nrz_cells(long_run)
    man_run = manchester_cells(long_run)
    print(f">>> 对照实验：比特串全为 0 时")
    print(f"    NRZ 跳变次数 = {transitions(nrz_run)} 次（无跳变，接收端无法提取时钟）")
    print(f"    曼彻斯特跳变次数 = {transitions(man_run)} 次（每比特仍有中间跳变，时钟不丢）")
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print("1. NRZ 编码效率最高（每比特只需 1 个信号单元），但缺乏自带同步且存在直流分量问题。")
    print("2. 曼彻斯特用 2 倍带宽换取「每比特必跳变」，接收端可直接从信号中提取时钟，且直流分量为 0。")
    print("3. 差分曼彻斯特在中间跳变的基础上，用比特边界的「有无跳变」区分 0/1，抗极性反转能力更强。")
    print("4. 快速以太网 100BASE-TX 用 4B5B + MLT-3 替代曼彻斯特，正是为了把 2 倍带宽开销降下来。")
    print()


if __name__ == "__main__":
    main()
