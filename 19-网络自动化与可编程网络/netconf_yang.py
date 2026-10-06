#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 ElementTree 构造 NETCONF get-config 请求，并解析示例 config 响应。

运行: python3 netconf_yang.py
"""
import sys
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import QName, SubElement

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

NC_NS = "urn:ietf:params:xml:ns:netconf:base:1.0"
IF_NS = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
IP_NS = "urn:ietf:params:xml:ns:yang:ietf-ip"

ET.register_namespace("", NC_NS)
ET.register_namespace("if", IF_NS)
ET.register_namespace("ip", IP_NS)

# 一段示例「设备回包」，模拟对上面 get-config 的 rpc-reply
SAMPLE_REPLY = """<?xml version="1.0" encoding="UTF-8"?>
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
  <data>
    <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
      <interface>
        <name>GigabitEthernet0/0</name>
        <description>Uplink-to-R1</description>
        <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
        <enabled>true</enabled>
        <mtu>1500</mtu>
        <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip">
          <address>
            <ip>192.0.2.1</ip>
            <prefix-length>24</prefix-length>
          </address>
        </ipv4>
      </interface>
      <interface>
        <name>GigabitEthernet0/1</name>
        <description>User-Port-VLAN100</description>
        <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
        <enabled>false</enabled>
        <mtu>1400</mtu>
        <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip">
          <address>
            <ip>198.51.100.2</ip>
            <prefix-length>24</prefix-length>
          </address>
        </ipv4>
      </interface>
    </interfaces>
  </data>
</rpc-reply>
"""


def build_get_config(message_id: str = "101") -> ET.Element:
    """构造 <rpc><get-config>...</get-config></rpc> 请求树。"""
    rpc = ET.Element(QName(NC_NS, "rpc"), {"message-id": message_id})
    get_config = SubElement(rpc, QName(NC_NS, "get-config"))
    source = SubElement(get_config, QName(NC_NS, "source"))
    SubElement(source, QName(NC_NS, "running"))
    flt = SubElement(get_config, QName(NC_NS, "filter"), {"type": "subtree"})
    interfaces = SubElement(flt, QName(IF_NS, "interfaces"))
    SubElement(interfaces, QName(IF_NS, "interface"))
    return rpc


def dump_xml(elem: ET.Element, title: str) -> None:
    print(SUB)
    print(title)
    print(SUB)
    ET.indent(elem, space="  ")
    text = ET.tostring(elem, encoding="unicode")
    for line in text.splitlines():
        print("  " + line)
    print(SUB)
    print(f"  报文长度 = {len(text)} 字节")


def parse_reply(xml_text: str) -> list:
    """按 YANG 路径提取接口清单，返回 [dict, ...]。"""
    root = ET.fromstring(xml_text)
    ns = {"nc": NC_NS, "if": IF_NS, "ip": IP_NS}
    rows = []
    for iface in root.findall(".//if:interface", ns):
        name = iface.findtext("if:name", default="", namespaces=ns)
        desc = iface.findtext("if:description", default="", namespaces=ns)
        enabled = iface.findtext("if:enabled", default="", namespaces=ns)
        mtu = iface.findtext("if:mtu", default="", namespaces=ns)
        addr = iface.find("ip:ipv4/ip:address", ns)
        ip = addr.findtext("ip:ip", default="", namespaces=ns) if addr is not None else ""
        plen = addr.findtext("ip:prefix-length", default="", namespaces=ns) if addr is not None else ""
        rows.append({
            "name": name, "desc": desc, "enabled": enabled,
            "mtu": mtu, "ip": ip, "plen": plen,
        })
    return rows


def main() -> None:
    print(SEP)
    print("NETCONF / YANG 演练：构造 get-config 请求、解析 config 响应")
    print(SEP)

    print(SUB)
    print("【一】NETCONF 分层与常见操作")
    print(SUB)
    print(f"{'操作':<16}{'作用':<40}{'以 YANG 为例'}")
    print(SUB)
    ops = [
        ("<get>", "读运行状态 + 配置（含 state 数据）", "取接口计数器、CPU 利用率"),
        ("<get-config>", "只读配置数据，需指定数据源", "读取 running / candidate 配置"),
        ("<edit-config>", "修改候选配置或直接改运行配置", "merge / replace / create / delete"),
        ("<commit>", "把候选配置提交为运行配置", "配合 confirmed-commit 做自动回滚"),
        ("<lock>/<unlock>", "锁定配置数据，防止并发修改", "配置变更前先 lock candidate"),
    ]
    for a, b, c in ops:
        print(f"{a:<16}{b:<40}{c}")

    print()
    dump_xml(build_get_config(), "【二】构造的 <rpc><get-config> 请求（subtree 过滤接口）")

    print()
    print(SUB)
    print("【三】解析示例 <rpc-reply>（按 YANG 路径提取）")
    print(SUB)
    rows = parse_reply(SAMPLE_REPLY)
    print(f"{'接口名':<24}{'描述':<20}{'enabled':<9}{'MTU':<7}{'地址'}")
    print(SUB)
    for row in rows:
        print(f"{row['name']:<24}{row['desc']:<20}{row['enabled']:<9}"
              f"{row['mtu']:<7}{row['ip']}/{row['plen']}")
    print(SUB)
    print("  提取路径示例（第 1 个接口）：")
    if rows:
        base = f"/interfaces/interface[name='{rows[0]['name']}']"
        print(f"    name        <- {base}/name")
        print(f"    description <- {base}/description")
        print(f"    enabled     <- {base}/enabled")
        print(f"    mtu         <- {base}/mtu")
        print(f"    ip/prefix   <- {base}/ipv4/address/ip + /ipv4/address/prefix-length")

    print()
    print(SUB)
    print("【四】数据模型对照：命令行 vs YANG 路径")
    print(SUB)
    print(f"{'运维看到的 CLI':<44}{'对应 YANG 路径'}")
    print(SUB)
    mapping = [
        ("interface Gi0/0", "/interfaces/interface/name"),
        (" ip address 192.0.2.1 255.255.255.0",
         "/interfaces/interface/ipv4/address/ip + prefix-length"),
        (" mtu 1500", "/interfaces/interface/mtu"),
        (" shutdown", "/interfaces/interface/enabled = false"),
        (" description Uplink-to-R1", "/interfaces/interface/description"),
    ]
    for a, b in mapping:
        print(f"{a:<44}{b}")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. NETCONF 把配置操作标准化为 rpc：get-config 读、edit-config 改、commit 提交。")
    print("2. 每个字段都有确定的 YANG 路径（如 /interfaces/interface/name），机器可解析、可校验。")
    print("3. 候选配置(candidate)+提交(commit)是 NETCONF 相对 CLI 的核心优势：支持事务与回滚。")
    print("4. 用标准库 ElementTree + 命名空间即可构造和解析 NETCONF 报文，无需第三方库。")
    print()


if __name__ == "__main__":
    main()
