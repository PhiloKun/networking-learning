#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟 ARP 请求广播 / 单播应答 / 缓存老化 / 免费 ARP，并说明 ARP 欺骗与 DAI 防御。

运行: python3 arp_sim.py
"""
import sys

sys.dont_write_bytecode = True

# 教学拓扑：一个广播域，192.0.2.0/24
HOSTS = [
    ("PC1", "192.0.2.1", "02:00:00:00:00:0A"),
    ("PC2", "192.0.2.2", "02:00:00:00:00:0B"),
    ("PC3", "192.0.2.3", "02:00:00:00:00:0C"),
    ("GW", "192.0.2.254", "02:00:00:00:00:FE"),
]
BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"
UNKNOWN_MAC = "00:00:00:00:00:00"
ARP_AGING_S = 300          # 教学用老化时间（Linux neigh 默认量级；Cisco 默认 14400s）


def idx_by_name(name: str) -> int:
    return next(i for i, h in enumerate(HOSTS) if h[0] == name)


def arp_request(src_name: str, target_ip: str) -> dict:
    s = HOSTS[idx_by_name(src_name)]
    return {
        "op": "REQUEST",
        "eth_dst": BROADCAST_MAC,
        "eth_src": s[2],
        "sender_mac": s[2],
        "sender_ip": s[1],
        "target_mac": UNKNOWN_MAC,
        "target_ip": target_ip,
    }


def arp_reply(src_name: str, target_name: str) -> dict:
    s = HOSTS[idx_by_name(src_name)]
    t = HOSTS[idx_by_name(target_name)]
    return {
        "op": "REPLY",
        "eth_dst": t[2],           # 应答是单播，不回广播
        "eth_src": s[2],
        "sender_mac": s[2],
        "sender_ip": s[1],
        "target_mac": t[2],
        "target_ip": t[1],
    }


def show_frame(f: dict) -> None:
    print(f"  [{f['op']}] 以太网 目的={f['eth_dst']} 源={f['eth_src']}")
    print(f"          ARP   sender_mac={f['sender_mac']} sender_ip={f['sender_ip']}")
    print(f"                target_mac={f['target_mac']} target_ip={f['target_ip']}")
    if f["eth_dst"] == BROADCAST_MAC:
        print("                → 广播域内所有主机都会收到并交给 ARP 模块处理")


def main() -> int:
    print("=" * 80)
    print("ARP 工作机制模拟（广播域：192.0.2.0/24，教学模拟，未发起真实流量）")
    print("=" * 80)
    for name, ip, mac in HOSTS:
        print(f"  {name:<4} {ip:<14} {mac}")
    print("-" * 80)

    cache = {}   # (主机名, IP) -> (MAC, 剩余寿命)
    print("场景 1：PC1 首次 ping 192.0.2.2（ARP 缓存为空）")
    print("-" * 80)
    print("  step0：PC1 查本机 ARP 缓存 → 未命中，需要解析 192.0.2.2 的 MAC")
    print("  step1：PC1 广播 ARP Request")
    show_frame(arp_request("PC1", "192.0.2.2"))
    print("  step2：所有主机都收到广播帧，逐个比对 target_ip 是否等于自己：")
    for name, ip, mac in HOSTS:
        if name == "PC1":
            continue
        if ip == "192.0.2.2":
            print(f"          {name}: target_ip 命中自己 → 准备单播应答")
        else:
            print(f"          {name}: 不是问我，丢弃；但会顺手学走 sender 的映射（欺骗的温床）")
    print("  step3：PC2 单播回 ARP Reply")
    show_frame(arp_reply("PC2", "PC1"))
    cache[("PC1", "192.0.2.2")] = ["02:00:00:00:00:0B", ARP_AGING_S]
    cache[("PC2", "192.0.2.1")] = ["02:00:00:00:00:0A", ARP_AGING_S]
    cache[("PC3", "192.0.2.1")] = ["02:00:00:00:00:0A", ARP_AGING_S]
    print("  step4：PC1 学到映射，开始发 ICMP Echo Request")
    print()
    print("  解析完成后的各主机 ARP 缓存：")
    print(f"    {'主机':<6}{'IP':<14}{'MAC':<20}{'剩余寿命(s)'}")
    for (h, ip), (mac, life) in sorted(cache.items()):
        print(f"    {h:<6}{ip:<14}{mac:<20}{life}")
    print()
    print("  >>> 结论：ARP Request 广播、ARP Reply 单播。一次广播让所有主机都「被动学习」，")
    print("            这正是 ARP 欺骗能成功的原因——没人验证应答的真伪。")
    print()

    print("场景 2：缓存老化（老化时间模拟为 300s，每 100s 抽样一次）")
    print("-" * 80)
    for t in range(0, 401, 100):
        state = []
        for k, v in cache.items():
            life = ARP_AGING_S - t
            if life > 0:
                state.append(f"{k[0]}→{k[1]} (剩 {life}s)")
        print(f"  t={t:>3}s : " + ("；".join(state) if state else "全部表项已过期"))
    print("  t=400s : PC1 的 192.0.2.2 表项已过期，下次通信要重新广播 ARP Request")
    print("  >>> 结论：老化让地址变化能被重新学习，但老化窗口内被投毒的记录会一直生效。")
    print()

    print("场景 3：免费 ARP（Gratuitous ARP）")
    print("-" * 80)
    print("  GW 更换网卡 / VRRP 主备切换后，主动广播「我的 IP 对应这个新 MAC」：")
    print(f"  ARP Request: sender_ip=target_ip=192.0.2.254, sender_mac=02:00:00:00:00:FE, "
          f"target_mac={UNKNOWN_MAC}")
    print("  全网主机收到后更新缓存，无需等待老化。两个用途：")
    print("    ① 探测 IP 冲突：若有人应答「我也是 192.0.2.254」则说明地址冲突；")
    print("    ② 快速刷新全网缓存：网卡更换、VRRP/HSRP 切换、容器漂移后立即生效。")
    print()
    print("=" * 80)
    print("ARP 欺骗的形成与防御（5 行说明，纯模拟，不攻击任何真实主机）")
    print("=" * 80)
    print("  1. 攻击者持续发送伪造的免费 ARP，声称「网关 IP 192.0.2.254 的 MAC 是我的」，")
    print("     主机无条件更新缓存，于是所有出网流量先发给攻击者，形成中间人。")
    print("  2. 抓包特征：同一 IP 的 MAC 映射短时间内反复变化；出现大量 ARP 广播且 sender_mac 异常。")
    print("  3. 防御第一层：动态 ARP 检测（Dynamic ARP Inspection, DAI）——交换机用 DHCP Snooping")
    print("     建立的 IP↔MAC↔端口 绑定表校验每个 ARP 报文，不匹配的直接丢弃。")
    print("  4. 防御第二层：DHCP Snooping（建绑定表）+ IP Source Guard（校验源 IP）")
    print("     + 端口安全（限制 MAC 数），三者共用同一张绑定表。")
    print("  5. 防御第三层：关键主机静态 ARP 绑定、网关侧对下联口限速 ARP、跨网段用 VLAN 隔离缩小广播域。")
    print()
    print("小结")
    print("  1. ARP 用「广播问、单播答」完成 IP→MAC 解析，无认证机制是它天生的缺陷。")
    print("  2. 缓存老化（教学 300s，Cisco 默认 14400s）保证地址变化可被重新学习。")
    print("  3. 免费 ARP 既用于检测 IP 冲突，也用于 VRRP/换卡后的快速缓存刷新。")
    print("  4. 防 ARP 欺骗靠 DAI + DHCP Snooping + IP Source Guard 三件套，缺一不可。")
    return 0

if __name__ == "__main__":
    sys.exit(main())
