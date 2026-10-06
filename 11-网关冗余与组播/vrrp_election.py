#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VRRP Master/Backup 选举、抢占、认证失败与虚拟 MAC 生成演示。

运行: python3 vrrp_election.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


def ip_num(ip):
    return tuple(int(x) for x in ip.split("."))


VRID = 1
VIRTUAL_IP = "203.0.113.254"


def virtual_mac(vrid):
    """VRRP 虚拟 MAC：固定前缀 00-00-5E-00-01 + VRID（1 字节）。"""
    return f"00:00:5E:00:01:{vrid:02X}"


# (名字, 优先级, 接口物理 IP, 是否 VIP 真正拥有者, 认证口令, 是否开启抢占)
def member(name, pri, ip, owner=False, auth="cisco", preempt=True):
    return dict(name=name, pri=pri, ip=ip, ipn=ip_num(ip), owner=owner,
                auth=auth, preempt=preempt)


INITIAL = [
    member("R1", 200, "203.0.113.1"),
    member("R2", 100, "203.0.113.2"),
    member("R3", 150, "203.0.113.3"),
]


def elect(members, note_auth=False):
    """选举：先看是否为 IP 拥有者(优先级 255)，再比优先级，平局比接口 IP 大者。"""
    valid = [m for m in members if m["pri"] > 0]
    if not valid:
        return None, None
    owners = [m for m in valid if m["owner"]]
    if owners:
        master = owners[0]
    else:
        master = sorted(valid, key=lambda m: (m["pri"], m["ipn"]), reverse=True)[0]
    backups = [m for m in valid if m is not master]
    backups.sort(key=lambda m: (m["pri"], m["ipn"]), reverse=True)
    backup = backups[0] if backups else None
    return master, backup


def skew_time(pri):
    """Skew_Time = (256 - Priority) / 256 秒。"""
    return (256 - pri) / 256.0


def down_interval(pri, adv=1.0):
    """Master_Down_Interval = 3 × Advertisement_Interval + Skew_Time。"""
    return 3 * adv + skew_time(pri)


def show(title, members, master, backup, extra=()):
    print("-" * 92)
    print(title)
    print(pad("路由器", 10) + pad("优先级", 10) + pad("接口 IP", 18)
          + pad("角色", 12) + pad("Skew时间", 12) + "Master_Down_Interval")
    for m in members:
        if master and m["name"] == master["name"]:
            role = "Master"
        elif backup and m["name"] == backup["name"]:
            role = "Backup"
        elif m["pri"] == 0:
            role = "不参选(0)"
        else:
            role = "Backup"
        st = skew_time(m["pri"]) if m["pri"] > 0 else 0.0
        di = down_interval(m["pri"]) if m["pri"] > 0 else 0.0
        print(pad(m["name"], 10) + pad(str(m["pri"]), 10) + pad(m["ip"], 18)
              + pad(role, 12) + pad(f"{st:.3f}s", 12) + f"{di:.3f}s")
    for e in extra:
        print("  " + e)


