#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BGP 选路 11 步逐条演示：给 5 条候选路由，按属性顺序淘汰，打印每轮原因与胜出者。

运行: python3 bgp_best_path.py
"""
import sys
import unicodedata

sys.dont_write_bytecode = True


def w(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s, n):
    return s + " " * max(0, n - w(s))


def rid_num(rid):
    return tuple(int(x) for x in rid.split("."))


# 每步规则：(序号, 名称, 比较对象, 方向说明)
RULES = [
    (1, "Weight / Preferred-Value", "Weight", "大者优；思科私有，仅本机有效，不传递给邻居"),
    (2, "LOCAL_PREF", "LocalPref", "大者优；AS 内随 iBGP 传递，默认 100"),
    (3, "本地始发", "产生方式", "network / redistribute / aggregate 产生的优于学来的"),
    (4, "AS_PATH 长度", "AS_PATH", "短者优（AS_SET 只计 1）"),
    (5, "ORIGIN", "Origin", "IGP(0) 优于 EGP(1) 优于 INCOMPLETE(2)"),
    (6, "MED", "MED", "小者优；默认只在「同一邻居 AS」的多条路径间比较"),
    (7, "eBGP 优于 iBGP", "邻居类型", "同前缀下外部路由优先"),
    (8, "IGP 度量", "到 NEXT_HOP 的度量", "小者优；前提是下一跳能递归解析"),
    (9, "路由年龄", "Age", "思科：同为 eBGP 时取最早收到的（抑制抖动）"),
    (10, "Router-ID", "对端 Router-ID", "小者优（比较的是起源路由器 ID）"),
    (11, "Cluster-List 长度", "Cluster-List", "短者优；再平局比对等体地址，小者优"),
]


def new(name, **kw):
    base = dict(name=name, weight=0, local_pref=100, local=False, as_path_len=1,
                origin="IGP", med=0, neigh_as=65001, peer="eBGP", igp=30, age=100,
                rid="203.0.113.1", nbr="203.0.113.1", cluster=0)
    base.update(kw)
    return base


ORIGIN_RANK = {"IGP": 0, "EGP": 1, "INCOMPLETE": 2}
PEER_RANK = {"eBGP": 1, "iBGP": 0}


def apply_rule(idx, cands):
    """返回 (幸存列表, 淘汰列表, 说明, 是否平局)。"""
    if idx == 1:
        key = lambda c: c["weight"]
        desc = "Weight"
        best = max(key(c) for c in cands)
        return _filter(cands, key, best, equal=True,
                       tie_txt=f"全平局（Weight 都是 {best}）",
                       win_txt=f"Weight 最大 = {best}", desc=desc, fmt=lambda c: c["weight"])
    if idx == 2:
        key = lambda c: c["local_pref"]
        best = max(key(c) for c in cands)
        return _filter(cands, key, best, equal=True,
                       tie_txt=f"全平局（LocalPref 都是 {best}）",
                       win_txt=f"LocalPref 最大 = {best}", desc="LocalPref",
                       fmt=lambda c: c["local_pref"])
    if idx == 3:
        key = lambda c: 1 if c["local"] else 0
        best = max(key(c) for c in cands)
        return _filter(cands, key, best, equal=True,
                       tie_txt="全平局（没有本地始发的路由）",
                       win_txt="本地始发优先", desc="产生方式",
                       fmt=lambda c: "本地始发" if c["local"] else "从邻居学来")
    if idx == 4:
        key = lambda c: c["as_path_len"]
        best = min(key(c) for c in cands)
        return _filter(cands, key, best, equal=False,
                       tie_txt=f"全平局（AS_PATH 长度都是 {best}）",
                       win_txt=f"AS_PATH 最短 = {best}", desc="AS_PATH 长度",
                       fmt=lambda c: str(c["as_path_len"]))
    if idx == 5:
        key = lambda c: ORIGIN_RANK[c["origin"]]
        best = min(key(c) for c in cands)
        return _filter(cands, key, best, equal=False,
                       tie_txt=f"全平局（Origin 都是 {cands[0]['origin']}）",
                       win_txt="Origin 最优 = IGP", desc="Origin",
                       fmt=lambda c: f"{c['origin']}({ORIGIN_RANK[c['origin']]})")
    if idx == 6:
        groups = {c["neigh_as"] for c in cands}
        if len(groups) > 1:
            return cands, [], ("跳过：候选来自不同邻居 AS "
                               f"({','.join(str(g) for g in sorted(groups))})，"
                               "按默认规则 MED 不参与比较"), True
        key = lambda c: c["med"]
        best = min(key(c) for c in cands)
        return _filter(cands, key, best, equal=False,
                       tie_txt=f"全平局（MED 都是 {best}）",
                       win_txt=f"MED 最小 = {best}", desc="MED",
                       fmt=lambda c: str(c["med"]))
    if idx == 7:
        key = lambda c: PEER_RANK[c["peer"]]
        best = max(key(c) for c in cands)
        return _filter(cands, key, best, equal=True,
                       tie_txt="全平局（都是同类邻居）",
                       win_txt="eBGP 优先于 iBGP", desc="邻居类型",
                       fmt=lambda c: c["peer"])
    if idx == 8:
        key = lambda c: c["igp"]
        best = min(key(c) for c in cands)
        return _filter(cands, key, best, equal=False,
                       tie_txt=f"全平局（IGP 度量都是 {best}）",
                       win_txt=f"IGP 度量最小 = {best}", desc="IGP 度量",
                       fmt=lambda c: str(c["igp"]))
    if idx == 9:
        key = lambda c: c["age"]
        best = max(key(c) for c in cands)
        return _filter(cands, key, best, equal=True,
                       tie_txt=f"全平局（年龄都是 {best}s）",
                       win_txt=f"最早收到（年龄最大 = {best}s）", desc="年龄",
                       fmt=lambda c: f"{c['age']}s")
    if idx == 10:
        key = lambda c: rid_num(c["rid"])
        best = min(key(c) for c in cands)
        return _filter(cands, key, best, equal=False,
                       tie_txt=f"全平局（Router-ID 都是 {cands[0]['rid']}）",
                       win_txt=f"Router-ID 最小 = {'.'.join(map(str, best))}", desc="Router-ID",
                       fmt=lambda c: c["rid"])
    # idx == 11
    key = lambda c: c["cluster"]
    best = min(key(c) for c in cands)
    return _filter(cands, key, best, equal=False,
                   tie_txt=f"全平局（Cluster-List 长度都是 {best}）",
                   win_txt=f"Cluster-List 最短 = {best}", desc="Cluster-List 长度",
                   fmt=lambda c: str(c["cluster"]))


def _filter(cands, key, best, equal, tie_txt, win_txt, desc, fmt):
    kept, gone = [], []
    for c in cands:
        (kept if key(c) == best else gone).append(c)
    if not gone:
        return cands, [], tie_txt, True
    detail = "、".join(f"{c['name']}={fmt(c)}" for c in gone)
    reason = f"淘汰 {detail} —— 不及 {win_txt}"
    return kept, gone, reason, False


def run(scenario_title, cands):
    print("=" * 104)
    print(scenario_title)
    print("-" * 104)
    print(pad("候选", 16) + pad("Weight", 8) + pad("LP", 6) + pad("AS长度", 8)
          + pad("Origin", 12) + pad("MED", 6) + pad("邻居AS", 10) + pad("类型", 8)
          + pad("IGP", 6) + pad("年龄", 8) + "Router-ID")
    for c in cands:
        print(pad(c["name"], 16) + pad(str(c["weight"]), 8) + pad(str(c["local_pref"]), 6)
              + pad(str(c["as_path_len"]), 8) + pad(c["origin"], 12) + pad(str(c["med"]), 6)
              + pad(str(c["neigh_as"]), 10) + pad(c["peer"], 8) + pad(str(c["igp"]), 6)
              + pad(f"{c['age']}s", 8) + c["rid"])
    print("-" * 104)
    survivors = list(cands)
    winner = None
    for idx, rname, obj, direction in RULES:
        if winner is not None:
            print(pad(f"步骤 {idx}", 10) + pad(rname, 26)
                  + f"未执行（已在上一步唯一确定）")
            continue
        kept, gone, reason, tie = apply_rule(idx, survivors)
        print(pad(f"步骤 {idx}", 10) + pad(rname, 26) + "比较 " + pad(obj, 18))
        print(pad("", 10) + "  → " + reason)
        survivors = kept
        if not tie:
            names = "、".join(c["name"] for c in survivors)
            print(pad("", 10) + "  幸存：" + names)
        if len(survivors) == 1:
            winner = survivors[0]
    print("-" * 104)
    if winner:
        print(f">>> 最终胜出：{winner['name']}"
              f"（下一跳 {winner['nbr']}，Router-ID {winner['rid']}）")
    else:
        print(">>> 11 步全部走完仍有多条等价路由 → 开启 multipath 时全部装表做负载分担")
    print()
    return winner


def main():
    print()
    print("BGP 选路最佳路径演示 · 目的前缀 198.51.100.0/24，本机 AS 65001")
    print("规则说明：严格按 1→11 顺序执行，某一步出现唯一最优就立即结束，后面的步骤不再执行。")
    print()
    print(pad("步骤", 6) + pad("规则", 26) + pad("比较对象", 24) + "方向")
    for idx, rname, obj, direction in RULES:
        print(pad(str(idx), 6) + pad(rname, 26) + pad(obj, 24) + direction)
    print()

    base = [
        new("A(AS65001)", weight=0, local_pref=100, as_path_len=1, origin="IGP",
            med=20, neigh_as=65001, peer="eBGP", igp=30, age=100,
            rid="203.0.113.1", nbr="203.0.113.1"),
        new("B(AS65001)", weight=0, local_pref=100, as_path_len=1, origin="IGP",
            med=10, neigh_as=65001, peer="eBGP", igp=30, age=120,
            rid="203.0.113.2", nbr="203.0.113.2"),
        new("C(AS65002)", weight=0, local_pref=100, as_path_len=2, origin="IGP",
            med=5, neigh_as=65002, peer="eBGP", igp=20, age=60,
            rid="203.0.113.3", nbr="203.0.113.3"),
        new("D(AS65003)", weight=0, local_pref=100, as_path_len=1, origin="IGP",
            med=15, neigh_as=65003, peer="eBGP", igp=30, age=200,
            rid="203.0.113.4", nbr="203.0.113.4"),
        new("E(AS65004)", weight=0, local_pref=50, as_path_len=1, origin="EGP",
            med=5, neigh_as=65004, peer="eBGP", igp=10, age=80,
            rid="203.0.113.5", nbr="203.0.113.5"),
    ]
    run("场景 1（基准）：5 条候选，看规则在第几步收敛", base)

    s2 = [dict(c) for c in base]
    for c in s2:
        c["age"] = 120                      # 把年龄拉平，让 Router-ID 接手
    run("场景 2：把年龄拉平 → 决策点后移到第 10 步（Router-ID）", s2)

    s3 = [
        new("X(RR客户端)", weight=0, local_pref=100, as_path_len=1, origin="IGP",
            med=10, neigh_as=65001, peer="iBGP", igp=30, age=120,
            rid="203.0.113.7", nbr="203.0.113.7", cluster=2),
        new("Y(RR客户端)", weight=0, local_pref=100, as_path_len=1, origin="IGP",
            med=10, neigh_as=65001, peer="iBGP", igp=30, age=120,
            rid="203.0.113.7", nbr="203.0.113.8", cluster=3),
    ]
    run("场景 3（边界构造）：前 10 步全平，只有 Cluster-List 长度不同", s3)

    print("=" * 104)
    print("厂商差异提示")
    print("-" * 104)
    print("· 思科第 1 步是 Weight，华为对应 Preferred-Value（命令 peer x.x.x.x preferred-value N）：")
    print("  两者作用等价，都只在本地有效、不随报文传出。")
    print("· 思科把「路由年龄」放在 Router-ID 之前；华为不比较年龄，")
    print("  直接在 IGP 度量之后比较 Cluster-List 长度、再比 Router-ID、最后比对等体地址。")
    print("· 第 3 步「本地始发」的优先级链是：手动 aggregate > 自动 aggregate > network > import-route。")
    print("· MED 默认只在同一邻居 AS 的多条路径间比较；跨 AS 比 MED 需显式打开")
    print("  「always-compare-med」，这一步是现网选路不符合预期的高发原因。")
    print()
    print("小结：")
    print("1. 选路是严格的字典序：任何一步出现唯一最优立即结束，后面十步形同不存在。")
    print("2. 实际排障时先看 Weight/LocalPref（本地可控），再看 AS_PATH、MED（对端可控），")
    print("   最后才轮到 IGP 度量与 Router-ID —— 前面几项才是「人为调过」的高概率位置。")
    print("3. 想让某条路优先，最稳妥的是调 LocalPref（作用 AS 内、语义清晰），")
    print("   而不是依赖 Router-ID 这类「碰巧」的比较项。")
    print()


if __name__ == "__main__":
    main()
