#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K8s Service 流量路径建模：外部 -> Ingress -> ClusterIP -> Endpoint -> Pod 与 DNAT/SNAT。

运行: python3 k8s_service_path.py
"""
import sys

sys.dont_write_bytecode = True

SEP = "=" * 78
SUB = "-" * 78

# 统一演示地址（RFC 5737 与 K8s 典型私有段）
CLIENT = "203.0.113.50:40000"
NODE = "192.0.2.100:30080"
INGRESS_POD = "10.244.1.5:8080"
SVC_CLUSTERIP = "10.96.0.10:80"
ENDPOINT_POD = "10.244.3.7:8080"


def hop_table(rows: list) -> None:
    print(f"{'跳':<4}{'位置':<20}{'源地址:端口':<24}{'目的地址:端口':<24}{'动作'}")
    print(SUB)
    for i, (place, src, dst, act) in enumerate(rows, 1):
        print(f"{i:<4}{place:<20}{src:<24}{dst:<24}{act}")


def main() -> None:
    print(SEP)
    print("Kubernetes Service 流量路径与地址转换建模")
    print(SEP)
    print("场景：集群外客户端访问 Ingress -> Ingress 反代到 Service -> 转发到后端 Pod")
    print(f"  客户端      = {CLIENT}")
    print(f"  NodePort    = {NODE}")
    print(f"  Ingress Pod = {INGRESS_POD}")
    print(f"  Service     = {SVC_CLUSTERIP}（ClusterIP）")
    print(f"  Endpoint Pod= {ENDPOINT_POD}")

    print()
    print(SUB)
    print("【一】去程逐跳路径（每跳发生在哪里、改了什么）")
    print(SUB)
    hops = [
        ("集群外客户端", CLIENT, NODE, "发起请求，目的为 Node 的 NodePort"),
        ("Node 内核 netfilter", f"{CLIENT}", INGRESS_POD,
         "kube-proxy 规则 DNAT: NodePort -> Ingress Pod"),
        ("Ingress Controller", INGRESS_POD.split(':')[0], SVC_CLUSTERIP,
         "反向代理，按 Host/Path 新建一条到 Service 的连接"),
        ("Node 内核 netfilter", f"{INGRESS_POD.split(':')[0]}:45000", ENDPOINT_POD,
         "kube-proxy 规则 DNAT: ClusterIP -> 选中 Endpoint"),
        ("后端 Pod", ENDPOINT_POD.split(':')[0], "-",
         "业务处理，按 conntrack 反向表回包"),
    ]
    hop_table(hops)

    print()
    print(SUB)
    print("【二】地址转换明细（DNAT / SNAT 逐条）")
    print(SUB)
    print(f"{'阶段':<24}{'转换类型':<16}{'转换前':<26}{'转换后'}")
    print(SUB)
    nat_rows = [
        ("NodePort -> Pod", "DNAT",
         f"dst {NODE}", f"dst {INGRESS_POD}"),
        ("Ingress 新建连接", "SNAT(隐式)",
         f"src 客户端IP", f"src {INGRESS_POD.split(':')[0]}"),
        ("ClusterIP -> Endpoint", "DNAT",
         f"dst {SVC_CLUSTERIP}", f"dst {ENDPOINT_POD}"),
        ("回程包", "conntrack 反向",
         f"src {ENDPOINT_POD}", f"src {SVC_CLUSTERIP} -> {NODE}"),
    ]
    for a, b, c, d in nat_rows:
        print(f"{a:<24}{b:<16}{c:<26}{d}")
    print(SUB)
    print(">>> 结论：一次外部访问在节点上经历 2 次 DNAT；Ingress 自身还会另起连接。")
    print(">>> externalTrafficPolicy=Local 时不 SNAT，保留客户端真实源 IP；")
    print(">>> externalTrafficPolicy=Cluster 时会 SNAT 成节点 IP，后端看不到真实源 IP。")

    print()
    print(SUB)
    print("【三】kube-proxy iptables 模式的规则膨胀")
    print(SUB)
    services = 5000
    eps_per_svc = 3
    endpoints = services * eps_per_svc
    rules = services + endpoints
    print(f"  假设：Service 数量 = {services}，每个 Service 平均 {eps_per_svc} 个 Endpoint")
    print(f"  总 Endpoint = {services} × {eps_per_svc} = {endpoints}")
    print("  iptables 链路结构：")
    print("    KUBE-SERVICES  —— 每个 Service 一条 jump 规则（线性匹配）")
    print("    KUBE-SVC-xxx   —— 每个服务一条链，按概率分发到各 Endpoint")
    print("    KUBE-SEP-yyy   —— 每个 Endpoint 一条 DNAT 规则")
    print(f"  规则总数约 = {services}(服务) + {endpoints}(端点) = {rules} 条")
    per_rule_us = 0.3
    scan_ms = services * per_rule_us / 1000
    print(f"  单包最坏匹配成本 ≈ {services} 条 × {per_rule_us} µs = {scan_ms:.1f} ms")
    print("  （数值为数量级估算，实际随内核版本、规则命中位置而变）")
    print()
    print("  每次 Service/Endpoint 变更都要重写整条规则链：")
    print(f"    一次变更的重写量约 {rules} 条规则 -> 变更风暴时 kube-proxy CPU 飙升")
    print(">>> 结论：iptables 模式的瓶颈不是规则数本身，而是「线性匹配 + 全量重写」。")

    print()
    print(SUB)
    print("【四】IPVS 与 eBPF 的改进")
    print(SUB)
    print(f"{'模式':<12}{'匹配复杂度':<16}{'更新代价':<22}{'适用规模'}")
    print(SUB)
    modes = [
        ("iptables", "O(服务数) 线性", "全量重写规则链", "中小集群"),
        ("IPVS", "O(1) 哈希查找", "只增删受影响条目", "大规模（数千 Service）"),
        ("nftables", "近似 O(服务数)，结构更优", "按表增量更新", "中大规模"),
        ("eBPF(Cilium)", "O(1) 哈希 + 可编程", "增量、无规则链", "超大规模、需可观测"),
    ]
    for a, b, c, d in modes:
        print(f"{a:<12}{b:<16}{c:<22}{d}")
    print(SUB)
    print(">>> 结论：IPVS 把「每包扫 N 条规则」换成「一次哈希查找」，")
    print("          在数千 Service 规模下连接建立时延与 kube-proxy CPU 都明显下降。")

    print()
    print(SUB)
    print("【五】关联的云网络概念对照")
    print(SUB)
    print(f"{'概念':<16}{'作用':<30}{'与 Service 的关系'}")
    print(SUB)
    cps = [
        ("ClusterIP", "集群内虚拟 IP", "由 kube-proxy 规则实现，仅集群内可达"),
        ("NodePort", "在每个节点暴露固定端口", "DNAT 到 Service 或直接到 Pod"),
        ("LoadBalancer", "云厂商负载均衡器接入", "把外部流量导到 NodePort/Ingress"),
        ("Ingress", "L7 路由（按域名/路径）", "自身也是 Pod，再代理到 Service"),
        ("NetworkPolicy", "Pod 级访问控制", "在 CNI 层实现，和 Service 转发独立"),
    ]
    for a, b, c in cps:
        print(f"{a:<16}{b:<30}{c}")

    print()
    print(SEP)
    print("小结")
    print(SEP)
    print("1. 外部访问 Pod 要经过 NodePort/Ingress 的 DNAT 与 ClusterIP 的 DNAT，共 2 次转换。")
    print("2. conntrack 记录转换关系，回程包自动反向转换；externalTrafficPolicy 决定是否 SNAT。")
    print(f"3. iptables 模式规则数约等于「服务数 + 端点数」，本例约 {rules} 条，且每包线性匹配。")
    print("4. IPVS 用哈希表把匹配降到 O(1)，并支持增量更新，是规模化集群的首选。")
    print()


if __name__ == "__main__":
    main()
