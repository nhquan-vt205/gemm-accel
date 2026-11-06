#!/usr/bin/env python3
"""Chạy một danh sách regress và tổng hợp PASS/FAIL.

    python3 src/sim/scripts/run_regress.py src/sim/regress/unit.list [--sim questa] [--seeds 1,2,3]

Mỗi dòng của file .list:   <TB> <TC> [BIẾN=giá_trị ...]
ví dụ:                     tb_gemm_vpu  unit/vpu/basic
                           tb_gemm_accel_top  top/chain_pp  PARAMS="HAS_CHAIN=1 HAS_PINGPONG=1"
Dòng trống và dòng bắt đầu bằng # bị bỏ qua. Thoát với mã 1 nếu có test FAILED.
"""
import argparse, os, re, shlex, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SIMDIR = os.path.join(ROOT, "src", "sim")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list")
    ap.add_argument("--sim", default=os.environ.get("SIM", "questa"))
    ap.add_argument("--seeds", default="1")
    args = ap.parse_args()
    jobs = []
    for ln in open(args.list):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        tok = shlex.split(ln)
        for s in args.seeds.split(","):
            jobs.append((tok[0], tok[1], tok[2:], s))
    if not jobs:
        print("danh sách rỗng: %s" % args.list)
        return 0
    res = []
    for tb, tc, extra, seed in jobs:
        t0 = time.time()
        cmd = ["make", "-s", "-C", SIMDIR, "sim", "SIM=" + args.sim, "TB=" + tb, "TC=" + tc, "SEED=" + seed] + extra
        p = subprocess.run(cmd, capture_output=True, text=True)
        out = p.stdout + p.stderr
        m = re.search(r"TEST (PASSED|FAILED).*", out)
        ok = p.returncode == 0 and m is not None and m.group(1) == "PASSED"
        res.append((ok, tb, tc, seed, m.group(0) if m else "không có dòng kết quả", time.time() - t0))
        print("%-6s %-24s %-32s seed=%-4s %5.1fs  %s" % ("PASS" if ok else "FAIL", tb, tc, seed, res[-1][5], res[-1][4]))
    n_fail = sum(1 for r in res if not r[0])
    print("-" * 80)
    print("%d/%d PASS" % (len(res) - n_fail, len(res)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
