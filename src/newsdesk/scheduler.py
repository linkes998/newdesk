"""
定时调度器 —— 借鉴 smm-bot 的 daemon 模式 + ExperienceRecall 100018307/09 的时区/触发防护。

支持两种用法：
  1) 常驻后台：python -m newsdesk.scheduler   （每 30 分钟跑一次）
  2) 命令行单次：python -m newsdesk.scheduler --once
  3) 自定义频率：python -m newsdesk.scheduler --interval 20
"""
from __future__ import annotations

import argparse
import signal
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .output import main as run_newsdesk


def _job():
    print(f"[{datetime.now(timezone.utc).isoformat()}] ⏰ 定时触发 → 抓取+生成", flush=True)
    try:
        run_newsdesk()
    except Exception as exc:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ❌ 定时任务异常: {exc}", flush=True)


def run_forever(interval_minutes: int = 30) -> None:
    """常驻模式：interval_minutes 分钟跑一次。"""
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(
        _job,
        IntervalTrigger(minutes=interval_minutes),
        id="newsdesk-cycle",
        max_instances=1,  # 上一轮没跑完就跳过（防重入）
        next_run_time=datetime.now(timezone.utc),  # 启动时立即跑一次
        misfire_grace_time=300,  # 错过触发后 5 分钟内补一次
    )

    def _graceful(signum, frame):
        print(f"\n收到信号 {signum}，正在停止...", flush=True)
        sched.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _graceful)
    signal.signal(signal.SIGTERM, _graceful)

    print(f"🚀 NewsDesk scheduler 启动：每 {interval_minutes} 分钟一次（UTC），Ctrl+C 停止", flush=True)
    print(f"   下一次运行：立即执行", flush=True)
    sched.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="NewsDesk 定时调度器")
    parser.add_argument("--once", action="store_true", help="只跑一次就退出")
    parser.add_argument("--interval", type=int, default=30, help="常驻模式下的分钟数（默认 30）")
    args = parser.parse_args()

    if args.once:
        run_newsdesk()
    else:
        run_forever(interval_minutes=args.interval)


if __name__ == "__main__":
    main()
