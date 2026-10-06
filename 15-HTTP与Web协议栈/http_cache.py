#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给定响应头逐条判定：强缓存是否命中、是否需要协商缓存、启发式过期计算。

运行: python3 http_cache.py
"""
import sys
from email.utils import parsedate_to_datetime

sys.dont_write_bytecode = True

HEURISTIC_RATIO = 0.10          # 启发式新鲜度比例
HEURISTIC_CAP = 86400           # 启发式上限 24 小时


def to_epoch(gmt: str) -> int:
    return int(parsedate_to_datetime(gmt).timestamp())


def get(headers: dict[str, str], name: str) -> str | None:
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None


def evaluate(title: str, headers: dict[str, str], now: int, last_used: int) -> None:
    """打印 HTTP 缓存判定过程。now/last_used 为 epoch 秒。"""
    print("\n" + "-" * 72)
    print("场景：%s" % title)
    print("-" * 72)
    for k, v in headers.items():
        print("    %-18s: %s" % (k, v))
    age = now - last_used
    print("    已缓存时长 age = now - stored = %d 秒" % age)

    cc = (get(headers, "Cache-Control") or "").lower()
    cc_has = lambda token: token in [t.strip() for t in cc.split(",") if t.strip()]

    if cc_has("no-store"):
        print("    -> Cache-Control: no-store：响应禁止写入任何缓存（连磁盘都不存）")
        print("    >>> 结论：不缓存，每次都必须回源。")
        return
    if cc_has("private"):
        print("    -> Cache-Control: private：只允许浏览器私有缓存，代理/CDN 不得缓存")
    if cc_has("no-cache"):
        print("    -> Cache-Control: no-cache：可以存但每次使用前必须与服务器协商校验")
        print("       （no-cache 不是「不缓存」，而是「缓存了也要校验」）")
        revalidate(headers, "强制协商校验")
        return

    max_age = None
    if cc_has("max-age=0") or "max-age" in cc:
        for token in [t.strip() for t in cc.split(",") if t.strip()]:
            if token.startswith("max-age="):
                max_age = int(token.split("=")[1])
    if max_age is not None:
        print("    -> 命中强缓存规则 Cache-Control: max-age=%d 秒" % max_age)
        if age < max_age:
            remain = max_age - age
            print("       age=%d < max-age=%d -> 强缓存新鲜，直接使用本地副本" % (age, max_age))
            print("    >>> 结论：强缓存命中，剩余新鲜期 %d 秒，不发任何请求。" % remain)
        else:
            print("       age=%d >= max-age=%d -> 已过期，进入协商缓存" % (age, max_age))
            revalidate(headers, "强缓存过期后协商")
        return

    expires = get(headers, "Expires")
    if expires:
        exp = to_epoch(expires)
        print("    -> 无 Cache-Control，退回 HTTP/1.0 的 Expires: %s" % expires)
        print("       now=%d, Expires=%d" % (now, exp))
        if now < exp:
            print("    >>> 结论：Expires 未到，强缓存命中。")
        else:
            print("    >>> 结论：Expires 已过，进入协商缓存。")
            revalidate(headers, "Expires 过期后协商")
        return

    lm = get(headers, "Last-Modified")
    date = get(headers, "Date")
    if lm and date:
        d = to_epoch(date)
        lm_epoch = to_epoch(lm)
        span = max(0, d - lm_epoch)
        heuristic = min(int(span * HEURISTIC_RATIO), HEURISTIC_CAP)
        print("    -> 无 Cache-Control 且无 Expires，使用启发式过期公式：")
        print("       新鲜期 = (Date - Last-Modified) × 10%")
        print("              = (%d - %d) × 0.10" % (d, lm_epoch))
        print("              = %d × 0.10 = %d 秒（上限 %d 秒）" % (span, heuristic, HEURISTIC_CAP))
        if age < heuristic:
            print("    >>> 结论：启发式新鲜期内，强缓存命中，剩余 %d 秒。" % (heuristic - age))
        else:
            print("    >>> 结论：启发式新鲜期已过，进入协商缓存。")
            revalidate(headers, "启发式过期后协商")
        return

    print("    -> 响应头里没有任何缓存指示，可自由缓存（各实现策略不同）")
    print("    >>> 结论：由客户端启发式决定，通常回源。")


def revalidate(headers: dict[str, str], why: str) -> None:
    etag = get(headers, "ETag")
    lm = get(headers, "Last-Modified")
    print("    [协商缓存] 原因：%s" % why)
    if etag:
        print("      请求带 If-None-Match: %s" % etag)
        print("        服务器比对 ETag：命中返回 304 Not Modified（不带正文），否则 200 + 新正文")
    if lm:
        print("      请求带 If-Modified-Since: %s" % lm)
        print("        服务器比对修改时间：未变化返回 304，否则 200 + 新正文")
    if not etag and not lm:
        print("      既无 ETag 也无 Last-Modified，无法协商，只能整体回源 200")
    print("    >>> 结论：协商命中得 304，可省正文带宽但仍有 1 个 RTT 开销。")


def main() -> None:
    print("=" * 72)
    print("HTTP 缓存判定演示（强缓存 / 协商缓存 / 启发式过期）")
    print("=" * 72)
    print("时间轴：now=1760000300（epoch 秒），缓存写入时间 stored 见各场景")

    # 场景 A：强缓存新鲜
    evaluate(
        "max-age=300，缓存 100 秒后再次访问",
        {"Date": "Mon, 06 Oct 2026 08:00:00 GMT",
         "Cache-Control": "public, max-age=300",
         "Content-Type": "text/html"},
        now=1760000300, last_used=1760000300 - 100,
    )

    # 场景 B：强缓存过期 -> 协商，有 ETag
    evaluate(
        "max-age=300，缓存 400 秒后再次访问（有过期但带 ETag）",
        {"Date": "Mon, 06 Oct 2026 08:00:00 GMT",
         "Cache-Control": "max-age=300",
         "ETag": "\"v1-abc\"",
         "Content-Type": "text/html"},
        now=1760000300, last_used=1760000300 - 400,
    )

    # 场景 C：no-cache
    evaluate(
        "Cache-Control: no-cache（可存但每次必须校验）",
        {"Cache-Control": "no-cache", "ETag": "\"v2-def\""},
        now=1760000300, last_used=1760000300 - 10,
    )

    # 场景 D：no-store
    evaluate(
        "Cache-Control: no-store（完全禁止缓存）",
        {"Cache-Control": "no-store", "Content-Type": "text/html"},
        now=1760000300, last_used=1760000300,
    )

    # 场景 E：启发式过期
    evaluate(
        "仅有 Last-Modified，无 Cache-Control / Expires",
        {"Date": "Mon, 06 Oct 2026 08:00:00 GMT",
         "Last-Modified": "Mon, 29 Sep 2026 08:00:00 GMT",
         "Content-Type": "text/html"},
        now=1760000300, last_used=1760000300 - 3600,
    )

    # 场景 F：Expires（HTTP/1.0）
    evaluate(
        "仅 Expires: Mon, 06 Oct 2026 08:10:00 GMT",
        {"Date": "Mon, 06 Oct 2026 08:00:00 GMT",
         "Expires": "Mon, 06 Oct 2026 08:10:00 GMT",
         "Content-Type": "text/html"},
        now=to_epoch("Mon, 06 Oct 2026 08:05:00 GMT"),
        last_used=to_epoch("Mon, 06 Oct 2026 08:00:00 GMT"),
    )

    print("\n" + "=" * 72)
    print("指令对照表")
    print("=" * 72)
    print("%-18s %-22s %s" % ("指令", "含义", "典型场景"))
    print("-" * 72)
    rows = [
        ("max-age=N", "强缓存 N 秒内直接用本地副本", "静态资源长缓存"),
        ("no-cache", "可缓存，但使用前必须协商校验", "频繁变更的 HTML"),
        ("no-store", "完全不缓存，任何位置都不存", "含隐私的接口响应"),
        ("private", "仅浏览器可缓存，代理/CDN 不可", "用户相关的个性化页面"),
        ("public", "允许任何缓存（含 CDN）存储", "无差异的静态资源"),
        ("must-revalidate", "过期后禁止用陈旧副本，必须校验", "强一致要求"),
        ("immutable", "期限内保证不变，连刷新都不校验", "带哈希指纹的 JS/CSS"),
    ]
    for a, b, c in rows:
        print("%-18s %-22s %s" % (a, b, c))

    print("\n" + "=" * 72)
    print("小结")
    print("-" * 72)
    print("1. 判断顺序：no-store(不缓存) -> no-cache(必校验) -> max-age -> Expires -> 启发式(10%)。")
    print("2. 强缓存命中时 0 请求 0 往返；协商缓存命中返回 304，省正文但不省 RTT。")
    print("3. 启发式新鲜期 = (Date - Last-Modified) × 10%，上限 24 小时，无显式头时兜底。")
    print("4. no-cache 与 no-store 最易混：前者「存但校验」，后者「根本不存」。")


if __name__ == "__main__":
    main()
