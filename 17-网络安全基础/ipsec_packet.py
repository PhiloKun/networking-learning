#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPsec ESP 报文封装结构解剖：传输模式 vs 隧道模式的字节开销逐项计算。

运行: python3 ipsec_packet.py
"""
import sys
from dataclasses import dataclass

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

BLOCK = 16          # AES 分组长度 16 字节（CBC 模式加密长度必须对齐到 16）
IV_LEN = 16         # AES-CBC 初始向量
ICV_LEN = 12        # HMAC-SHA1-96 完整性校验值（截断到 96 位 = 12 字节）
ESP_HDR = 8         # SPI(4) + 序号(4)
ESP_TRAILER = 2     # 填充长度(1) + 下一头部(1)


@dataclass
class EspLayout:
    mode: str
    outer_ip: int
    esp_hdr: int
    iv: int
    payload_in: int        # 进入加密的数据长度
    padding: int
    trailer: int
    icv: int

    def total(self) -> int:
        return (self.outer_ip + self.esp_hdr + self.iv +
                self.payload_in + self.padding + self.trailer + self.icv)

    def overhead(self) -> int:
        """相对明文 IP 分组的额外开销（不含被封装的原 IP 头本身）。"""
        return self.total() - self.payload_in


def align_up(n: int, block: int) -> int:
    return ((n + block - 1) // block) * block


def build_layout(mode: str, inner_packet_len: int, ip_hdr_len: int = 20) -> EspLayout:
    """
    计算 ESP 封装布局。
    mode = transport：加密的是传输层段（原 IP 头不加密，明文放在最前）
    mode = tunnel   ：加密的是整个原 IP 分组，前面再加一个新 IP 头
    """
    if mode == "transport":
        payload_in = inner_packet_len - ip_hdr_len     # 传输层段
        outer_ip = 0                                   # 复用原 IP 头
    else:
        payload_in = inner_packet_len                  # 整个原分组
        outer_ip = 20                                  # 新增隧道外层 IP 头
    # 加密区 = 明文 + 填充 + 尾部(1+1)，必须对齐到 BLOCK
    enc_target = align_up(payload_in + ESP_TRAILER, BLOCK)
    padding = enc_target - payload_in - ESP_TRAILER
    return EspLayout(mode, outer_ip, ESP_HDR, IV_LEN, payload_in,
                     padding, ESP_TRAILER, ICV_LEN)


def print_layout(layout: EspLayout, inner_packet_len: int) -> None:
    print(f"{'字段':<26}{'长度(B)':<10}{'说明'}")
    print(SUB)
    rows = [
        ("外层新 IP 头", layout.outer_ip,
         "仅隧道模式有；传输模式复用原 IP 头（不加）"),
        ("ESP 头 · SPI", 4, "安全参数索引，标识用哪一组 SA（隧道两端各自独立取值）"),
        ("ESP 头 · 序号", 4, "抗重放，每发一包 +1，接收端维护滑动窗口"),
        ("初始向量 IV", layout.iv, "AES-CBC 随机 IV，接收端解密的起点"),
        ("加密载荷", layout.payload_in,
         "传输模式=传输层段；隧道模式=整个原 IP 分组（含原 IP 头）"),
        ("填充 Padding", layout.padding, f"补齐到 {BLOCK} 字节整数倍（0 ~ {BLOCK - 1}）"),
        ("ESP 尾 · 填充长度", 1, "告诉接收端去掉多少填充字节"),
        ("ESP 尾 · 下一头部", 1, "指出被加密载荷是 IP(4) / TCP(6) / UDP(17)"),
        ("ICV 完整性校验", layout.icv, "HMAC-SHA1-96，覆盖 ESP 头到载荷末端"),
    ]
    for name, ln, desc in rows:
        shown = ln if ln else "—"
        print(f"{name:<26}{str(shown):<10}{desc}")
    print(SUB)
    total = layout.total()
    print(f"封装后总长度 = {total} B（明文原分组 {inner_packet_len} B）")
    overhead_total = total - inner_packet_len
    print(f">>> 结论：{layout.mode} 模式总开销 = {total} - {inner_packet_len} = "
          f"{overhead_total} B，其中固定开销 {layout.esp_hdr + layout.iv + layout.trailer + layout.icv} B"
          f" + 填充 {layout.padding} B + 新 IP 头 {layout.outer_ip} B")
    print(f">>> 相比明文，封装膨胀率 = {overhead_total} / {inner_packet_len} = "
          f"{overhead_total / inner_packet_len * 100:.1f}%")


def fmt_packet(inner_packet_len: int) -> None:
    print(SUB)
    print(f"示例内层分组：IP 头 20 B + UDP 头 8 B + 数据 {inner_packet_len - 28} B "
          f"= 共 {inner_packet_len} B")
    print(SUB)


def main() -> None:
    print(SEP)
    print("IPsec ESP 封装结构解剖（加密套件 AES-128-CBC + HMAC-SHA1-96）")
    print(SEP)
    print("AH 只做完整性校验、不加密，且无法穿越 NAT（校验和覆盖 IP 头中的地址）；")
    print("ESP 既加密又校验，还能被 NAT-T 封装进 UDP 4500，因此生产环境 99% 用 ESP。")
    inner = 128
    fmt_packet(inner)

    print()
    print("【A】传输模式（Transport Mode）")
    print("适用：主机到主机（如 PC1 与服务器直接建 IPsec 隧道），保护传输层段，路由开销小")
    print(SUB)
    tr = build_layout("transport", inner)
    print_layout(tr, inner)
    print("  报文外观：[原 IP 头][ESP 头][IV][加密(段+填充+尾)][ICV]")

    print()
    print("【B】隧道模式（Tunnel Mode）")
    print("适用：网关到网关（如 R1 与 R2 建站点到站点隧道），保护整个原分组，可隐藏内网地址")
    print(SUB)
    tu = build_layout("tunnel", inner)
    print_layout(tu, inner)
    print("  报文外观：[新 IP 头][ESP 头][IV][加密(原 IP 分组+填充+尾)][ICV]")

    print()
    print(SUB)
    print("【C】两种模式对照")
    print(SUB)
    print(f"{'对比项':<20}{'传输模式':<30}{'隧道模式'}")
    print(SUB)
    compare = [
        ("外层 IP 头", "复用原 IP 头（不新增）", "新增 20 B（源/目的为网关地址）"),
        ("被加密内容", "仅传输层段", "整个原 IP 分组（含原 IP 头）"),
        ("内网地址可见性", "原 IP 头明文，可见", "原 IP 头被加密，不可见"),
        ("总开销", f"{tr.overhead()} B", f"{tu.overhead()} B"),
        ("典型场景", "主机到主机", "站点到站点 / 远程接入"),
    ]
    for a, b, c in compare:
        print(f"{a:<20}{b:<30}{c}")

    print()
    print("【D】常见 MTU 影响")
    print(SUB)
    for mode, layout in (("传输模式", tr), ("隧道模式", tu)):
        print(f"  {mode}：物理 MTU 1500 时，留给内层明文的净空 = "
              f"1500 - {layout.total() - layout.payload_in} = "
              f"{1500 - (layout.total() - layout.payload_in)} B")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. ESP 结构固定为：ESP 头(8) + IV(16) + 加密载荷 + 填充 + 尾(2) + ICV(12)，填充对齐 16 字节分组。")
    print("2. 传输模式不新增外层 IP 头、开销小但内网地址明文可见；隧道模式加 20 B 外层头、隐藏内网地址。")
    print(f"3. 本例传输模式开销 {tr.overhead()} B、隧道模式开销 {tu.overhead()} B，隧道模式多出外层 IP 头。")
    print("4. AH 不能穿 NAT，ESP 才是生产主力；两者可叠加但极少这么用。")
    print()


if __name__ == "__main__":
    main()
