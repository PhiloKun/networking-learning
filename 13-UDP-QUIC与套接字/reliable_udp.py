#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 UDP 之上实现序号+累积ACK+超时重传+滑动窗口，20% 丢包下保证有序到达。

运行: python3 reliable_udp.py
"""
import random
import sys

sys.dont_write_bytecode = True

random.seed(42)

TOTAL_SEG = 20          # 待发送报文段总数
WINDOW = 4              # 发送窗口大小（报文段数）
LOSS_RATE = 0.20        # 模拟丢包率
ACK_LOSS_RATE = 0.10    # ACK 丢失率
TIMEOUT_TICKS = 3       # 超时计时器（模拟时钟刻度）


class Sender:
    def __init__(self) -> None:
        self.base = 1               # 窗口左沿（最早未确认序号）
        self.next_seq = 1           # 下一个待发序号
        self.timer = None           # 计时器剩余刻度，None 表示未启动
        self.retransmits = 0
        self.sent_count = 0
        self.acked = set()

    def window_full(self) -> bool:
        return self.next_seq >= self.base + WINDOW

    def can_send(self) -> bool:
        return self.next_seq <= TOTAL_SEG and not self.window_full()


def receiver_ack(expected: int, seq: int) -> tuple[int, bool]:
    """接收端累积确认：只有收到期望序号才前移。返回（新期望, 是否交付）。"""
    if seq == expected:
        return expected + 1, True
    return expected, False  # 乱序丢弃，重复回送当前期望-1 的 ACK


def main() -> None:
    print("=" * 68)
    print("基于 UDP 的可靠传输模拟（序号 + 累积ACK + 超时重传 + 滑动窗口）")
    print("=" * 68)
    print("参数：报文段总数=%d  窗口=%d  数据丢包率=%.0f%%  ACK丢包率=%.0f%%  超时=%d刻度"
          % (TOTAL_SEG, WINDOW, LOSS_RATE * 100, ACK_LOSS_RATE * 100, TIMEOUT_TICKS))

    tx = Sender()
    rcvexp = 1
    delivered: list[int] = []
    timeline: list[str] = []
    tick = 0
    inflight: dict[int, bool] = {}   # 已发出但未确认的序号（值为是否在飞）

    while tx.base <= TOTAL_SEG and tick < 400:
        tick += 1
        # 1) 尽可能填满窗口发送
        while tx.can_send():
            seq = tx.next_seq
            tx.next_seq += 1
            tx.sent_count += 1
            if random.random() < LOSS_RATE:
                timeline.append("t=%-3d 发 DATA seq=%d  -> [丢包]" % (tick, seq))
            else:
                inflight[seq] = True
                timeline.append("t=%-3d 发 DATA seq=%d  -> 到达" % (tick, seq))
                new_exp, ok = receiver_ack(rcvexp, seq)
                acknum = new_exp - 1
                rcvexp = new_exp
                if ok:
                    delivered.append(seq)
                if random.random() < ACK_LOSS_RATE:
                    timeline.append("t=%-3d   <- ACK ack=%d [ACK丢失]" % (tick, acknum))
                else:
                    timeline.append("t=%-3d   <- ACK ack=%d" % (tick, acknum))
                    if acknum >= tx.base:
                        # 累积确认：左沿推进到 acknum+1
                        for s in list(inflight):
                            if s <= acknum:
                                del inflight[s]
                        tx.base = acknum + 1
                        tx.timer = None
        # 2) 启动 / 推进计时器
        if tx.base < tx.next_seq and tx.timer is None:
            tx.timer = TIMEOUT_TICKS
        if tx.timer is not None:
            tx.timer -= 1
            if tx.timer <= 0:
                # 超时：回退 N，重发窗口内全部未确认报文段（go-back-N）
                resend = [s for s in range(tx.base, tx.next_seq)]
                timeline.append("t=%-3d 超时！回退到 seq=%d，重发 %s" % (tick, tx.base, resend))
                tx.retransmits += len(resend)
                tx.next_seq = tx.base  # 窗口回退，下一轮重新发送
                tx.timer = TIMEOUT_TICKS

    print("\n[1] 关键事件时间线（节选前 40 条）")
    for line in timeline[:40]:
        print("    " + line)
    print("    （共 %d 条事件）" % len(timeline))

    print("\n[2] 交付结果")
    print("    发送报文段数（含重传）= %d" % tx.sent_count)
    print("    重传次数 = %d" % tx.retransmits)
    print("    首次发送数 = %d" % TOTAL_SEG)
    print("    接收端按序交付 = %s" % (delivered == list(range(1, TOTAL_SEG + 1))))
    print("    交付序列 = %s" % delivered)

    dup_ratio = tx.retransmits / tx.sent_count * 100 if tx.sent_count else 0.0
    print("\n[3] 开销分析")
    print("    重传占比 = %d / %d = %.1f%%" % (tx.retransmits, tx.sent_count, dup_ratio))
    print(">>> 结论：在 %.0f%% 丢包下，累积ACK+超时重传仍保证数据完整按序到达；"
          % (LOSS_RATE * 100))
    print(">>>        代价是重传带来的额外带宽开销（约 %.0f%%）。" % dup_ratio)
    print(">>> 对比：若用「选择重传 SR」只重传丢失的段，重传占比会更低。")

    print("\n" + "=" * 68)
    print("小结")
    print("-" * 68)
    print("1. UDP 只提供「数据报」语义，序号 / 确认 / 重传 / 窗口全部要应用层自己实现。")
    print("2. 累积 ACK 表示「ack 号之前的所有字节都已收到」，天然容忍 ACK 丢失。")
    print("3. 回退 N（GBN）实现简单，但一个段丢失会连累窗口内后续段一起重传。")
    print("4. QUIC 把上述机制做到了协议层，并加入多路复用与 0-RTT，避免了自研的坑。")


if __name__ == "__main__":
    main()
