#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""二层交换机 MAC 地址学习 / 泛洪 / 转发 / 老化全过程模拟（4 口）。"""

import sys
import unicodedata

sys.dont_write_bytecode = True

SEP = "=" * 80
SUB = "-" * 80
PORTS = [1, 2, 3, 4]
AGING_TIME = 300          # 思科默认 MAC 表老化时间 300 秒
MAC_TABLE: dict[str, tuple[int, float]] = {}

# (到达时刻, 入端口, 源 MAC, 目的 MAC)
FRAMES = [
    (0,  1, "02:00:00:00:00:0A", "02:00:00:00:00:0B"),   # 未知目的 -> 泛洪
    (1,  2, "02:00:00:00:00:0B", "02:00:00:00:00:0A"),   # 双向已知 -> 单播转发
    (2,  3, "02:00:00:00:00:0C", "02:00:00:00:00:0A"),   # 新源学习 + 已知目的转发
    (3,  4, "02:00:00:00:00:0D", "02:00:00:00:00:0C"),   # 未知目的 -> 泛洪
    (4,  1, "02:00:00:00:00:0A", "02:00:00:00:00:0A"),   # 目的=入端口 -> 过滤丢弃
    (5,  2, "02:00:00:00:00:0B", "02:00:00:00:00:0D"),   # 已知 -> 转发到 4 口
]


def dw(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, right: bool = False) -> str:
    space = max(0, width - dw(s))
    return (" " * space + s) if right else (s + " " * space)


def dump_table(now: float) -> None:
    if not MAC_TABLE:
        print("        MAC 表：空")
        return
    print("        MAC 表：")
    print("        " + pad("MAC 地址", 22) + pad("出端口", 10) + pad("表项年龄(s)", 12, True))
    for mac in sorted(MAC_TABLE):
        port, ts = MAC_TABLE[mac]
        print("        " + pad(mac, 22) + pad(f"G0/{port}", 10)
              + pad(f"{now - ts:.0f}", 12, True))


def process(now: float, in_port: int, src: str, dst: str) -> None:
    print(f"  [T+{now:.0f}s] 帧从端口 G0/{in_port} 进入：源 {src}  目的 {dst}")
    # 1) 学习源 MAC
    if src in MAC_TABLE:
        old_port, _ = MAC_TABLE[src]
        if old_port != in_port:
            print(f"    1. 学习：源 MAC {src} 原本在 G0/{old_port}，现移动到 G0/{in_port}，"
                  f"更新表项")
        else:
            print(f"    1. 学习：源 MAC {src} 已在 G0/{in_port}，刷新老化计时")
    else:
        print(f"    1. 学习：源 MAC {src} 首次出现，记录到 G0/{in_port}")
    MAC_TABLE[src] = (in_port, now)
    # 2) 查目的 MAC 决定动作
    if dst in MAC_TABLE:
        out_port, _ = MAC_TABLE[dst]
        if out_port == in_port:
            print(f"    2. 查表：目的 MAC {dst} 在 G0/{out_port}（与入端口相同）")
            print(f"    3. 动作：过滤（Filter）——同一端口不必转发，直接丢弃")
        else:
            print(f"    2. 查表：目的 MAC {dst} 命中，出端口 G0/{out_port}")
            print(f"    3. 动作：单播转发（Forward）——只从 G0/{out_port} 发出")
    else:
        others = [p for p in PORTS if p != in_port]
        print(f"    2. 查表：目的 MAC {dst} 未命中（未知单播）")
        print(f"    3. 动作：泛洪（Flood）——从除入端口外的 "
              f"{', '.join('G0/' + str(p) for p in others)} 发出")
    print()


def main() -> None:
    print(SEP)
    print("二层交换机 MAC 学习 / 泛洪 / 转发 / 老化 模拟 · 4 口交换机")
    print(SEP)
    print("初始状态：MAC 表为空。交换机对未知单播帧泛洪，对已知单播帧定向转发。")
    print()

    print(SUB)
    print("【一】逐帧处理过程")
    print(SUB)
    for now, in_port, src, dst in FRAMES:
        process(now, in_port, src, dst)
        dump_table(now)
        print()

    print(SUB)
    print(f"【二】老化（Aging）：默认 {AGING_TIME}s 未刷新则删除表项")
    print(SUB)
    print("查看各表项的年龄（当前时刻 T+5s）：")
    for mac in sorted(MAC_TABLE):
        port, ts = MAC_TABLE[mac]
        print("  " + pad(mac, 22) + pad(f"G0/{port}", 10) + f"年龄 {5 - ts:.0f}s")
    print()
    print(f"时间推进到 T+{AGING_TIME + 6}s，期间没有任何帧刷新：")
    removed = []
    for mac in list(MAC_TABLE):
        port, ts = MAC_TABLE[mac]
        # 最后刷新时刻为 ts；到 T+306s 时年龄 = 306 - ts
        if (AGING_TIME + 6) - ts > AGING_TIME:
            removed.append(mac)
            del MAC_TABLE[mac]
    for mac in removed:
        print(f"  {mac} 年龄超过 {AGING_TIME}s，表项被删除")
    dump_table(AGING_TIME + 6)
    print()
    print(f">>> 老化是必要的：如果主机换了端口而旧表项不失效，交换机会持续把帧发到错误端口。")
    print(f">>> 思科默认 300s，华为默认 300s；可通过 mac-address aging-time 调整。")
    print()

    print(SUB)
    print("【三】交换机转发动作小结")
    print(SUB)
    print(pad("动作", 14) + pad("触发条件", 34) + "行为")
    print(SUB)
    rows = [
        ("Learning 学习", "收到任何帧", "把「源 MAC + 入端口」写入 MAC 表"),
        ("Flooding 泛洪", "目的 MAC 未知 / 广播 / 组播", "从除入端口外所有端口发出"),
        ("Forwarding 转发", "目的 MAC 已知且与入端口不同", "只从对应端口发出"),
        ("Filtering 过滤", "目的 MAC 已知且就是入端口", "丢弃，不再转发"),
        ("Aging 老化", "表项超过 300s 未刷新", "删除表项"),
    ]
    for a, b, c in rows:
        print(pad(a, 14) + pad(b, 34) + c)
    print(SUB)
    print()

    print(SEP)
    print("小结")
    print(SEP)
    print("1. 交换机靠「学习源 MAC、查目的 MAC」建立转发表，无需人工配置即可自学习。")
    print("2. 未知单播必须泛洪，这是二层网络「先广播找路、再单播通信」的代价，也是环路风险来源。")
    print("3. 目的 MAC 与入端口相同时执行过滤，避免同端口回环浪费带宽。")
    print(f"4. 表项老化时间默认 {AGING_TIME}s，不老化会导致主机迁移后转发错误。")
    print()


if __name__ == "__main__":
    main()
