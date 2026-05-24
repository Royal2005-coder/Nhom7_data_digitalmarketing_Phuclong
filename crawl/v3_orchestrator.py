#!/usr/bin/env python3
"""V3 Orchestrator — SQLite + Windows compatible."""
import argparse, subprocess, sys
from datetime import datetime
from v3_config import *


def run_script(script, args_list=[]):
    cmd = [sys.executable, str(BASE_DIR / script)] + args_list
    print(f"\n{'='*70}")
    print(f"  RUN: {' '.join(cmd)}")
    print(f"  Time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*70}")
    try:
        result = subprocess.run(cmd, timeout=3600)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  ⚠ TIMEOUT: {script}")
        return False
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--skip-tiktok", action="store_true")
    parser.add_argument("--skip-facebook", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("  V3 ORCHESTRATOR — SQLite Backend")
    print(f"  Rounds: {args.rounds}")
    print("=" * 70)

    conn = get_conn()
    print_status(conn)
    conn.close()

    for r in range(args.rounds):
        print(f"\n{'#'*70}")
        print(f"  ROUND {r+1}/{args.rounds}")
        print(f"{'#'*70}")

        if not args.skip_tiktok:
            run_script("v3_token_harvester.py")
            run_script("v3_tiktok_comments.py", ["--brands", "all", "--top-n", "200"])

        if not args.skip_facebook:
            run_script("v3_facebook_comments.py", ["--brands", "all", "--top-n", "50"])

        import time
        time.sleep(30)

    conn = get_conn()
    print("\n  FINAL STATUS:")
    print_status(conn)
    conn.close()


if __name__ == "__main__":
    main()