#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置版本比对：unified diff 风格输出 + 按接口/路由/ACL/安全分类 + 高危变更标记。

运行: python3 config_diff.py
"""
import difflib
import re
import sys

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

# 变更前（设备 current 配置）
CONFIG_BEFORE = """hostname R1
!
interface GigabitEthernet0/0
 description Uplink-to-R2
 ip address 203.0.113.1 255.255.255.252
 mtu 1500
!
interface GigabitEthernet0/1
 description User-Port
 switchport mode access
 switchport access vlan 100
!
ip route 0.0.0.0 0.0.0.0 203.0.113.2
!
access-list 100 permit tcp 192.0.2.0 0.0.0.255 host 198.51.100.10 eq 443
access-list 100 permit icmp 192.0.2.0 0.0.0.255 any
!
line vty 0 4
 transport input ssh
 login local
!
end
"""

# 变更后（新下发的配置）
CONFIG_AFTER = """hostname R1
!
interface GigabitEthernet0/0
 description Uplink-to-R2
 ip address 203.0.113.1 255.255.255.252
 mtu 1400
!
interface GigabitEthernet0/1
 description User-Port
 switchport mode access
 switchport access vlan 200
 shutdown
!
ip route 0.0.0.0 0.0.0.0 203.0.113.6
ip route 198.51.100.0 255.255.255.0 203.0.113.2
!
access-list 100 permit tcp 192.0.2.0 0.0.0.255 host 198.51.100.10 eq 443
!
line vty 0 4
 transport input telnet
 login local
!
end
"""

SECTION_START = {
    "interface": re.compile(r"^interface\s+"),
    "route": re.compile(r"^(ip|ipv6)\s+route\s+"),
    "acl": re.compile(r"^access-list\s+|^ip\s+access-list\s+"),
    "security": re.compile(r"^\s*(line\s+|aaa\s+|username\s+|enable\s+|crypto\s+|"
                           r"transport\s+|login\s+|no\s+ip\s+http|service\s+password)"),
}
# 接口小节内的子行（有缩进），需要按上下文归到 interface
IFACE_SUB = re.compile(r"^\s+(description|ip\s+address|mtu|switchport|shutdown|no\s+shutdown)\b")

HIGH_RISK = [
    (re.compile(r"^\s*shutdown\s*$"), "接口将被关闭，业务直接中断"),
    (re.compile(r"^\s*transport input telnet"), "明文登录，安全降级"),
    (re.compile(r"^access-list .*\bdeny\b"), "新增/变更 ACL 拒绝规则，可能误杀业务"),
    (re.compile(r"^\s*no\s+"), "删除类操作，可能移除关键配置"),
    (re.compile(r"^ip\s+route\s+0\.0\.0\.0"), "默认路由变更，影响全局可达性"),
    (re.compile(r"^\s*switchport access vlan"), "接入 VLAN 变更，可能造成跨网段不通"),
]


def classify(line: str) -> str:
    """纯内容分类：接口 / 路由 / ACL / 安全 / 其它。"""
    if IFACE_SUB.match(line):
        return "interface"
    for name, pat in SECTION_START.items():
        if pat.search(line):
            return name
    return "其它"


def risk_of(line: str) -> str:
    for pat, desc in HIGH_RISK:
        if pat.search(line):
            return desc
    return ""


def main() -> None:
    before = CONFIG_BEFORE.splitlines()
    after = CONFIG_AFTER.splitlines()

    print(SEP)
    print("配置版本比对：unified diff + 分类 + 高危变更标记")
    print(SEP)
    print(f"变更前行数 = {len(before)}，变更后行数 = {len(after)}")

    print()
    print(SUB)
    print("【一】unified diff（变更前 -> 变更后）")
    print(SUB)
    diff = list(difflib.unified_diff(before, after,
                                     fromfile="R1-running(old)",
                                     tofile="R1-running(new)", lineterm="", n=1))
    for line in diff:
        print("  " + line)

    print()
    print(SUB)
    print("【二】按小节分类的变更清单")
    print(SUB)
    changes = []
    for line in diff:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line[:1] not in ("+", "-"):
            continue
        content = line[1:]
        changes.append((line[0], content, classify(content), risk_of(content)))

    print(f"{'类别':<10}{'动作':<8}{'内容':<44}{'风险'}")
    print(SUB)
    for sign, content, section, rk in changes:
        action = "新增" if sign == "+" else "删除"
        show = content if len(content) <= 42 else content[:39] + "..."
        risk = ("高危: " + rk) if rk else "-"
        print(f"{section:<10}{action:<8}{show:<44}{risk}")

    print()
    print(SUB)
    print("【三】按小节统计变更数量")
    print(SUB)
    counter = {}
    for _s, _c, section, _r in changes:
        counter[section] = counter.get(section, 0) + 1
    print(f"{'小节':<12}{'变更行数'}")
    print(SUB)
    for section in sorted(counter, key=lambda k: -counter[k]):
        print(f"{section:<12}{counter[section]}")
    print(SUB)
    print(f"变更总行数 = {len(changes)}")

    print()
    print(SUB)
    print("【四】高危变更汇总（必须人工复核）")
    print(SUB)
    risky = [(c, r) for _s, c, _k, r in changes if r]
    if not risky:
        print("  无高危变更")
    for content, rk in risky:
        print(f"  ! {content}")
        print(f"    影响: {rk}")
    print(SUB)
    print(f">>> 结论：本次变更共 {len(changes)} 行，其中高危 {len(risky)} 行；"
          f"高危变更必须先走审批与回滚预案再下发")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. unified diff 用 + / - 标记新增与删除，配合上下文行就能完整还原变更意图。")
    print("2. 自动化变更必须先分类（接口/路由/ACL/安全），再按类别套用不同的审批等级。")
    print("3. shutdown、VLAN 变更、默认路由变更、ACL deny 新增属于高危项，必须人工复核。")
    print("4. 金标准模板 + 差异审计 = 配置漂移可发现、变更可回滚、审计可追溯。")
    print()


if __name__ == "__main__":
    main()
