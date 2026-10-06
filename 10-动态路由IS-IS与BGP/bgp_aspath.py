#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BGP AS_PATH 防环 + iBGP 水平分割 / 路由反射器 / 联盟 / Cluster-List 防环演示。

运行: python3 bgp_aspath.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


LOCAL_AS = 65001


def as_path_str(path):
    if not path:
        return "(空)"
    return " ".join(str(a) for a in path)


def recv_from_ebgp(path, local_as):
    """eBGP 收到路由：先做「AS_PATH 中是否有本 AS」的环路检查。"""
    if local_as in path:
        return False, f"AS_PATH 中出现本地 AS {local_as} → 判定环路，直接丢弃该路由"
    return True, "AS_PATH 中不含本地 AS，接受"


def send_to_ebgp(path, local_as):
    """向 eBGP 邻居发送：把自己的 AS 号 prepend 到 AS_PATH 最前面。"""
    return [local_as] + list(path)


def section(title):
    print("=" * 100)
    print(title)
    print("-" * 100)


def main():
    print()
    print("BGP AS_PATH 防环与 iBGP 水平分割 / 路由反射器演示 · 本机 AS 65001")
    print()

    # ---------------- 一、AS_PATH 防环 ----------------
    section("一、AS_PATH 防环：收到含本 AS 号的路由必须拒绝")
    print(pad("场景", 26) + pad("收到的 AS_PATH", 30) + "处理结果")
    cases = [
        ("eBGP 收到正常路由", [65002, 65003, 65004]),
        ("eBGP 收到环路路由", [65002, 65003, 65001]),
        ("eBGP 收到两跳环路", [65002, 65001]),
    ]
    for name, path in cases:
        ok, msg = recv_from_ebgp(path, LOCAL_AS)
        print(pad(name, 26) + pad(as_path_str(path), 30) + msg)
    print("-" * 100)
    print("步骤编号（eBGP 收方向）：")
    print("  1) 检查 AS_PATH 中是否含本 AS 号；含则丢弃，不再参与选路。")
    print("  2) 通过检查后，比较其它属性进入 11 步选路流程。")
    print("  3) 若被选为最优并向外宣告，把自己的 AS 号 prepend 到最前面。")
    print("步骤编号（eBGP 发方向）：")
    print("  1) 取本地最优路由的 AS_PATH。")
    print("  2) 在最前面插入本地 AS 号（如 [65002] → [65001, 65002]）。")
    print("  3) 发给 eBGP 邻居。iBGP 方向不改 AS_PATH。")
    print("-" * 100)
    for name, path in cases:
        ok, msg = recv_from_ebgp(path, LOCAL_AS)
        if ok:
            new = send_to_ebgp(path, LOCAL_AS)
            print(f">>> {name}：接受，转发给 eBGP 邻居时 AS_PATH 变为 {as_path_str(new)}")
        else:
            print(f">>> {name}：拒绝，不装表、不转发 —— {msg}")
    print()

    # ---------------- 二、iBGP 水平分割 ----------------
    section("二、iBGP 水平分割：从 iBGP 学来的路由，不再传给其它 iBGP 邻居")
    routers = ["R1", "R2", "R3", "R4"]
    full_mesh = len(routers) * (len(routers) - 1) // 2
    print("拓扑（AS 65001 内部 4 台路由器，R1 从 AS 65002 学到 198.51.100.0/24）：")
    print("      AS 65002")
    print("         │ eBGP")
    print("        R1")
    print("     ╱  │  ╲")
    print("   R2   R3   R4       ← AS 65001 内的 iBGP 对等关系")
    print("-" * 100)
    print(f"若不使用路由反射器，iBGP 需要全网状(Full Mesh)对等：{len(routers)} 台需要 "
          f"{full_mesh} 条会话。")
    print(f"原因：R1 从 eBGP 学到路由后可以发给 R2/R3/R4，但 R2 从 R1 这条 iBGP 会话学到的路由")
    print(f"      不能再转发给 R3、R4 —— 这就是 iBGP 的水平分割规则。")
    print()
    print("逐跳推演（无路由反射器）：")
    steps = [
        ("R1 从 eBGP(AS65002) 学到 198.51.100.0/24", "AS_PATH=[65002]", "R1 装表"),
        ("R1 向 R2/R3/R4 宣告（iBGP，不改 AS_PATH）", "AS_PATH=[65002]", "R2/R3/R4 学到"),
        ("R2 想把该路由转给 R3（同为 iBGP）", "AS_PATH=[65002]",
         "被水平分割阻止：iBGP 学来的不再转给 iBGP 邻居"),
        ("结论", "", "R3、R4 只能靠 R1 直连或全网状对等才能学到"),
    ]
    print(pad("步骤", 46) + pad("AS_PATH", 18) + "结果")
    for a, b, c in steps:
        print(pad(a, 46) + pad(b, 18) + c)
    print()

    # ---------------- 三、路由反射器 ----------------
    section("三、路由反射器（Route Reflector）：用 Cluster 打破水平分割")
    print("把 R2 设为 RR，cluster-id = 1.1.1.1，R1/R3/R4 为客户机（Client）：")
    print("      R1(client) ──┐")
    print("                   ├── R2(RR, cluster 1.1.1.1)")
    print("  R3(client) ─────┤")
    print("  R4(client) ─────┘")
    print("-" * 100)
    rr_steps = [
        ("R1 → R2（client 发给 RR）", "Cluster-List=空", "RR 接受"),
        ("R2 反射给 R3（client）", "Cluster-List=[1.1.1.1]", "R3 接受并装表"),
        ("R2 反射给 R4（client）", "Cluster-List=[1.1.1.1]", "R4 接受并装表"),
        ("R3 → R2 回送该路由", "Cluster-List=[1.1.1.1]",
         "RR 发现列表里已有自己的 cluster-id 1.1.1.1 → 丢弃，防环"),
        ("会话数量", "", f"从 {full_mesh} 条降到 {len(routers) - 1} 条（每台 client 只与 RR 建会话）"),
    ]
    print(pad("步骤", 34) + pad("Cluster-List", 28) + "结果")
    for a, b, c in rr_steps:
        print(pad(a, 34) + pad(b, 28) + c)
    print("-" * 100)
    print(">>> 结论：RR 反射路由时会给 Cluster-List 追加自己的 cluster-id；")
    print("    任何路由器收到 Cluster-List 中已含自己 cluster-id 的路由就丢弃，避免反射成环。")
    print()

    # ---------------- 四、联盟 ----------------
    section("四、联盟（Confederation）：把一个 AS 拆成若干子 AS")
    print("AS 65001 内部再分为 65001:1 / 65001:2 / 65001:3 三个子 AS，对外仍是一个 AS 65001。")
    print("-" * 100)
    print(pad("对比项", 24) + pad("路由反射器", 32) + "联盟")
    print(pad("环路防护", 24) + pad("Cluster-List", 32) + "AS_CONFED_SEQUENCE")
    print(pad("AS_PATH 变化", 24) + pad("不变（仍是外部 AS 序列）", 32) + "子 AS 号记在 AS_CONFED_SEQUENCE")
    print(pad("对外可见性", 24) + pad("完全透明", 32) + "子 AS 信息不出联盟，出口剥除")
    print(pad("对等关系", 24) + pad("iBGP 会话 + Cluster", 32) + "子 AS 间像 eBGP，子 AS 内像 iBGP")
    print(pad("复杂度", 24) + pad("低，现网主流", 32) + "高，配置与排障都更重")
    print("-" * 100)
    conf_path = ["(AS_CONFED_SEQUENCE: 65001:1 65001:2)", "65002", "65003"]
    print(f"示意：联盟内部传播时 AS_PATH 形如 {conf_path[0]} + [65002 65003]，")
    print("      离开联盟边界时子 AS 序列被清除，对外只看到 AS 65001 65002 65003。")
    print(">>> 结论：联盟本质是「用多台设备分摊 iBGP 全互联的会话压力」，")
    print("    而 RR 是「用一台设备做反射中心」，两者都是为了替代 n(n-1)/2 的 iBGP 全互联。")
    print()
    print("小结：")
    print("1. AS_PATH 防环是 eBGP 的第一道闸门：收到含本 AS 号的 AS_PATH 一律丢弃。")
    print("2. iBGP 水平分割规定「iBGP 学来的路由不再转给其它 iBGP 邻居」，因此默认需要全网状对等。")
    print("3. 路由反射器用 Cluster-List 打破水平分割；联盟用 AS_CONFED_SEQUENCE 防环，")
    print("   两者都只在 AS 内部有效，对外完全透明。")
    print()


if __name__ == "__main__":
    main()