def main():
    print()
    print("VRRP 选举与虚拟 MAC 演示 · VRID = 1，虚拟 IP = " + VIRTUAL_IP)
    print()

    print("=" * 92)
    print("一、虚拟 MAC 的生成规则")
    print("-" * 92)
    mac = virtual_mac(VRID)
    print(f"虚拟 MAC = 固定前缀 00-00-5E-00-01 + VRID(1 字节) = {mac}")
    print("  第 1 字节 00、第 2 字节 00、第 3 字节 5E → IANA 分配的 VRRP 组织唯一标识")
    print("  第 4 字节 00、第 5 字节 01 → 标识这是 VRRP 协议")
    print(f"  第 6 字节 {VRID:02X} → 就是 VRID，范围 1~255")
    print("-" * 92)
    print("主机侧的 ARP 表现：")
    print("  PC1 执行 arp -a 会看到 " + VIRTUAL_IP
          + f" 对应的 MAC 是 {mac}")
    print("  这个 MAC 不会随 Master 切换而改变 —— 这是 VRRP 对主机「透明」的关键。")
    print(">>> 结论：Master 切换时主机完全无感，因为网关 IP 与网关 MAC 都没变，")
    print("    变化的只是「哪台物理设备在回应这个 MAC」。")
    print()

    print("=" * 92)
    print("二、初始选举：比优先级，平局比接口 IP（大者胜）")
    master, backup = elect(INITIAL)
    show("三台路由器同时启动", INITIAL, master, backup, [
        f"R1 优先级 200 最高 → 当选 Master；R3(150) 次之 → 当选 Backup。",
        f"Master 每 1 秒向 224.0.0.18 发一次 Advertisement"
        f"（目的 MAC 01:00:5E:00:00:12）。",
    ])
    print(f">>> 选举结果：Master = {master['name']}，Backup = {backup['name']}")
    print()

    print("=" * 92)
    print("三、Master 失效：Backup 接任")
    members2 = [m for m in INITIAL if m["name"] != "R1"]
    m2, b2 = elect(members2)
    show("R1 掉线（Backup 在 Master_Down_Interval 后接管）", members2, m2, b2, [
        f"R3 优先级 150 > R2 的 100 → R3 接任 Master。",
        f"R3 的 Master_Down_Interval = 3 × 1s + Skew"
        f"((256-150)/256={skew_time(150):.3f}s) = {down_interval(150):.3f}s。",
        "R3 接管后立刻发免费 ARP，把虚拟 IP 的 MAC 更新为 " + virtual_mac(VRID) + "。",
    ])
    print(f">>> 选举结果：Master = {m2['name']}，Backup = {b2['name']}")
    print()

    print("=" * 92)
    print("四、原 Master 恢复：抢占（Preempt）行为对比")
    members3 = INITIAL
    m3, b3 = elect(members3)
    show("场景 A：R1 恢复且开启抢占（默认）", members3, m3, b3, [
        "R1 发 Advertisement 后，R3 发现对端优先级 200 > 自己的 150，主动让位。",
        f"最终 Master 回到 R1 —— 抢占让「规划好的主」重新成为主。",
    ])
    r1_nopre = member("R1", 200, "203.0.113.1", preempt=False)
    members4 = [r1_nopre, INITIAL[1], INITIAL[2]]
    master4 = INITIAL[2]          # R3 继续当 Master
    backup4 = INITIAL[1]
    show("场景 B：R1 恢复但关闭抢占（no preempt）", members4, master4, backup4, [
        "R1 优先级仍是 200，但配置了 no preempt，不再抢夺 Master 位置。",
        "R3 继续担任 Master，直到它自己失效 —— 减少一次无谓的主备切换。",
    ])
    print(">>> 结论：抢占能保证「规划中的主」回到主位；关闭抢占能避免链路抖动引起的反复切换。")
    print()

    print("=" * 92)
    print("五、认证失败：口令不一致会导致什么")
    bad = [member("R1", 200, "203.0.113.1", auth="cisco"),
           member("R2", 100, "203.0.113.2", auth="HUAWEI"),
           member("R3", 150, "203.0.113.3", auth="HUAWEI")]
    print("R1 用口令 cisco，R2/R3 用口令 HUAWEI：")
    print("  1) R2/R3 收到 R1 的 Advertisement，口令校验失败 → 直接丢弃，不参与选举。")
    print("  2) R1 收不到 R2/R3 的合法 Advertisement → 认为没有竞争者，独占 Master。")
    print("  3) 若 R1 也丢弃 R2/R3 的报文，R2/R3 将在 Master_Down_Interval 后各自认为")
    print("     「没有 Master」并尝试竞选 → 出现双 Master，网关 MAC 冲突、主机流量黑洞。")
    print("-" * 92)
    print(">>> 结论：VRRP 认证不一致不会立刻报错，而是表现为「莫名双主」或「主备争抢」，")
    print("    排障第一步就是两端核对认证配置与 VRID。")
    print("    注意：RFC 5798（VRRPv3）已取消认证字段，改用 IPsec 保护，")
    print("    因此「认证」只在 VRRPv2 设备上才有；跨版本混用要注意兼容性。")
    print()

    print("=" * 92)
    print("六、优先级 0 与 255 的特殊含义")
    print("-" * 92)
    print(pad("优先级", 12) + "含义")
    print(pad("0", 12) + "不参与选举；Master 主动发优先级 0 的 Advertisement 表示「我要退位」")
    print(pad("1~254", 12) + "正常参与选举，数值越大越优先，默认 100")
    print(pad("255", 12) + "IP 地址拥有者（Address Owner）：该路由器接口 IP 就是虚拟 IP，永远是 Master")
    print("-" * 92)
    print(">>> 结论：优先级 255 是「保留给 VIP 真正拥有者」的，配置前先确认 VIP 是否落在某台设备的接口网段上。")
    print()
    print("小结：")
    print("1. VRRP 选举顺序：IP 拥有者(255) > 优先级大者 > 接口 IP 大者；优先级 0 不参选。")
    print("2. 虚拟 MAC 固定为 00:00:5E:00:01:{VRID}，与物理设备无关，所以主备切换对主机透明。")
    print("3. Master 每秒发 Advertisement（224.0.0.18）；Backup 在 3×Advertisement + Skew 后接管，")
    print("   Skew = (256-优先级)/256 秒，优先级越低等待越久，避免低优先级设备抢先接管。")
    print()


if __name__ == "__main__":
    main()
