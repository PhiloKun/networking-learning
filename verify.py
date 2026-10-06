#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""networking-learning 仓库自检脚本（零第三方依赖，Python 3.9+）

五层校验，缺一不可：
  1) 结构   —— 23 个章节目录齐全，每章存在 README.md
  2) 体量   —— 笔记字节数达标、示例脚本数量达标、README 内引用的 .py 真实存在
  3) 语法   —— 用内置 compile() 逐文件编译（不落盘、不产生 __pycache__）
  4) 运行   —— 逐脚本 subprocess 运行：退出码须为 0，且输出不得含 Traceback
  5) 整洁   —— 运行前后对比文件快照，仓库不得出现非预期残留文件

用法:
    python3 verify.py                # 全部检查
    python3 verify.py 05 06 12       # 只检查指定章号
    python3 verify.py --syntax       # 只做语法检查（最快）
    python3 verify.py --no-run       # 结构 + 体量 + 语法，不实际运行脚本
    python3 verify.py --quiet        # 只打印失败项与汇总

退出码: 0 = 全部通过, 1 = 存在失败项
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---- 验收阈值（与 .build/SPEC.md 保持一致）----
MIN_NOTE_BYTES_MAIN = 9000      # 01~20 主线章笔记下限
MIN_NOTE_BYTES_SIDE = 8000      # 00 导论与 21/22 附录下限
MIN_SCRIPTS_MAIN = 3            # 01~20 每章示例脚本数下限
MIN_SCRIPTS_SIDE = 1            # 00/21/22 脚本数下限
RUN_TIMEOUT = 30                # 单个脚本运行上限（秒）
PY = sys.executable

SIDE_CHAPTERS = {"00", "21", "22"}
FAIL_TOKENS = (
    "Traceback (most recent call last)",
    "Segmentation fault",
    "core dumped",
)
RESIDUE_IGNORE = {"__pycache__", ".git", ".build", ".DS_Store"}

C_OK, C_BAD, C_WARN, C_DIM, C_END = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def styled(ok: bool) -> str:
    return f"{C_OK}通过{C_END}" if ok else f"{C_BAD}失败{C_END}"


def discover_chapters() -> list[str]:
    """返回形如 ['00-学习路线与知识地图', '01-...'] 的章节目录名（已排序）。"""
    names = [
        n for n in os.listdir(ROOT)
        if os.path.isdir(os.path.join(ROOT, n)) and re.match(r"^\d{2}-", n)
    ]
    return sorted(names)


def chapter_id(dirname: str) -> str:
    return dirname[:2]


def chapter_scripts(dirname: str) -> list[str]:
    d = os.path.join(ROOT, dirname)
    return sorted(f for f in os.listdir(d) if f.endswith(".py"))


def snapshot() -> set[str]:
    """仓库内所有文件的相对路径快照（排除忽略项）。"""
    found: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in RESIDUE_IGNORE]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            if any(part in RESIDUE_IGNORE for part in rel.split(os.sep)):
                continue
            found.add(rel)
    return found


# ---------------- 1. 结构 ----------------
def check_structure(chapters: list[str]) -> tuple[bool, list[str], list[str]]:
    problems: list[str] = []
    warns: list[str] = []
    for ch in chapters:
        readme = os.path.join(ROOT, ch, "README.md")
        if not os.path.isfile(readme):
            problems.append(f"{ch}/ 缺少 README.md")
    if not chapters:
        problems.append("未发现任何 NN- 形式的章节目录")
    if len(chapters) != 23:
        warns.append(f"章节目录数为 {len(chapters)}，预期 23（00~22）")
    return (not problems), problems, warns


# ---------------- 2. 体量 ----------------
def check_volume(chapters: list[str]) -> tuple[bool, list[str], list[str], dict]:
    problems: list[str] = []
    warns: list[str] = []
    stats = {"note_bytes": 0, "notes": 0, "scripts": 0}
    # 全仓库脚本清单：用于区分「跨章引用」（合理）与「引用不存在」（笔误）
    all_scripts = {f for name in discover_chapters() for f in chapter_scripts(name)}
    all_scripts.add("verify.py")
    for ch in chapters:
        cid = chapter_id(ch)
        is_side = cid in SIDE_CHAPTERS
        min_note = MIN_NOTE_BYTES_SIDE if is_side else MIN_NOTE_BYTES_MAIN
        min_scripts = MIN_SCRIPTS_SIDE if is_side else MIN_SCRIPTS_MAIN

        readme = os.path.join(ROOT, ch, "README.md")
        if os.path.isfile(readme):
            size = os.path.getsize(readme)
            stats["note_bytes"] += size
            stats["notes"] += 1
            if size < min_note:
                problems.append(
                    f"{ch}/README.md 仅 {size} 字节，低于下限 {min_note}（约需 {min_note // 1024}KB+）"
                )
            # README 中引用的 .py 是否真实存在
            with open(readme, "r", encoding="utf-8") as fh:
                text = fh.read()
            referenced = set(re.findall(r"[A-Za-z0-9_\-]+\.py", text))
            existing = set(chapter_scripts(ch))
            for ref in sorted(referenced - existing):
                if ref in all_scripts:
                    continue      # 跨章引用（导论/附录常引用其它章的脚本），合理
                warns.append(f"{ch}/README.md 引用了仓库中不存在的脚本 {ref}")

        scripts = chapter_scripts(ch)
        stats["scripts"] += len(scripts)
        if len(scripts) < min_scripts:
            problems.append(
                f"{ch}/ 仅 {len(scripts)} 个示例脚本，低于下限 {min_scripts}"
            )
    return (not problems), problems, warns, stats


