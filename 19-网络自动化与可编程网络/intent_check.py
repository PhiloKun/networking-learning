#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""声明式合规检查：用「意图规则」扫描设备配置文本，输出违规项与修复建议。

运行: python3 intent_check.py
"""
import re
import sys

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

# 待检查的示例配置（SW1，故意埋入多处违规）
CONFIG = """hostname SW1
!
enable password cisco123
!
interface GigabitEthernet0/1
 description Access-Port-A
 switchport mode access
 switchport access vlan 100
!
interface GigabitEthernet0/2
 description Access-Port-B
 switchport mode access
 switchport nonegotiate
!
interface GigabitEthernet0/3
 description Access-Port-C
 switchport mode access
 switchport access vlan 200
 switchport nonegotiate
!
interface Vlan10
 ip address 192.0.2.2 255.255.255.0
 ip ospf 1 area 0
!
interface Vlan20
 ip address 198.51.100.2 255.255.255.0
 ip ospf 1 area 0
 ip ospf authentication message-digest
!
router ospf 1
 network 192.0.2.0 0.0.0.255 area 0
!
line vty 0 4
 transport input telnet ssh
!
end
"""


def parse_blocks(text: str) -> list:
    """按 '!' 切分配置块；空行与 '!' 丢弃。"""
    blocks = []
    current = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.strip() == "!":
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def is_interface(block: list) -> bool:
    return bool(block) and block[0].startswith("interface ")


def iface_name(block: list) -> str:
    return block[0].split(None, 1)[1] if is_interface(block) else "(全局)"


def has(block: list, pattern: str) -> bool:
    return any(re.search(pattern, line) for line in block)


# ---------- 意图规则 ----------
def rule_access_vlan(blocks: list) -> list:
    out = []
    for b in blocks:
        if is_interface(b) and has(b, r"^\s*switchport mode access$"):
            if not has(b, r"^\s*switchport access vlan \d+$"):
                out.append(("高", iface_name(b),
                            "接入口已设为 Access 模式，但未显式划分 VLAN",
                            "补充: switchport access vlan <VID>"))
    return out


def rule_dtp_off(blocks: list) -> list:
    out = []
    for b in blocks:
        if is_interface(b) and has(b, r"^\s*switchport mode access$"):
            if not has(b, r"^\s*switchport nonegotiate$"):
                out.append(("高", iface_name(b),
                            "接入口未关闭 DTP，可能被协商成 Trunk（VLAN Hopping 风险）",
                            "补充: switchport nonegotiate"))
    return out


def rule_ospf_auth(blocks: list) -> list:
    area_auth = any(has(b, r"^\s*area \d+ authentication")
                    for b in blocks if b[0].startswith("router ospf"))
    out = []
    if area_auth:
        return out
    for b in blocks:
        if is_interface(b) and has(b, r"^\s*ip ospf \d+ area \d+"):
            if not has(b, r"^\s*ip ospf authentication"):
                out.append(("中", iface_name(b),
                            "运行 OSPF 的接口未配置认证，存在伪造 Hello 建立邻居的风险",
                            "补充: ip ospf authentication message-digest + key"))
    return out


def rule_enable_secret(blocks: list) -> list:
    out = []
    glob = [b for b in blocks if b[0].startswith("enable ")]
    if any(has(b, r"^enable password ") for b in glob):
        out.append(("高", "(全局)",
                    "使用 enable password，密码在配置中以弱保护存放",
                    "改为: enable secret <强口令>（或 aaa 认证）"))
    if not any(has(b, r"^enable secret ") for b in glob):
        out.append(("中", "(全局)",
                    "未配置 enable secret，进入特权模式缺少强口令保护",
                    "补充: enable secret <强口令>"))
    return out


def rule_http_server(blocks: list) -> list:
    if any(has(b, r"^no ip http server$") for b in blocks):
        return []
    return [("中", "(全局)",
             "未显式关闭 HTTP 管理服务，可能暴露明文管理面",
             "补充: no ip http server（只保留 no ip http secure-server 之外的 ssh）")]


def rule_vty_ssh(blocks: list) -> list:
    out = []
    for b in blocks:
        if b[0].startswith("line vty"):
            for line in b:
                if re.search(r"^\s*transport input\b", line):
                    if "telnet" in line:
                        out.append(("高", "line vty",
                                    f"管理登录允许明文 Telnet（{line.strip()}）",
                                    "改为: transport input ssh"))
    return out


RULES = [
    ("R1 接入口必须划分 VLAN", rule_access_vlan),
    ("R2 接入口必须关闭 DTP", rule_dtp_off),
    ("R3 OSPF 接口必须有认证", rule_ospf_auth),
    ("R4 特权口令必须用 secret", rule_enable_secret),
    ("R5 必须关闭 HTTP 管理", rule_http_server),
    ("R6 vty 只允许 SSH", rule_vty_ssh),
]


def main() -> None:
    print(SEP)
    print("声明式合规检查：意图规则扫描配置文本")
    print(SEP)

    blocks = parse_blocks(CONFIG)
    print(f"解析到 {len(blocks)} 个配置块（按 '!' 切分），其中接口块 "
          f"{sum(1 for b in blocks if is_interface(b))} 个")
    print()
    print(SUB)
    print("【一】规则库")
    print(SUB)
    for name, _fn in RULES:
        print(f"  - {name}")
    print("  规则是「意图」声明：与具体设备型号无关，只约束最终状态。")

    print()
    print(SUB)
    print("【二】逐条规则检查结果")
    print(SUB)
    all_violations = []
    for name, fn in RULES:
        found = fn(blocks)
        status = "通过" if not found else f"违规 {len(found)} 处"
        print(f"  [{status}] {name}")
        for severity, target, msg, fix in found:
            all_violations.append((name, severity, target, msg, fix))
            print(f"      ! ({severity}) {target}: {msg}")
    print(SUB)
    print(f"封面统计：违规总数 = {len(all_violations)}")

    print()
    print(SUB)
    print("【三】违规明细与修复建议")
    print(SUB)
    print(f"{'序号':<5}{'级别':<6}{'对象':<24}{'问题':<40}{'修复建议'}")
    print(SUB)
    for i, (_rule, severity, target, msg, fix) in enumerate(all_violations, 1):
        show_msg = msg if len(msg) <= 38 else msg[:35] + "..."
        print(f"{i:<5}{severity:<6}{target:<24}{show_msg:<40}{fix}")
    print(SUB)

    high = sum(1 for v in all_violations if v[1] == "高")
    mid = sum(1 for v in all_violations if v[1] == "中")
    print(f">>> 结论：共 {len(all_violations)} 处违规（高危 {high}、中危 {mid}）；"
          f"高危项必须先修复再上线")

    print()
    print(SUB)
    print("【四】合规覆盖率")
    print(SUB)
    total_rules = len(RULES)
    passed = sum(1 for _n, fn in RULES if not fn(blocks))
    print(f"{'规则总数':<12}{'通过':<8}{'违规':<8}{'覆盖率'}")
    print(SUB)
    print(f"{total_rules:<12}{passed:<8}{total_rules - passed:<8}"
          f"{passed / total_rules * 100:.1f}%")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. 把「意图」写成规则（必须划分 VLAN、必须关 DTP、必须认证）就能自动化合规检查。")
    print("2. 规则扫描的是最终配置文本，不依赖设备型号，天然适合多厂商统一治理。")
    print("3. 高危违规（明文 Telnet、未关 DTP、弱口令）应做 CI 门禁：不通过不许下发。")
    print("4. 合规检查 + 修复建议 = 配置漂移可自动发现、可自动纠正。")
    print()


if __name__ == "__main__":
    main()
