from __future__ import annotations

import argparse

from stock_analysis.tasks.job_runner import run_worker_forever


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Beta analysis task worker")
    parser.add_argument("--poll", type=int, default=3, help="poll interval seconds")
    parser.add_argument("--timeout", type=int, default=900, help="single job timeout seconds")
    args = parser.parse_args()

    run_worker_forever(poll_interval_seconds=args.poll, timeout_seconds=args.timeout)


if __name__ == "__main__":
    main()