# ---------------- 3. 语法 ----------------
def check_syntax(chapters: list[str]) -> tuple[bool, list[str]]:
    problems: list[str] = []
    for ch in chapters:
        for fn in chapter_scripts(ch):
            path = os.path.join(ROOT, ch, fn)
            rel = f"{ch}/{fn}"
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()
                if raw.startswith(b"\xef\xbb\xbf"):
                    problems.append(f"{rel} 带 UTF-8 BOM，请去掉")
                    continue
                src = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                problems.append(f"{rel} 不是合法 UTF-8：{exc}")
                continue
            try:
                compile(src, rel, "exec")
            except SyntaxError as exc:
                problems.append(f"{rel} 语法错误：第 {exc.lineno} 行 {exc.msg}")
    return (not problems), problems


# ---------------- 4. 运行 ----------------
def check_run(chapters: list[str], quiet: bool) -> tuple[bool, list[str], list[str]]:
    problems: list[str] = []
    warns: list[str] = []
    for ch in chapters:
        chdir = os.path.join(ROOT, ch)
        for fn in chapter_scripts(ch):
            rel = f"{ch}/{fn}"
            t0 = time.time()
            try:
                proc = subprocess.run(
                    [PY, fn],
                    cwd=chdir,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=RUN_TIMEOUT,
                    start_new_session=True,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"},
                )
            except subprocess.TimeoutExpired:
                problems.append(f"{rel} 运行超过 {RUN_TIMEOUT}s 未退出（疑似死循环 / 阻塞等待输入）")
                continue
            out = proc.stdout.decode("utf-8", errors="replace")
            elapsed = time.time() - t0
            if proc.returncode != 0:
                tail = "\n      ".join(out.strip().splitlines()[-6:])
                problems.append(f"{rel} 退出码 {proc.returncode}\n      {tail}")
                continue
            for token in FAIL_TOKENS:
                if token in out:
                    idx = out.find(token)
                    tail = "\n      ".join(out[idx:].strip().splitlines()[:6])
                    problems.append(f"{rel} 正常退出但输出含「{token}」\n      {tail}")
                    break
            if elapsed > 10 and not quiet:
                warns.append(f"{rel} 耗时 {elapsed:.1f}s，偏长（建议 < 5s）")
    return (not problems), problems, warns


# ---------------- 5. 整洁 ----------------
def check_clean(before: set[str]) -> tuple[bool, list[str], list[str]]:
    after = snapshot()
    residue = sorted(after - before)
    warns = [f"出现 __pycache__（建议脚本内设 sys.dont_write_bytecode = True）：见 {p}"
             for p in residue if "__pycache__" in p]
    hard = [p for p in residue if "__pycache__" not in p]
    return (not hard), [f"运行后残留文件：{p}" for p in hard], warns


# ---------------- 主流程 ----------------
def main() -> int:
    argv = [a for a in sys.argv[1:]]
    only_syntax = "--syntax" in argv
    no_run = "--no-run" in argv
    quiet = "--quiet" in argv
    filters = [a for a in argv if re.match(r"^\d{1,2}$", a)]

    chapters = discover_chapters()
    if filters:
        wanted = {f.zfill(2) for f in filters}
        chapters = [c for c in chapters if chapter_id(c) in wanted]
        if not chapters:
            print(f"{C_BAD}没有匹配章号 {filters} 的目录{C_END}")
            return 1

    print(f"\n{C_DIM}networking-learning 自检 · 共 {len(chapters)} 章 · Python {sys.version.split()[0]}{C_END}\n")
    all_problems: list[str] = []
    all_warns: list[str] = []

    def report(label: str, ok: bool, problems: list[str], warns: list[str]) -> None:
        mark = f"{C_OK}✓{C_END}" if ok else f"{C_BAD}✗{C_END}"
        if not quiet:
            print(f"  {mark} {label}  {styled(ok)}")
        all_problems.extend(problems)
        all_warns.extend(warns)

    # 1 结构
    ok, probs, warns = check_structure(chapters)
    report("结构：章节目录与 README 齐全", ok, probs, warns)
    # 2 体量
    ok, probs, warns, stats = check_volume(chapters)
    report("体量：笔记字节数与示例数量达标", ok, probs, warns)
    # 3 语法
    ok, probs = check_syntax(chapters)
    report("语法：可解码且通过 compile()", ok, probs, [])
    # 4 运行
    if only_syntax or no_run:
        if not quiet:
            print(f"  {C_DIM}- 运行检查已跳过（--syntax / --no-run）{C_END}")
    else:
        before = snapshot()
        ok, probs, warns = check_run(chapters, quiet)
        report("运行：退出码 0 且无异常回溯", ok, probs, warns)
        # 5 整洁
        ok, probs, warns = check_clean(before)
        report("整洁：无运行残留文件", ok, probs, warns)

    if all_warns and not quiet:
        print(f"\n{C_WARN}提示（不阻断交付）:{C_END}")
        for w in all_warns:
            print(f"  · {w}")

    if all_problems:
        print(f"\n{C_BAD}失败明细（{len(all_problems)} 项）:{C_END}")
        for p in all_problems:
            print(f"  ✗ {p}")

    print(
        f"\n{C_DIM}规模：笔记 {stats['notes']} 篇 / {stats['note_bytes'] / 1024:.0f} KB"
        f" · 示例脚本 {stats['scripts']} 个{C_END}"
    )
    if all_problems:
        print(f"{C_BAD}===== 自检未通过：{len(all_problems)} 项失败 ====={C_END}\n")
        return 1
    print(f"{C_OK}===== 自检全部通过 ====={C_END}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
