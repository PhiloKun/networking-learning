#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wi-Fi 漫游时间线分解：扫描 → 认证 → 关联 → 4 次握手 → 数据恢复，逐段累加。

运行: python3 roaming_timeline.py
"""
import sys

sys.dont_write_bytecode = True

# 语音场景的一向时延预算（ITU-T G.114 建议 < 150ms，VoWLAN 切换目标 < 50ms）
VOICE_BUDGET_MS = 50.0

# 每个阶段的 (名称, 乐观ms, 典型ms, 悲观ms, 说明)
SCENARIOS = {
    "传统漫游（Passive Scan 全信道 13 个）": [
        ("被动扫描：每信道驻留 100ms", 1300, 1300, 1300, "11b/g 共 13 信道都要听 Beacon"),
        ("802.11 开放认证（NULL+ACK）", 1, 2, 3, "2 帧交换"),
        ("关联请求 / 关联响应", 2, 4, 8, "AP 侧建 STA 表并回 Association ID"),
        ("4 次握手（EAPOL 4-Way）", 3, 6, 15, "派生 PTK，安装 CCMP 密钥"),
        ("数据通路恢复（首个上行帧）", 1, 3, 10, "DHCP/ARP 若跨子网还要重来"),
    ],
    "优化漫游（Active Scan + PMKSA 缓存）": [
        ("主动扫描：每信道 30ms × 13", 100, 390, 500, "Probe Request 直接问，不等 Beacon"),
        ("802.11 开放认证", 1, 2, 3, "同左"),
        ("关联请求 / 关联响应", 2, 4, 8, "同左"),
        ("4 次握手（命中 PMKSA 缓存）", 2, 4, 8, "省掉 802.1X/EAP，PMK 复用"),
        ("数据通路恢复", 1, 2, 5, "同左"),
    ],
    "802.11r 快速 BSS 切换（FT）": [
        ("邻居报告驱动的定向扫描", 5, 15, 40, "AP 提供邻居列表，只扫 1~2 个信道"),
        ("FT 认证（FTAA）", 1, 3, 6, "与关联并行，预派生 PTK"),
        ("FT 关联（FTAR）+ 密钥安装", 4, 10, 20, "重关联帧同时携带 RSN IE 完成密钥"),
        ("数据通路恢复", 1, 2, 4, "同左"),
    ],
    "企业级 802.1X（无缓存，最坏情况）": [
        ("被动扫描 13 信道", 1300, 1300, 1300, "同左"),
        ("802.11 开放认证 + 关联", 3, 6, 11, "两段合并"),
        ("EAP 完整认证（EAP-TLS）", 200, 600, 1200, "多次 RADIUS 往返 + 证书校验"),
        ("4 次握手", 3, 6, 15, "同左"),
        ("数据通路恢复", 1, 3, 10, "同左"),
    ],
}


def render(key: str) -> None:
    rows = SCENARIOS[key]
    lo = sum(r[1] for r in rows)
    typ = sum(r[2] for r in rows)
    hi = sum(r[3] for r in rows)
    print("-" * 88)
    print(f"场景：{key}")
    print("-" * 88)
    print(f"{'阶段':<34}{'乐观(ms)':>9}{'典型(ms)':>9}{'悲观(ms)':>9}  说明")
    print("-" * 88)
    acc = 0.0
    for name, a, b, c, note in rows:
        acc += b
        print(f"{name:<34}{a:>9}{b:>9}{c:>9}  {note}")
        if b >= 100:
            print(f"{'  └ 累计(典型)':<34}{'':>9}{acc:>9.0f}{'':>9}  ← 到这里已超 "
                  f"{VOICE_BUDGET_MS:.0f}ms 预算" if acc > VOICE_BUDGET_MS else "")
    print("-" * 88)
    verdict = "满足 50ms 预算" if typ <= VOICE_BUDGET_MS else "超出 50ms 预算"
    print(f"合计：乐观 {lo:.0f}ms / 典型 {typ:.0f}ms / 悲观 {hi:.0f}ms  →  {verdict}")
    print()


def main() -> int:
    print("=" * 88)
    print("Wi-Fi 漫游时间线分解（STA 从 AP1 切到同一 ESS 的 AP2，语音场景预算 50ms）")
    print("=" * 88)
    print()
    for key in SCENARIOS:
        render(key)

    print("=" * 88)
    print("优化建议（按收益排序，均针对「典型」列）")
    print("=" * 88)
    tips = [
        ("开 802.11k 邻居报告", "扫描从 13 信道缩到 1~2 个，省 300~1300ms", "交换机/AC 需支持 k"),
        ("开 802.11r 快速切换（FT）", "认证+关联合并，省 5~10ms，覆盖密钥预派生", "需 AP+客户端同时支持 r"),
        ("开 802.11v BSS 过渡管理", "由网络侧引导 STA 在信号尚好时切换", "需 AC 统一管理"),
        ("启用 OKC / PMKSA 缓存", "跳过完整 802.1X，企业网省 200~1200ms", "AP 间需共享 PMK 缓存"),
        ("同 VLAN / 同子网部署", "避免切 AP 后重跑 DHCP，省 100~2000ms", "否则应做三层漫游"),
        ("关闭低频段、5G 单频", "减少扫描信道数，2.4G 只 3 个信道", "覆盖会变差，需补点"),
        ("调小 Beacon 但保留 DTIM", "不缩短扫描时间，只影响省电", "对漫游无直接帮助，避免误信"),
    ]
    for i, (t, gain, cond) in enumerate(tips, 1):
        print(f"  {i}. {t}")
        print(f"     收益：{gain}；前提：{cond}")
    print()
    print(">>> 结论：传统被动扫描一个 1300ms 就吃掉 26 倍语音预算，必须开 11k/11r。")
    print(">>> 结论：802.11r 把典型切换压到约 30ms，才真正满足 50ms 语音要求。")
    print(">>> 结论：漫游失败最常见的原因不是无线侧，而是切 AP 后跨子网重跑 DHCP。")
    print()
    print("小结")
    print("  1. 漫游 = 扫描 + 认证 + 关联 + 密钥 + 数据恢复，五段各占一份时间。")
    print("  2. 扫描是大头，11k/11r 优化的核心就是把「盲扫全部信道」变成「定向扫 1~2 个」。")
    print("  3. 密钥阶段靠缓存（OKC/PMKSA）压时间，企业网没有缓存基本做不成语音漫游。")
    print("  4. 把同 ESS 的 AP 规划进同一 VLAN 或做三层漫游，能避免切换后重跑 DHCP 的秒级中断。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
